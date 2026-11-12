"""校验调度: V1 占位符、V3 卡片规则、V4 槽位长度、V5 高敏授权。

V2 / V6 / V7 是纯文本规则, 放在 rules.py; V3 的类型/序列/证据形态在 card_rules.py。
两边都只依赖 schema 里的类型。
"""

import re

from recapkits.story.card_rules import check_card_rules
from recapkits.story.measure import SLOT_BUDGET_PX, Measure, default_measure
from recapkits.story.refs import build_refs
from recapkits.story.rules import PLACEHOLDER, check_causality, check_names, check_numbers
from recapkits.story.schema import Card, InsightRef, Story, StoryError

__all__ = ["build_refs", "validate_story"]

#: 占位符里允许的字符。必须包含 `-`, 因为 disc.* 的 id 带日期
#: (例如 disc.longest_gap:git:2024:2024-03-10); 少了它, 这类洞察永远无法被引用。
STRICT_PLACEHOLDER = re.compile(r"^[a-z0-9_.:-]+$")


def _card_allowed(card: Card) -> list[str]:
    """一张卡可以引用的洞察 id: insight 字段 + evidence 列表。"""
    allowed = [card.insight] if card.insight else []
    return [*allowed, *card.evidence]


def _check_placeholders(
    card_index: int, slot: str, text: str, allowed: list[str], refs: dict[str, InsightRef]
) -> list[StoryError]:
    """V1: 占位符必须落在该卡引用的洞察上, 且 fact 存在。"""
    errors: list[StoryError] = []
    for match in PLACEHOLDER.finditer(text):
        body = match.group(1)
        if not STRICT_PLACEHOLDER.match(body) or "." not in body:
            errors.append(
                StoryError(
                    "PLACEHOLDER_MALFORMED",
                    card_index,
                    slot,
                    body,
                    "形如 {{insight_id.fact_key}}",
                    "删掉这组花括号, 或改成被引洞察里的 fact",
                )
            )
            continue
        insight_id, _, fact_key = body.rpartition(".")
        if insight_id not in refs:
            errors.append(
                StoryError(
                    "PLACEHOLDER_UNKNOWN_INSIGHT",
                    card_index,
                    slot,
                    insight_id,
                    "已存在的洞察 id",
                    "先在 insights.json 里找到这个 id, 或改用本卡的 insight 字段",
                )
            )
            continue
        if insight_id not in allowed:
            errors.append(
                StoryError(
                    "PLACEHOLDER_NOT_REFERENCED",
                    card_index,
                    slot,
                    insight_id,
                    "本卡 insight 或 evidence 里列出的 id",
                    "把这行 id 加进 evidence, 否则数字无法从证据链复算",
                )
            )
            continue
        if fact_key not in refs[insight_id].facts:
            errors.append(
                StoryError(
                    "PLACEHOLDER_UNKNOWN_FACT",
                    card_index,
                    slot,
                    fact_key,
                    f"{insight_id} 的 fact key",
                    "抄 facts[].key 里的名字, 不要自己起名",
                )
            )
    return errors


def _check_sensitivity(
    card_index: int, card: Card, refs: dict[str, InsightRef], allow_sensitive: bool
) -> list[StoryError]:
    """V5: 高敏洞察必须由用户在命令行显式授权, JSON 里的字段一律忽略。"""
    if allow_sensitive:
        return []
    targets = [card.insight, *card.evidence] if card.insight else list(card.evidence)
    errors: list[StoryError] = []
    for insight_id in dict.fromkeys(targets):
        ref = refs.get(insight_id)
        if ref and ref.sensitivity == "high":
            errors.append(
                StoryError(
                    "SENSITIVE_REQUIRES_CONSENT",
                    card_index,
                    None,
                    insight_id,
                    "用户显式传入 --allow-sensitive",
                    "让用户自己决定, 不要写进 story.json",
                )
            )
    return errors


def _check_length(
    card_index: int, slot: str, text: str, theme: str, measure: Measure
) -> list[StoryError]:
    """V4: 槽位长度必须放得下; 占位符渲染后长度未知, 先按去掉占位符估算。"""
    budget = SLOT_BUDGET_PX.get(slot)
    if budget is None:
        return []
    width = measure(slot, PLACEHOLDER.sub("", text), theme)
    if width <= budget:
        return []
    return [
        StoryError(
            "SLOT_TOO_LONG",
            card_index,
            slot,
            f"{width:.0f}px",
            f"不超过 {budget:.0f}px",
            "缩短文案, 或把细节挪到另一张卡",
        )
    ]


def validate_story(
    story: Story,
    refs: dict[str, InsightRef],
    *,
    allow_sensitive: bool = False,
    allow_unknown_names: bool = False,
    measure: Measure = default_measure,
) -> list[StoryError]:
    """跑完 V1-V7, 返回按卡序排列的错误; 空列表表示通过。"""
    errors: list[StoryError] = []
    for index, card in enumerate(story.cards):
        allowed = _card_allowed(card)
        for slot, text in card.copy.items():
            errors += _check_placeholders(index, slot, text, allowed, refs)
            errors += check_numbers(index, slot, text)
            errors += check_causality(index, slot, text)
            if not allow_unknown_names:
                errors += check_names(index, slot, text, allowed, refs)
            errors += _check_length(index, slot, text, story.meta.theme, measure)
        errors += check_card_rules(index, card, refs)
        errors += _check_sensitivity(index, card, refs, allow_sensitive)
        if card.type == "summary-grid" and len(allowed) < 3:
            errors.append(
                StoryError(
                    "SUMMARY_NEEDS_EVIDENCE",
                    index,
                    None,
                    str(len(allowed)),
                    "至少 3 条被引洞察",
                    "补 evidence, 或换一张卡型",
                )
            )
    return errors
