"""四个子命令的实现: init / import / insights / doctor。

失败时都抛 `RecapError`, 由 cli.main 统一打印成一句人话。
"""

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from recapkits.adapters.base import Adapter, FileLedger, IngestReport
from recapkits.adapters.git_local import GitAdapter
from recapkits.adapters.netflix import NetflixAdapter
from recapkits.adapters.spotify import SpotifyAdapter
from recapkits.db import (
    connect,
    count_events,
    init_schema,
    insert_import_report,
    list_sources,
)
from recapkits.emit import render, write
from recapkits.errors import RecapError
from recapkits.insights import engine, markdown
from recapkits.insights.model import Insight
from recapkits.payload import measure, minimize
from recapkits.tz import rebuild_local, utc_now_iso
from recapkits.workspace import WORKSPACE, Workspace, ensure_gitignore, load_workspace

#: 内置适配器注册表: 键同时是 `--source` 的取值与自动选路的候选。
#: 顺序固定, 不用 entry point 发现 —— 那会让 detect() 依赖安装顺序, 破坏确定性。
ADAPTERS: dict[str, Adapter] = {
    "git": GitAdapter(),
    "spotify": SpotifyAdapter(),
    "netflix": NetflixAdapter(),
}

#: 自动选路时, 第一名与第二名差小于这个值就认为「像两个源」, 要求显式指定。
AMBIGUITY_MARGIN = 0.2


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


def _pick_adapter(path: Path, source: str) -> Adapter:
    """按 `--source` 取适配器; `auto` 取 detect 最高分, 分数接近就报错不猜。"""
    if source != "auto":
        return ADAPTERS[source]
    ranked = sorted(
        ((adapter.detect(path), name) for name, adapter in ADAPTERS.items()),
        key=lambda item: (-item[0], item[1]),
    )
    best_score, best_name = ranked[0]
    if best_score < 0.1:
        names = ", ".join(ADAPTERS)
        raise RecapError(f"{path} 无法识别数据源: 用 --source 显式指定 ({names})")
    if len(ranked) > 1 and ranked[1][0] >= 0.1 and best_score - ranked[1][0] < AMBIGUITY_MARGIN:
        raise RecapError(
            f"{path} 同时像 {best_name} 与 {ranked[1][1]}, 置信度太接近: 用 --source 指定"
        )
    return ADAPTERS[best_name]


def _ledger_line(ledger: FileLedger) -> str:
    """一行文件账: 文件名、解析数、跳过数与原因明细。"""
    if ledger.problem:
        return f"{ledger.name}  整份跳过 ({ledger.problem})"
    detail = ", ".join(
        f"{reason} {count}" for reason, count in sorted(ledger.reasons.items()) if count
    )
    tail = f" ({detail})" if detail else ""
    return f"{ledger.name}  解析 {ledger.rows:,} · 跳过 {ledger.skipped:,}{tail}"


def _print_report(report: IngestReport, added: int, start: str, end: str) -> None:
    """打印导入报告: 只有计数与时间, 没有任何数据内容。"""
    unit = report.unit
    print(f"源        {report.source}")
    print(f"扫描      {report.units} 个{unit}")
    print(f"解析      {report.rows:,} 条")
    print(f"新增      {added:,} 条")
    print(f"跳过      {report.skipped:,} 条")
    if report.first_ts and report.last_ts:
        print(f"时间范围  {report.first_ts} 至 {report.last_ts}")
    print(f"覆盖率    {(report.coverage or 0.0):.1%} (窗口 {start} 至 {end})")
    for note in report.notes:
        print(f"说明      {note}")
    for warning in report.warnings[:5]:
        print(f"警告      {warning}")
    if len(report.warnings) > 5:
        print(f"警告      另有 {len(report.warnings) - 5} 条省略")
    if report.files:
        print(f"逐文件    {len(report.files)} 个")
        for ledger in report.files:
            print(f"          {_ledger_line(ledger)}")


def _print_insights(
    insights: Sequence[Insight], stats: dict[str, tuple[int, int]], *, explain: bool
) -> None:
    """人类可读输出: 一行一个分数加一句事实; --explain 再补分项与充足度。"""
    ranked = [item for item in insights if item.kind not in engine.RENDER_ONLY_KINDS]
    auxiliary = [item for item in insights if item.kind in engine.RENDER_ONLY_KINDS]
    for rank, insight in enumerate(ranked, start=1):
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
    if auxiliary:
        kinds = ", ".join(item.kind for item in auxiliary)
        print(f"    (另有 {len(auxiliary)} 条渲染专用序列: {kinds}; 不参与排名)")


