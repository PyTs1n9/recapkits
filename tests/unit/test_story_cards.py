"""story 层对四种卡片的契约: 类型兼容、序列轴、证据形态与烘焙载荷。

渲染器只读 story.json; 所以"卡片需要什么数据"必须在这里就确定下来, 不能等到
TypeScript 侧发现 series 是 undefined。
"""

import copy

from recapkits.story.bake import bake_card
from recapkits.story.refs import build_refs
from recapkits.story.schema import Card, Story
from recapkits.story.validate import validate_story

CONC = "conc.top_entity:repo:alpha:2024"
DAILY = "vol.daily_series:git:2024"
HOUR = "time.hour_rhythm:git:2024"
TOTAL = "vol.total:git:2024"


def meta() -> dict:
    return {
        "year": 2024,
        "locale": "zh-CN",
        "theme": "neon",
        "tone": "deadpan",
        "tz": "Asia/Shanghai",
        "build_id": "b3:cards",
    }


def story_of(cards: list[dict]) -> Story:
    return Story.from_dict({"version": 1, "meta": meta(), "cards": cards})


def errors_of(payload: dict, cards: list[dict]) -> list[str]:
    return [error.code for error in validate_story(story_of(cards), build_refs(payload))]


def test_four_cards_validate(cards_payload) -> None:
    """四个类型在各自的数据上都应通过; 这是 6a 的主干路径。"""
    cards = [
        {"id": "r", "type": "ranking", "insight": CONC, "copy": {"headline": "提交集中度"}},
        {"id": "h", "type": "heatmap", "insight": DAILY, "copy": {"headline": "全年节奏"}},
        {"id": "c", "type": "clock", "insight": HOUR, "copy": {"headline": "小时分布"}},
        {
            "id": "s",
            "type": "summary-grid",
            "copy": {"kicker": "总览"},
            "evidence": [TOTAL, CONC, HOUR],
        },
    ]

    assert errors_of(cards_payload, cards) == []


def test_heatmap_requires_a_day_series(cards_payload) -> None:
    """没有 series 的 vol.daily_series 不能画 heatmap: 空网格会误导成"全零"。"""
    payload = copy.deepcopy(cards_payload)
    daily = next(item for item in payload["insights"] if item["id"] == DAILY)
    del daily["series"]

    assert errors_of(
        payload,
        [{"id": "h", "type": "heatmap", "insight": DAILY, "copy": {"headline": "全年节奏"}}],
    ) == ["CARD_SERIES_MISSING"]


def test_heatmap_rejects_an_hour_series(cards_payload) -> None:
    """轴不符是错误, 不是"凑合画": hour 轴画 365 天没有任何意义。"""
    payload = copy.deepcopy(cards_payload)
    daily = next(item for item in payload["insights"] if item["id"] == DAILY)
    daily["series"] = {
        "axis": "hour",
        "keys": [str(hour) for hour in range(24)],
        "values": [1 / 24] * 24,
        "unit": "share",
    }

    assert errors_of(
        payload,
        [{"id": "h", "type": "heatmap", "insight": DAILY, "copy": {"headline": "全年节奏"}}],
    ) == ["CARD_SERIES_AXIS_MISMATCH"]


def test_clock_rejects_a_weekday_series(cards_payload) -> None:
    """clock 只认 hour 轴。"""
    payload = copy.deepcopy(cards_payload)
    hour = next(item for item in payload["insights"] if item["id"] == HOUR)
    hour["series"] = {
        "axis": "weekday",
        "keys": [str(day) for day in range(7)],
        "values": [1 / 7] * 7,
        "unit": "share",
    }

    assert errors_of(
        payload,
        [{"id": "c", "type": "clock", "insight": HOUR, "copy": {"headline": "小时分布"}}],
    ) == ["CARD_SERIES_AXIS_MISMATCH"]


