"""四个子命令的实现: init / import / insights / doctor。

失败时都抛 `RecapError`, 由 cli.main 统一打印成一句人话。
"""

import argparse
import json
import platform
import shutil
import subprocess
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from recapkits import __version__
from recapkits.adapters.base import IngestReport
from recapkits.adapters.git_local import GitAdapter
from recapkits.db import (
    connect,
    count_events,
    init_schema,
    insert_import_report,
    list_sources,
)
from recapkits.emit import render, write
from recapkits.errors import RecapError
from recapkits.insights import engine
from recapkits.insights.model import Insight
from recapkits.tz import rebuild_local, utc_now_iso
from recapkits.workspace import WORKSPACE, Workspace, ensure_gitignore, load_workspace


def _require_workspace() -> Workspace:
    """取工作区; 没有就提醒先 init。"""
    workspace = load_workspace()
    if workspace is None:
        raise RecapError("未找到工作区: 先运行 recap init --tz Asia/Shanghai")
    return workspace


def _parse_date(text: str | None, flag: str) -> date | None:
    """把命令行日期解析为 date; 格式不对就给一句人话。"""
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise RecapError(f"{flag} 需要 YYYY-MM-DD, 收到 {text}") from exc


def _pick_adapter(path: Path, source: str) -> GitAdapter:
    """目前只有 git; auto 模式下置信度为 0 就报错, 不猜。"""
    if source == "git":
        return GitAdapter()
    adapter = GitAdapter()
    if adapter.detect(path) < 0.1:
        raise RecapError(f"{path} 下没有 git 仓库: 换一个目录, 或用 --source git 显式指定")
    return adapter


def _print_report(report: IngestReport, added: int, start: str, end: str) -> None:
    """打印导入报告: 只有计数与时间, 没有任何数据内容。"""
    unit = "仓库" if report.source == "git" else "文件"
    print(f"源        {report.source}")
    print(f"扫描      {report.units} 个{unit}")
    print(f"解析      {report.rows:,} 条")
    print(f"新增      {added:,} 条")
    print(f"跳过      {report.skipped:,} 条")
    if report.first_ts and report.last_ts:
        print(f"时间范围  {report.first_ts} 至 {report.last_ts}")
    print(f"覆盖率    {(report.coverage or 0.0):.1%} (窗口 {start} 至 {end})")
    for warning in report.warnings[:5]:
        print(f"警告      {warning}")
    if len(report.warnings) > 5:
        print(f"警告      另有 {len(report.warnings) - 5} 条省略")


def _print_insights(
    insights: Sequence[Insight], stats: dict[str, tuple[int, int]], *, explain: bool
) -> None:
    """人类可读输出: 一行一个分数加一句事实; --explain 再补分项与充足度。"""
    for rank, insight in enumerate(insights, start=1):
        head = insight.headline_fact
        print(f"{rank:>2}. {insight.score:+.3f}  {insight.kind:<22} {head.label} {head.display}")
        if not explain:
            continue
        parts = "  ".join(
            f"{name} {value:+.2f}" + ("(闸门)" if name in insight.gated else "")
            for name, value in insight.score_parts.items()
        )
        print(f"    {parts}")
        events, active_days = stats.get(insight.source, (0, 0))
        print(f"    数据充足度: {insight.data_sufficiency} ({events} 事件 / {active_days} 活跃日)")


