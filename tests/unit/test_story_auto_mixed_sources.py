"""`--auto` 的多源规则: 只讲主源的故事, 其余源的卡进跳过表并写明原因。

主源判定: 已选洞察里 `source` 出现次数最多者; 平局比该源的最小洞察 id;
渲染专用序列不参与计票。判定结果必须解释得清, 否则用户会以为卡片随机消失。
"""

import pytest

from recapkits.story import auto, templates
from recapkits.story.auto import MIXED, NO_HOUR
from recapkits.story.schema import InsightRef

PERIOD = {"start": "2024-01-01", "end": "2024-12-31", "tz": "Asia/Shanghai", "coverage": 0.5}


def entry(
    kind: str,
    source: str,
    ident: str,
    *,
    value: float = 0.5,
    sensitivity: str = "low",
    with_source: bool = True,
) -> dict:
    """一条最小洞察; 只填 build_refs 与模板会读的字段。"""
    payload = {
        "id": ident,
        "kind": kind,
        "period": PERIOD,
        "headline_fact": {
            "key": "share",
            "label": "占比",
            "value": value,
            "unit": "pct",
            "display": f"{value:.0%}",
        },
        "facts": [
            {
                "key": "share",
                "label": "占比",
                "value": value,
                "unit": "pct",
                "display": f"{value:.0%}",
            }
        ],
        "evidence_sql": "SELECT 1",
        "evidence_rows": 1,
        "score": 0.5,
        "score_parts": {},
        "novelty": "constant",
        "sensitivity": sensitivity,
        "data_sufficiency": "ok",
        "gated": [],
        "caveats": [],
    }
    if with_source:
        payload["source"] = source
    return payload


def payload_of(items: list[dict]) -> dict:
    return {
        "version": 1,
        "build_id": "b3:mixed",
        "generated_from": {
            "sources": sorted({item.get("source", "") for item in items}),
            "event_count": 100,
            "tz": "Asia/Shanghai",
        },
        "insights": items,
    }


def cards(result: auto.Plan) -> dict[str, dict]:
    return {str(card["id"]): card for card in result.story["cards"]}


def referenced(card: dict) -> list[str]:
    """一张卡引用的所有洞察 id。"""
    ids = [card["insight"]] if card.get("insight") else []
    return [*ids, *card.get("evidence", [])]


def primary_id(card: dict) -> str:
    """卡的主洞察: cover 用 evidence[0], 其余用 insight。"""
    return str(card.get("insight") or card["evidence"][0])


def test_minority_source_cards_are_skipped_with_reason() -> None:
    """spotify 多数票, 但时钟只在 git 有: clock 进跳过表并点名两个源。"""
    items = [
        entry("vol.total", "spotify", "vol.total:spotify:2024"),
        entry("conc.top_entity", "spotify", "conc.top_entity:artist:a:2024"),
        entry("time.weekday_rhythm", "spotify", "time.weekday_rhythm:spotify:2024"),
        entry("vol.daily_series", "spotify", "vol.daily_series:spotify:2024"),
        entry("vol.total", "git", "vol.total:git:2024"),
        entry("time.hour_rhythm", "git", "time.hour_rhythm:git:2024"),
        entry("vol.daily_series", "git", "vol.daily_series:git:2024"),
    ]

    result = auto.plan(payload_of(items), year=2024)

    built = cards(result)
    assert primary_id(built["cover"]) == "vol.total:spotify:2024"
    assert built["ranking"]["insight"] == "conc.top_entity:artist:a:2024"
    assert built["heatmap"]["insight"] == "vol.daily_series:spotify:2024"
    assert ("clock", MIXED.format(primary="spotify", others="git")) in [
        (skip.card, skip.reason) for skip in result.skips
    ]
    for card in built.values():
        assert all("git" not in ident for ident in referenced(card)), card["id"]


