# ruff: noqa: RUF001
"""把 insights 写成人类可读的 Markdown。

这条产物是为「没有 Node / 不想出图」的用户准备的: 解析三分钟之后, 至少应该拿到
一份能读的结论。分项口径与 `--explain` 完全一致, 不另算一套。
"""

from collections.abc import Sequence

from recapkits.insights.model import Insight, Period

GATED_REASONS = {
    "deviation": "没有上一期数据",
    "discontinuity": "没有上一期数据",
}

NODE_FOOTER = "要出图需要 Node 22+，或把 insights.json 交给你的 agent 生成故事。"


def _cell(text: str) -> str:
    """表格单元格: 去掉换行, 转义竖线。"""
    return text.replace("\n", " ").replace("|", "\\|")


def _one_line(insight: Insight) -> str:
    head = insight.headline_fact
    return f"{head.label} {head.display}"


def _parts(insight: Insight) -> str:
    """与 --explain 同一口径: 每项已加权值, 被闸门的项加标记。"""
    pieces = []
    for name, value in insight.score_parts.items():
        mark = "(闸门)" if name in insight.gated else ""
        pieces.append(f"{name} {value:+.2f}{mark}")
    return f"{insight.score:+.4f}（" + "，".join(pieces) + "）"


def _table(ranked: Sequence[Insight]) -> list[str]:
    lines = [
        "| # | 类型 | 一句话事实 | 分数 | 数据充足度 |",
        "|---:|---|---|---:|---|",
    ]
    for rank, insight in enumerate(ranked, start=1):
        lines.append(
            f"| {rank} | `{insight.kind}` | {_cell(_one_line(insight))} "
            f"| {insight.score:+.4f} | {insight.data_sufficiency} |"
        )
    return lines


def _breakdown(ranked: Sequence[Insight], stats: dict[str, tuple[int, int]]) -> list[str]:
    lines: list[str] = ["## 分项", ""]
    for rank, insight in enumerate(ranked, start=1):
        events, active_days = stats.get(insight.source, (0, 0))
        lines.append(f"### {rank}. `{insight.id}`")
        lines.append("")
        lines.append(f"- 事实：{_one_line(insight)}")
        lines.append(f"- 分数：{_parts(insight)}")
        lines.append(
            f"- 数据充足度：{insight.data_sufficiency}（{events} 事件 / {active_days} 活跃日）"
        )
        if insight.gated:
            detail = "、".join(
                f"{name}（{GATED_REASONS.get(name, '已关闭')}）" for name in insight.gated
            )
            lines.append(f"- 闸门：{detail}")
        for caveat in insight.caveats:
            lines.append(f"- 说明：{caveat}")
        lines.append("")
    return lines


def _gated_section(ranked: Sequence[Insight]) -> list[str]:
    gated = next((item.gated for item in ranked if item.gated), [])
    if not gated:
        return []
    lines = ["## 被闸门关闭的分量", ""]
    for name in gated:
        lines.append(f"- `{name}`：{GATED_REASONS.get(name, '已关闭')}")
    lines.append("")
    return lines


def render_markdown(
    ranked: Sequence[Insight],
    *,
    period: Period,
    stats: dict[str, tuple[int, int]],
    sources: Sequence[str],
    event_count: int,
    render_only: Sequence[Insight] = (),
) -> str:
    """返回完整的 insights.md 文本; 不写盘。"""
    data_line = f"- 数据 {'、'.join(sources) or '无'} · {event_count:,} 条事件"
    header = [
        f"# {period.start[:4]} 年度洞察",
        "",
        f"- 窗口 {period.start} 至 {period.end}（{period.tz}）",
        f"{data_line} · 覆盖率 {period.coverage:.0%}",
        "",
        "## 排名",
        "",
        *_table(ranked),
        "",
    ]
    if render_only:
        kinds = "、".join(f"`{item.kind}`" for item in render_only)
        note = (
            f"> 另有 {len(render_only)} 条渲染专用序列（{kinds}），"
            "已写入 insights.json，不参与排名。"
        )
        header.extend([note, ""])
    body = _breakdown(ranked, stats)
    tail = [*_gated_section(ranked), NODE_FOOTER, ""]
    return "\n".join([*header, *body, *tail])
