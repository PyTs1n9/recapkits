"""命令的人类可读输出: 导入报告、洞察列表、外发清单。

单独成文, 是因为 `commands` 的职责是编排 (读配置、调引擎、写文件), 而这里的
函数只做格式化。它们不读磁盘、不改状态, 所以也不需要被命令的顺序绑住。
"""

from collections.abc import Sequence

from recapkits.adapters.base import FileLedger, IngestReport
from recapkits.insights import engine
from recapkits.insights.model import Insight
from recapkits.payload import measure


def _ledger_line(ledger: FileLedger) -> str:
    """一行文件账: 文件名、解析数、跳过数与原因明细。"""
    if ledger.problem:
        return f"{ledger.name}  整份跳过 ({ledger.problem})"
    detail = ", ".join(
        f"{reason} {count}" for reason, count in sorted(ledger.reasons.items()) if count
    )
    tail = f" ({detail})" if detail else ""
    return f"{ledger.name}  解析 {ledger.rows:,} · 跳过 {ledger.skipped:,}{tail}"


def print_report(report: IngestReport, added: int, start: str, end: str) -> None:
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


def print_insights(
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


def print_payload_preview(payload: dict[str, object]) -> None:
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
