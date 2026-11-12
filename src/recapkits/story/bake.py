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

#: summary-grid 的上限与"够用"阈值: 版式是两列网格, 六到九格都成立。
MAX_SUMMARY_FACTS = 9
SUMMARY_FACTS_ENOUGH = 6

#: 分桶事实 (小时 / 星期) 属于 clock 与星期卡, 不进总览。
BUCKET_FACT = re.compile(r"^(h\d{2}|wd_\d)$")


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


def _ranking_rows(card: Card, refs: dict[str, InsightRef]) -> list[dict[str, object]]:
    """ranking 的行: 只取 `rank_*` 事实, 保持检测器给出的名次顺序。"""
    ref = refs.get(card.insight or "")
    if ref is None:
        return []
    rows = [fact for fact in ref.fact_list if fact.key.startswith("rank_")]
    return [{"label": fact.label, "value": fact.display, "unit": fact.unit} for fact in rows[:5]]


def _summary_facts(card: Card, refs: dict[str, InsightRef]) -> list[dict[str, str]]:
    """summary-grid 的 fact: 按被引洞察轮流取, 每个洞察先给 headline。

    两条规则, 都是为了"九个格子摆出来要像一份总览, 而不是某个检测器的转储":
    - **轮流**, 不把一个洞察的事实一次抽干; 否则 24 个小时分桶会占满整张网格。
    - **跳过分桶事实** (`h00..h23` / `wd_1..wd_7`): 那是 clock 与星期卡的职责,
      在总览里只是噪声。
    同一洞察里与 headline 同 key 的事实只保留一次 (检测器常把它既放进 facts 又当
    headline), 跨洞察按标签去重。凑满 6 个且跑完一轮就停, 不再用日期之类的事实填位。
    """
    order = [card.insight, *card.evidence] if card.insight else list(card.evidence)
    sources = [refs[ident] for ident in dict.fromkeys(order) if ident in refs]
    seen_labels: set[str] = set()
    facts: list[dict[str, str]] = []
    depth = max((len(ref.fact_list) for ref in sources), default=0)
    for index in range(depth):
        for ref in sources:
            if index >= len(ref.fact_list):
                continue
            fact = ref.fact_list[index]
            if index > 0 and fact.key == ref.fact_list[0].key:
                continue
            if BUCKET_FACT.match(fact.key) or fact.label in seen_labels:
                continue
            seen_labels.add(fact.label)
            facts.append({"label": fact.label, "value": fact.display})
            if len(facts) == MAX_SUMMARY_FACTS:
                return facts
        if len(facts) >= SUMMARY_FACTS_ENOUGH:
            break
    return facts


def _series(card: Card, refs: dict[str, InsightRef]) -> dict[str, object] | None:
    """只有 heatmap / clock 需要序列; 其余卡型不把序列带进产物。"""
    if card.type not in {"heatmap", "clock"}:
        return None
    ref = refs.get(card.insight or "")
    return ref.series.as_dict() if ref is not None and ref.series is not None else None


def bake_card(card: Card, refs: dict[str, InsightRef]) -> dict[str, Any]:
    """一张卡烘焙成渲染器可直接消费的结构。"""
    copy: dict[str, str] = {}
    for slot, text in card.copy.items():
        resolved = _resolve(text, refs, card_id=card.id, slot=slot)
        _check_residue(card.id, slot, resolved)
        copy[slot] = resolved

    number: str | None = None
    if card.type == "big-number" and card.insight:
        # 只认 insight。ranking 上线后, 借 evidence 承载数字的过渡通道已删除:
        # 一个语义两种表达方式, 留着就一定会有人用错。
        ref = refs.get(card.insight)
        if ref is not None and ref.headline:
            number = ref.headline

    payload: dict[str, Any] = {
        "id": card.id,
        "type": card.type,
        "copy": copy,
        "number": number,
        "insight": card.insight,
    }
    rows = _ranking_rows(card, refs) if card.type == "ranking" else []
    if rows:
        payload["rows"] = rows
    facts = _summary_facts(card, refs) if card.type == "summary-grid" else []
    if facts:
        payload["facts"] = facts
    series = _series(card, refs)
    if series is not None:
        payload["series"] = series
    return payload


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