def _print_payload_preview(payload: dict[str, object]) -> None:
    """外发清单: 三行, 只有计数与字段名, 不打内容。

    `--json` 时由调用方改打最小版, 这里不做分支 —— 一份函数一种输出。
    """
    measurement = measure(payload)
    share = measurement.saved_share
    sign = "-" if share > 0 else ""
    tail = f"（{sign}{share:.0%}）"  # noqa: RUF001
    print(f"payload      {measurement.full_bytes:,} 字节 · {measurement.count} 条洞察")
    print(f"agent        {measurement.agent_bytes:,} 字节 · {measurement.count} 条洞察{tail}")
    detail = " · ".join(f"{key} {size:,}" for key, size in measurement.dropped) or "无"
    print(f"删除         {detail}")


def cmd_init(args: argparse.Namespace) -> int:
    """建工作区, 写配置与 .gitignore; 已有工作区时只切换 local_only。

    `--local-only` 是工作区策略而不是一次性开关: 一次设置, 所有命令一致。
    不带这个 flag 时保持「不覆盖」, 否则改个 tz 就会顺手抹掉用户的策略。
    """
    root = Path.cwd() / WORKSPACE
    config_path = root / "config.json"
    local_only = getattr(args, "local_only", None)
    if config_path.is_file():
        data = json.loads(config_path.read_text(encoding="utf-8"))
        if local_only is None:
            print(f"工作区已存在: {root} (tz={data['tz']}, year={data['year']}), 未覆盖")
            return 0
        data["local_only"] = bool(local_only)
        config_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"本地模式: {'开' if data['local_only'] else '关'} ({config_path})")
        return 0
    try:
        ZoneInfo(args.tz)
    except ZoneInfoNotFoundError as exc:
        raise RecapError(f"未知时区 {args.tz}: 请用 IANA 名称, 例如 Asia/Shanghai") from exc

    year = int(args.year) if args.year else int(utc_now_iso()[:4])
    root.mkdir(parents=True, exist_ok=True)
    config: dict[str, object] = {"tz": args.tz, "year": year, "created_at": utc_now_iso()}
    if local_only:
        config["local_only"] = True
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    ensure_gitignore()
    print(f"已创建工作区 {root} (tz={args.tz}, year={year})")
    if local_only:
        print("策略       本地模式（不生成 agent 载荷）")  # noqa: RUF001
    print(f"下一步: recap import <导出目录>  (自动识别 {' / '.join(ADAPTERS)}, 或用 --source 指定)")
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
            report = adapter.ingest(path, conn, since=since, until=until, tz=workspace.tz)
        except (OSError, RuntimeError, ValueError) as exc:
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
    """跑引擎, 选卡, 写完整版与 agent 版, 并按需打印。"""
    workspace = _require_workspace()
    entities = getattr(args, "entities", "name")
    if workspace.local_only and (args.payload_preview or entities != "name"):
        raise RecapError("本地模式不生成外发载荷: 先 recap init --no-local-only")
    if entities != "name":
        raise RecapError("--entities=placeholder 需要 agent/restore.json, 下一阶段启用")
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
        ranked = [item for item in selected if item.kind not in engine.RENDER_ONLY_KINDS]
        auxiliary = [item for item in selected if item.kind in engine.RENDER_ONLY_KINDS]
        sources = [name for name, _ in list_sources(conn)]
        payload = render(
            selected,
            sources=sources,
            event_count=count_events(conn),
            tz=workspace.tz,
        )
        out_path = write(workspace.out_path, payload)
        agent_path = (
            None
            if workspace.local_only
            else write(workspace.agent_insights_path, minimize(payload))
        )
        md_path = workspace.out_path.with_name("insights.md")
        if args.md:
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text(
                markdown.render_markdown(
                    ranked,
                    period=period,
                    stats=stats,
                    sources=sources,
                    event_count=count_events(conn),
                    render_only=auxiliary,
                ),
                encoding="utf-8",
            )

        if args.payload_preview:
            if args.json:
                print(json.dumps(minimize(payload), ensure_ascii=False, indent=2))
                return 0
            _print_payload_preview(payload)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        _print_insights(selected, stats, explain=args.explain)
        suffix = f" + {len(auxiliary)} 条渲染专用" if auxiliary else ""
        print(f"\n候选 {len(candidates)} 条, 选出 {len(ranked)} 条{suffix}")
        print(f"已写入 {out_path}")
        if args.md:
            print(f"已写入 {md_path}")
        if agent_path is not None:
            print(f"已写入 {agent_path}")
        elif workspace.agent_dir.is_dir():
            print(f"本地模式: {workspace.agent_dir} 已存在, 未改写")
        if not ranked:
            print("没有达到样本门槛的洞察: 换更长窗口, 或再导入一个源", file=sys.stderr)
        return 0
    finally:
        conn.close()