def test_tie_breaks_by_smallest_insight_id() -> None:
    """2:2 时按该源最小 id 升序: artist 排在 repo 前面, spotify 胜。"""
    items = [
        entry("vol.total", "git", "vol.total:git:2024"),
        entry("conc.top_entity", "git", "conc.top_entity:repo:a:2024"),
        entry("vol.total", "spotify", "vol.total:spotify:2024"),
        entry("conc.top_entity", "spotify", "conc.top_entity:artist:b:2024"),
    ]

    result = auto.plan(payload_of(items), year=2024)

    assert primary_id(cards(result)["cover"]) == "vol.total:spotify:2024"
    assert cards(result)["ranking"]["copy"]["headline"] == "听得最多的艺人"


def test_three_sources_pick_the_majority() -> None:
    """netflix 两票胜出; 只有它有的排名与封面进卡。"""
    items = [
        entry("vol.total", "git", "vol.total:git:2024"),
        entry("vol.total", "spotify", "vol.total:spotify:2024"),
        entry("vol.total", "netflix", "vol.total:netflix:2024"),
        entry("conc.top_entity", "netflix", "conc.top_entity:show:a:2024"),
    ]

    result = auto.plan(payload_of(items), year=2024)

    assert primary_id(cards(result)["cover"]) == "vol.total:netflix:2024"
    assert cards(result)["ranking"]["copy"]["headline"] == "看得最多的剧集"
    assert ("clock", NO_HOUR) in [(skip.card, skip.reason) for skip in result.skips]


def test_single_source_story_is_unchanged() -> None:
    """单一 git 源: 有没有 source 键都生成同一份故事。"""
    items = [
        entry("vol.total", "git", "vol.total:git:2024"),
        entry("conc.top_entity", "git", "conc.top_entity:repo:a:2024"),
        entry("time.hour_rhythm", "git", "time.hour_rhythm:git:2024"),
    ]
    without = [{key: value for key, value in item.items() if key != "source"} for item in items]

    assert (
        auto.plan(payload_of(items), year=2024).as_json()
        == auto.plan(payload_of(without), year=2024).as_json()
    )


def test_render_only_series_do_not_vote() -> None:
    """两条 daily_series 不给 spotify 加票: git 用 1 条洞察胜出。"""
    items = [
        entry("vol.daily_series", "spotify", "vol.daily_series:spotify:2024:a"),
        entry("vol.daily_series", "spotify", "vol.daily_series:spotify:2024:b"),
        entry("vol.total", "git", "vol.total:git:2024"),
    ]

    result = auto.plan(payload_of(items), year=2024)

    assert primary_id(cards(result)["cover"]) == "vol.total:git:2024"


def test_payload_without_sources_keeps_old_behaviour() -> None:
    """手写 payload 没有 source 键: 不做主源过滤, 也不出现混源理由。"""
    items = [
        entry("vol.total", "", "vol.total:a:2024", with_source=False),
        entry("conc.top_entity", "", "conc.top_entity:repo:a:2024", with_source=False),
    ]

    result = auto.plan(payload_of(items), year=2024)

    assert not any("主源" in skip.reason for skip in result.skips)
    assert cards(result)["ranking"]["copy"]["headline"] == "出现最多的项目"


@pytest.mark.parametrize(
    ("source", "headline"),
    [
        ("git", "出现最多的项目"),
        ("spotify", "听得最多的艺人"),
        ("netflix", "看得最多的剧集"),
        (None, "出现最多的项目"),
    ],
)
def test_ranking_headline_follows_the_source(source: str | None, headline: str) -> None:
    """只换 ranking 这一句; 未知源回落到 git 文案。"""
    ref = InsightRef(
        id="conc.top_entity:artist:a:2024",
        kind="conc.top_entity",
        sensitivity="low",
        facts={"share": "40%"},
        labels=["a"],
    )

    template = templates.copy("ranking", {"conc.top_entity": ref}, 2024, source=source)

    assert template.headline == headline
