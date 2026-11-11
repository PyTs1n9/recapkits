"""把 `story.json` 的占位符解析成最终字符串, 产出渲染器的输入。

**占位符逻辑只在这里存在一次。** 渲染器 (TypeScript) 不认识 `{{...}}`, 它拿到的
每一个字符串都已经是可以直接画的文本。这样做是因为: 同一套占位符语法若在两门语言
里各写一遍, 一定会漂移, 而漂移的表现是最糟的一种 —— 校验通过, 页面却显示 `{{...}}`。

顺序也是固定的: `validate` 先跑, `bake` 只在零错误时才执行, 所以烘焙时遇到
找不到的事实属于内部矛盾, 不是用户错误。
"""

import re
from typing import Any

from recapkits.story.rules import PLACEHOLDER
from recapkits.story.schema import Card, InsightRef, Story


class BakeError(ValueError):
    """烘焙失败: 占位符指不到事实, 或烘焙后仍有残留。"""


def _resolve(text: str, refs: dict[str, InsightRef], *, card_id: str, slot: str) -> str:
    """把一处文案里的全部占位符换成 `display` 字符串。"""

    def replace(match: re.Match[str]) -> str:
        body = str(match.group(1))
        insight_id, _, fact_key = body.rpartition(".")
        ref = refs.get(insight_id)
        if ref is None:
            raise BakeError(f"卡片 {card_id} 的 {slot} 引用了不存在的洞察 {insight_id!r}")
        if fact_key not in ref.facts:
            raise BakeError(f"卡片 {card_id} 的 {slot} 引用了 {insight_id} 没有的事实 {fact_key!r}")
        return ref.facts[fact_key]

    return PLACEHOLDER.sub(replace, text)


def _check_residue(card_id: str, slot: str, text: str) -> None:
    """烘焙之后不该再有花括号; 有就是内部矛盾, 宁可失败也不把字面量画出去。"""
    if "{{" in text or "}}" in text:
        raise BakeError(f"卡片 {card_id} 的 {slot} 烘焙后仍残留占位符: {text!r}")


def bake_card(card: Card, refs: dict[str, InsightRef]) -> dict[str, Any]:
    """一张卡烘焙成渲染器可直接消费的结构。"""
    copy: dict[str, str] = {}
    for slot, text in card.copy.items():
        resolved = _resolve(text, refs, card_id=card.id, slot=slot)
        _check_residue(card.id, slot, resolved)
        copy[slot] = resolved

    number: str | None = None
    if card.type == "big-number":
        # 优先用主角洞察的 headline_fact; 没有 insight 时退回首条 evidence。
        # 这条退路是为 ranking 落地前准备的: 集中度、断裂类只能借 evidence 上卡。
        target = card.insight or (card.evidence[0] if card.evidence else None)
        ref = refs.get(target) if target else None
        if ref is not None and ref.headline:
            number = ref.headline

    return {
        "id": card.id,
        "type": card.type,
        "copy": copy,
        "number": number,
        "insight": card.insight,
    }


def bake(story: Story, refs: dict[str, InsightRef]) -> dict[str, Any]:
    """整份故事烘焙成渲染器的输入; 键名用 camelCase 对齐 TypeScript 侧的类型。"""
    return {
        "version": 1,
        "meta": {
            "year": story.meta.year,
            "locale": story.meta.locale,
            "theme": story.meta.theme,
            "tone": story.meta.tone,
            "buildId": story.meta.build_id,
        },
        "cards": [bake_card(card, refs) for card in story.cards],
    }
