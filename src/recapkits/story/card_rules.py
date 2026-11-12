"""V3: 卡片类型、所需序列与证据形态。

单独成文, 是因为 6a 之后 V3 不再只是"kind 前缀匹配": 它还要判断
`heatmap` 有没有 day 序列、`clock` 有没有 hour 序列, 以及 `big-number`
是否误用了已经删除的 evidence 通道。validate.py 只负责按卡调度。
"""

from recapkits.story.schema import Card, InsightRef, StoryError

#: 类型兼容: (kind 前缀, 精确 kind)。cover 与 summary-grid 不限。
COMPATIBILITY: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "big-number": (("vol.", "time."), ()),
    "ranking": (("conc.",), ()),
    "heatmap": ((), ("vol.daily_series",)),
    "clock": ((), ("time.hour_rhythm",)),
}

#: 需要序列的卡型与它要求的轴; 缺失或轴不符都不允许出图。
REQUIRED_SERIES_AXIS = {"heatmap": "day", "clock": "hour"}


def _check_series(card_index: int, card: Card, ref: InsightRef) -> list[StoryError]:
    """heatmap / clock 必须拿到正确轴的序列; 没有序列就不该出这张卡。"""
    axis = REQUIRED_SERIES_AXIS.get(card.type)
    if axis is None:
        return []
    if ref.series is None:
        return [
            StoryError(
                "CARD_SERIES_MISSING",
                card_index,
                None,
                ref.id,
                f"带 series 的洞察 (axis={axis})",
                "换用带序列的洞察; 序列不能塞进 display 字符串",
            )
        ]
    if ref.series.axis != axis:
        return [
            StoryError(
                "CARD_SERIES_AXIS_MISMATCH",
                card_index,
                None,
                ref.series.axis,
                f"axis={axis}",
                "heatmap 要 day 轴, clock 要 hour 轴, 不能互换",
            )
        ]
    return []


def _check_compatibility(
    card_index: int, card: Card, refs: dict[str, InsightRef]
) -> list[StoryError]:
    """卡片类型决定它能承载哪类洞察; 通过后再检查序列轴。"""
    if not card.insight:
        return []
    ref = refs.get(card.insight)
    if ref is None:
        return [
            StoryError(
                "CARD_UNKNOWN_INSIGHT",
                card_index,
                None,
                card.insight,
                "已存在的洞察 id",
                "先确认 insights.json 里有这个 id",
            )
        ]
    if card.type in {"cover", "summary-grid"}:
        return []
    prefixes, exact = COMPATIBILITY.get(card.type, ((), ()))
    if ref.kind in exact or any(ref.kind.startswith(prefix) for prefix in prefixes):
        return _check_series(card_index, card, ref)
    return [
        StoryError(
            "CARD_TYPE_MISMATCH",
            card_index,
            None,
            f"{card.type} <- {ref.kind}",
            "类型兼容的组合",
            "换一张卡型, 或换一条同族的洞察",
        )
    ]


def _check_evidence_shape(card_index: int, card: Card) -> list[StoryError]:
    """big-number 不再借用 evidence 承载数字; 挂 3 条以上证据就是误用。"""
    if card.type != "big-number" or len(card.evidence) < 3:
        return []
    return [
        StoryError(
            "TYPE_EVIDENCE_MISMATCH",
            card_index,
            None,
            f"{len(card.evidence)} 条 evidence",
            "big-number 用 insight 指定主角, evidence 不超过 2 条",
            "改用 ranking / summary-grid, 或只保留主角洞察",
        )
    ]


def check_card_rules(card_index: int, card: Card, refs: dict[str, InsightRef]) -> list[StoryError]:
    """跑完 V3 的全部检查; 空列表表示通过。"""
    return [
        *_check_compatibility(card_index, card, refs),
        *_check_evidence_shape(card_index, card),
    ]
