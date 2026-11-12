"""把洞察写成 `insights.json`, 结构与契约 §5.2 逐字段对应。"""

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from recapkits import __version__
from recapkits.insights.model import Fact, Insight


def _fact(fact: Fact) -> dict[str, object]:
    """按契约的键序展开一个事实。"""
    return {
        "key": fact.key,
        "label": fact.label,
        "value": fact.value,
        "unit": fact.unit,
        "display": fact.display,
    }


def _insight(insight: Insight) -> dict[str, object]:
    """按契约的键序展开一条洞察; 没有 series 的洞察不写这个键。"""
    period = insight.period
    payload: dict[str, object] = {
        "id": insight.id,
        "kind": insight.kind,
        "source": insight.source,
        "period": {
            "start": period.start,
            "end": period.end,
            "tz": period.tz,
            "coverage": period.coverage,
        },
        "headline_fact": _fact(insight.headline_fact),
        "facts": [_fact(fact) for fact in insight.facts],
    }
    if insight.series is not None:
        payload["series"] = insight.series.as_dict()
    payload.update(
        {
            "evidence_sql": insight.evidence_sql,
            "evidence_rows": insight.evidence_rows,
            "score": insight.score,
            "score_parts": dict(insight.score_parts),
            "novelty": insight.novelty,
            "sensitivity": insight.sensitivity,
            "data_sufficiency": insight.data_sufficiency,
            "gated": list(insight.gated),
            "caveats": list(insight.caveats),
        }
    )
    return payload


def build_id(
    *, tz: str, sources: Sequence[str], event_count: int, insights: Sequence[Insight]
) -> str:
    """由引擎版本、窗口、输入规模与候选 id 派生, 同样的输入永远得到同样的 id。"""
    seed = "|".join(
        [
            __version__,
            tz,
            ",".join(sorted(sources)),
            str(event_count),
            ",".join(item.id for item in insights),
        ]
    )
    return "b3:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]


def render(
    insights: Sequence[Insight], *, sources: Sequence[str], event_count: int, tz: str
) -> dict[str, object]:
    """返回完整的 insights.json 结构; 不写盘, 便于 CLI 既打印又落盘。"""
    return {
        "version": 1,
        "build_id": build_id(tz=tz, sources=sources, event_count=event_count, insights=insights),
        "generated_from": {
            "sources": list(sources),
            "event_count": event_count,
            "tz": tz,
        },
        "insights": [_insight(insight) for insight in insights],
    }


def write(path: Path, payload: dict[str, object]) -> Path:
    """把结构写到磁盘, UTF-8、两空格缩进、结尾一个换行。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
    return path
