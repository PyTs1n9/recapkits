"""把 `insights.json` 抽成校验与烘焙共用的引用表。

单独成文, 是因为 `series` 进来之后这段解析有了契约校验的职责: 外部 agent 也可能
产出 insights.json, 不能假设它一定合法。键名与 `docs/decisions/0001-contracts.md`
一致; 序列不合法时给出带洞察 id 的错误, 而不是等到渲染阶段才崩。
"""

from typing import Any

from recapkits.insights.model import Series, SeriesError
from recapkits.story.schema import InsightRef, RefFact, StorySchemaError


def _ref_fact(raw: dict[str, Any]) -> RefFact:
    """一条事实; `display` 缺失时用 value 的字符串形态兜底。"""
    value = raw.get("value", "")
    return RefFact(
        key=str(raw.get("key", "")),
        label=str(raw.get("label", "")),
        value=value if isinstance(value, int | float | str) else str(value),
        unit=None if raw.get("unit") is None else str(raw["unit"]),
        display=str(raw.get("display", value)),
    )


def _series(raw: Any, insight_id: str, period: Any) -> Series | None:
    """解析并校验 series; 没有这个键时返回 None, 不写 null。"""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise StorySchemaError(f"洞察 {insight_id} 的 series 必须是对象")
    values = raw.get("values", [])
    if not isinstance(values, list):
        raise StorySchemaError(f"洞察 {insight_id} 的 series.values 必须是数组")
    try:
        series = Series(
            axis=str(raw.get("axis", "")),
            keys=tuple(str(key) for key in raw.get("keys", [])),
            values=tuple(values),
            unit=str(raw.get("unit", "")),
        )
        if isinstance(period, dict) and period.get("start") and period.get("end"):
            series.check_window(str(period["start"]), str(period["end"]))
    except (SeriesError, TypeError) as exc:
        raise StorySchemaError(f"洞察 {insight_id} 的 series 不合法: {exc}") from exc
    return series


def build_refs(payload: dict[str, Any]) -> dict[str, InsightRef]:
    """从 insights.json 的结构里抽出校验与烘焙所需的引用表。"""
    items = payload.get("insights", [])
    if not isinstance(items, list):
        raise StorySchemaError("insights.json 的 insights 必须是数组")
    refs: dict[str, InsightRef] = {}
    for item in items:
        if not isinstance(item, dict) or "id" not in item:
            continue
        insight_id = str(item["id"])
        headline_raw = item.get("headline_fact", {})
        facts_raw = item.get("facts", [])
        if not isinstance(headline_raw, dict):
            raise StorySchemaError(f"洞察 {insight_id} 的 headline_fact 必须是对象")
        if not isinstance(facts_raw, list):
            raise StorySchemaError(f"洞察 {insight_id} 的 facts 必须是数组")
        raw_facts = [headline_raw, *facts_raw]
        fact_list = tuple(
            _ref_fact(fact) for fact in raw_facts if isinstance(fact, dict) and "key" in fact
        )
        refs[insight_id] = InsightRef(
            id=insight_id,
            kind=str(item.get("kind", "")),
            sensitivity=str(item.get("sensitivity", "low")),
            facts={fact.key: fact.display for fact in fact_list},
            labels=[fact.label for fact in fact_list],
            headline=str(headline_raw.get("display", "")),
            fact_list=fact_list,
            series=_series(item.get("series"), insight_id, item.get("period")),
            source=str(item.get("source", "")),
        )
    return refs
