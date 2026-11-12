"""脱敏产物的一致性闸门: id 唯一, 且故事的每个占位符都能解析。

单独成文, 是因为它检查的是"两份文件能不能配对", 而不是怎么变换。变换在
`apply`, 检查在这里 —— 一个函数同时做两件事时, 失败信息总要猜是哪一步出的。
"""

from typing import Any

from recapkits.errors import RecapError
from recapkits.story.rules import PLACEHOLDER
from recapkits.story.schema import Story, StorySchemaError
from recapkits.story.validate import build_refs


def check_unique_ids(insights: dict[str, Any]) -> None:
    """两个实体都被抑制表整体移除时会撞 id; 静默合并会让一条洞察凭空消失。"""
    raw = insights.get("insights")
    items = raw if isinstance(raw, list) else []
    ids = [str(item.get("id", "")) for item in items if isinstance(item, dict)]
    duplicated = sorted({ident for ident in ids if ids.count(ident) > 1})
    if duplicated:
        raise RecapError(f"脱敏后出现重复的洞察 id: {', '.join(duplicated)}")


def check_resolvable(insights: dict[str, Any], story: dict[str, Any]) -> None:
    """写盘前的一致性闸门: id 唯一, 且故事的每个占位符都能解析。"""
    try:
        refs = build_refs(insights)
        parsed = Story.from_dict(story)
    except StorySchemaError as exc:
        raise RecapError(f"脱敏产物没有通过结构校验: {exc}") from exc

    check_unique_ids(insights)

    for index, card in enumerate(parsed.cards, start=1):
        allowed = [card.insight] if card.insight else []
        allowed += card.evidence
        for ident in allowed:
            if ident not in refs:
                raise RecapError(f"脱敏后卡#{index}引用了不存在的洞察 {ident}")
        for slot, text in card.copy.items():
            for match in PLACEHOLDER.finditer(text):
                insight_id, dot, fact_key = match.group(1).rpartition(".")
                if not dot or insight_id not in refs:
                    raise RecapError(f"脱敏后卡#{index}的 {slot} 占位符无法解析: {match.group(0)}")
                if insight_id not in allowed:
                    raise RecapError(f"脱敏后卡#{index}的 {slot} 引用了未列出的洞察 {insight_id}")
                if fact_key not in refs[insight_id].facts:
                    raise RecapError(f"脱敏后 {insight_id} 没有事实 {fact_key}")