def cmd_init(args: argparse.Namespace) -> int:
    """建工作区, 写配置与 .gitignore; 已存在时只提示。"""
    root = Path.cwd() / WORKSPACE
    config_path = root / "config.json"
    if config_path.is_file():
        data = json.loads(config_path.read_text(encoding="utf-8"))
        print(f"工作区已存在: {root} (tz={data['tz']}, year={data['year']}), 未覆盖")
        return 0
    try:
        ZoneInfo(args.tz)
    except ZoneInfoNotFoundError as exc:
        raise RecapError(f"未知时区 {args.tz}: 请用 IANA 名称, 例如 Asia/Shanghai") from exc

    year = int(args.year) if args.year else int(utc_now_iso()[:4])
    root.mkdir(parents=True, exist_ok=True)
    config = {"tz": args.tz, "year": year, "created_at": utc_now_iso()}
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    ensure_gitignore()
    print(f"已创建工作区 {root} (tz={args.tz}, year={year})")
    print("下一步: recap import <导出目录> --source git")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    """检测适配器, 入库, 重建本地层, 打印报告。"""
    workspace = _require_workspace()
    path = Path(args.path).expanduser()
    if not path.exists():
        raise RecapError(f"路径不存在: {args.path}")

    since = _parse_date(args.since, "--since")
    until = _parse_date(args.until, "--until")
    if since and until and since > until:
        raise RecapError(f"--since {since} 晚于 --until {until}")
    adapter = _pick_adapter(path, args.source)

    conn = connect(workspace.db_path)
    try:
        init_schema(conn)
        before = count_events(conn)
        try:
            report = adapter.ingest(path, conn, since=since, until=until)
        except (OSError, RuntimeError) as exc:
            raise RecapError(str(exc)) from exc
        rebuild_local(conn, workspace.tz)
        start, end = engine.review_window(workspace.year)
        report.coverage = engine.coverage(conn, tz=workspace.tz, start=start, end=end)
        insert_import_report(
            conn,
            source=report.source,
            src_hash=report.src_hash,
            rows=report.rows,
            skipped=report.skipped,
            warnings=report.warnings,
            coverage=report.coverage,
            created_at=utc_now_iso(),
        )
        _print_report(report, count_events(conn) - before, start, end)
    finally:
        conn.close()
    return 0


def cmd_insights(args: argparse.Namespace) -> int:
    """跑引擎, 选卡, 写 insights.json, 并按需打印。"""
    workspace = _require_workspace()
    if not workspace.db_path.is_file():
        raise RecapError("还没有数据库: 先运行 recap import <目录>")

    conn = connect(workspace.db_path)
    try:
        init_schema(conn)
        try:
            period = engine.build_period(conn, tz=workspace.tz, year=workspace.year)
            candidates = engine.run(conn, tz=workspace.tz, year=workspace.year)
        except ValueError as exc:
            raise RecapError(str(exc)) from exc
        stats = engine.source_stats(conn, period)
        selected = engine.select(candidates, top=args.top)
        payload = render(
            selected,
            sources=[name for name, _ in list_sources(conn)],
            event_count=count_events(conn),
            tz=workspace.tz,
        )
        out_path = write(workspace.out_path, payload)

        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        _print_insights(selected, stats, explain=args.explain)
        print(f"\n候选 {len(candidates)} 条, 选出 {len(selected)} 条, 已写入 {out_path}")
        if not selected:
            print("没有达到样本门槛的洞察: 换更长窗口, 或再导入一个源", file=sys.stderr)
        return 0
    finally:
        conn.close()


def cmd_doctor(args: argparse.Namespace) -> int:
    """诊断环境与工作区: 只打印计数, 不打印任何数据内容。"""
    print(f"recapkits  {__version__}")
    print(f"python     {platform.python_version()} ({sys.platform})")
    git = shutil.which("git")
    if git:
        completed = subprocess.run([git, "--version"], capture_output=True, text=True, check=False)
        print(f"git        {completed.stdout.strip() or git}")
    else:
        print("git        未找到; import --source git 不可用")

    node = shutil.which("node")
    if node:
        completed = subprocess.run([node, "--version"], capture_output=True, text=True, check=False)
        print(f"node       {completed.stdout.strip() or node}")
    else:
        print("node       未找到; render 不可用 (HTML 由 renderer 构建产物产出)")

    try:
        ZoneInfo("Asia/Shanghai")
        print("时区数据   可用")
    except ZoneInfoNotFoundError:
        print("时区数据   缺失; Windows 需要 tzdata")

    workspace = load_workspace()
    if workspace is None:
        print("workspace  未初始化; 先运行 recap init")
        return 0
    print(f"workspace  {WORKSPACE}/  tz={workspace.tz}  year={workspace.year}")
    if not workspace.db_path.is_file():
        print("events     数据库不存在")
        return 0

    conn = connect(workspace.db_path)
    try:
        init_schema(conn)
        total = count_events(conn)
        sources = list_sources(conn)
    finally:
        conn.close()

    print(f"events     {len(sources)} 个源, {total:,} 条事件")
    for name, count in sources:
        print(f"           {name}  {count:,}")
    return 0