def test_big_number_cannot_carry_three_evidence(cards_payload) -> None:
    """过渡通道删除后, big-number 挂 3 条以上 evidence 必须报错。"""
    cards = [
        {
            "id": "b",
            "type": "big-number",
            "insight": TOTAL,
            "copy": {"headline": "事件总数"},
            "evidence": [TOTAL, CONC, HOUR],
        }
    ]

    assert "TYPE_EVIDENCE_MISMATCH" in errors_of(cards_payload, cards)


def test_bake_ranking_rows_keep_order_and_units(cards_payload) -> None:
    """ranking 的行只取 rank_*, 顺序与检测器一致; count 保留单位提示。"""
    card = Card.from_dict(
        {"id": "r", "type": "ranking", "insight": CONC, "copy": {"headline": "提交集中度"}},
        0,
    )

    baked = bake_card(card, build_refs(cards_payload))

    assert [row["label"] for row in baked["rows"]] == [
        "一个特别特别长的仓库名字",
        "beta",
        "delta",
        "gamma",
        "epsilon",
    ]
    assert baked["rows"][0]["value"] == "137"
    assert baked["rows"][0]["unit"] == "count"


def test_bake_summary_facts_are_capped_at_nine(cards_payload) -> None:
    """summary-grid 最多 9 个 fact; 第一个是主角洞察的 headline。"""
    card = Card.from_dict(
        {
            "id": "s",
            "type": "summary-grid",
            "copy": {"kicker": "总览"},
            "evidence": [TOTAL, CONC, HOUR],
        },
        0,
    )

    baked = bake_card(card, build_refs(cards_payload))

    assert 3 <= len(baked["facts"]) <= 9
    assert baked["facts"][0] == {"label": "事件总数", "value": "220"}


def test_bake_summary_skips_hourly_buckets(cards_payload) -> None:
    """小时分桶是 clock 的职责; 总览里出现 "0 点 14" 只是噪声。"""
    card = Card.from_dict(
        {
            "id": "s",
            "type": "summary-grid",
            "copy": {"kicker": "总览"},
            "insight": TOTAL,
            "evidence": [HOUR, CONC],
        },
        0,
    )

    labels = [fact["label"] for fact in bake_card(card, build_refs(cards_payload))["facts"]]

    assert not [label for label in labels if label.endswith(" 点")]
    assert labels[0] == "事件总数"


def test_bake_summary_interleaves_insights(cards_payload) -> None:
    """轮流取: 每个被引洞察的头条先进, 再轮到第二个。"""
    card = Card.from_dict(
        {
            "id": "s",
            "type": "summary-grid",
            "copy": {"kicker": "总览"},
            "insight": TOTAL,
            "evidence": [CONC, HOUR],
        },
        0,
    )

    labels = [fact["label"] for fact in bake_card(card, build_refs(cards_payload))["facts"]]

    assert labels[:3] == ["事件总数", "占全部事件的比重", "深夜占比 22:00-03:00"]


def test_bake_summary_drops_the_headline_duplicate(cards_payload) -> None:
    """检测器常把同一个事实既写进 facts 又当 headline, 总览只该出现一次。"""
    card = Card.from_dict(
        {"id": "s", "type": "summary-grid", "copy": {"kicker": "总览"}, "insight": TOTAL},
        0,
    )

    values = [fact["value"] for fact in bake_card(card, build_refs(cards_payload))["facts"]]

    assert values[0] == "220"
    assert values.count("220") == 1


def test_bake_series_only_goes_to_heatmap_and_clock(cards_payload) -> None:
    """big-number 即使引用带序列的洞察, 也不把 series 带进产物。"""
    big = Card.from_dict(
        {"id": "b", "type": "big-number", "insight": HOUR, "copy": {"headline": "深夜占比"}},
        0,
    )
    heat = Card.from_dict(
        {"id": "h", "type": "heatmap", "insight": DAILY, "copy": {"headline": "全年节奏"}},
        1,
    )

    refs = build_refs(cards_payload)
    assert "series" not in bake_card(big, refs)
    assert bake_card(heat, refs)["series"]["axis"] == "day"
