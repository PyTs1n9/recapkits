"""四个卡片的真实渲染: 边界输入不崩、不静默截断, 且 DOM 带好 6c 的测量标记。

这些用例需要 node 与已构建的 renderer assets; 无 node 时跳过, 由 CI 的 node-gate
用一条独立断言防止"因为跳过而全绿"。
"""

import copy
import json
from pathlib import Path

import pytest

from recapkits.errors import RecapError
from recapkits.render import node
from recapkits.render.pipeline import render_document

_NODE = node.node_info()
needs_node = pytest.mark.skipif(
    _NODE is None or _NODE.major < node.MIN_NODE_MAJOR or not node.BUNDLE.is_file(),
    reason="需要 Node 22+ 与已构建的 renderer assets",
)

CONC = "conc.top_entity:repo:alpha:2024"
DAILY = "vol.daily_series:git:2024"
HOUR = "time.hour_rhythm:git:2024"
TOTAL = "vol.total:git:2024"

CARDS = [
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


def write_inputs(tmp_path: Path, payload: dict, cards: list[dict]) -> tuple[Path, Path]:
    """把 payload / story 落到临时目录, 让 render_document 走完整管线。"""
    insights = tmp_path / "insights.json"
    story = tmp_path / "story.json"
    insights.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    story.write_text(
        json.dumps(
            {
                "version": 1,
                "meta": {
                    "year": 2024,
                    "locale": "zh-CN",
                    "theme": "neon",
                    "tone": "deadpan",
                    "tz": "Asia/Shanghai",
                    "build_id": "b3:cards",
                },
                "cards": cards,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return story, insights


def insight_of(payload: dict, ident: str) -> dict:
    return next(item for item in payload["insights"] if item["id"] == ident)


@needs_node
def test_four_cards_render(tmp_path: Path, cards_payload) -> None:
    """四个类型同时出图: DOM 标记齐全, 文案真的进去了, 没有残留占位符。"""
    story, insights = write_inputs(tmp_path, cards_payload, CARDS)

    html = render_document(story, str(insights), aspect="9:16")

    assert "{{" not in html and "}}" not in html
    assert 'data-card-type="ranking"' in html
    assert "ranking__row" in html
    assert "heatmap__grid" in html
    assert 'data-cols="53"' in html
    assert "clock__svg" in html
    assert "summary-grid__cell--hero" in html
    # 六个 fact 时最后一格落单, 用横跨两列补平
    assert "summary-grid__cell--wide" in html
    assert 'data-fit="row0.label"' in html
    assert "一个特别特别长的仓库名字" in html


@needs_node
def test_four_by_five_keeps_all_cards(tmp_path: Path, cards_payload) -> None:
    """4:5 只换舞台高度, 四个卡片的标记不变。"""
    story, insights = write_inputs(tmp_path, cards_payload, CARDS)

    html = render_document(story, str(insights), aspect="4:5")

    assert "--stage-w:1080;--stage-h:1350" in html
    assert 'data-card-type="heatmap"' in html


@needs_node
def test_heatmap_draws_future_days_as_empty(tmp_path: Path, cards_payload) -> None:
    """窗口只到 3 月底: 之后的日期是"空", 不是 0。"""
    payload = copy.deepcopy(cards_payload)
    daily = insight_of(payload, DAILY)
    daily["period"]["end"] = "2024-03-31"
    daily["series"]["keys"] = daily["series"]["keys"][:91]
    daily["series"]["values"] = daily["series"]["values"][:91]
    story, insights = write_inputs(tmp_path, payload, [CARDS[1]])

    html = render_document(story, str(insights), aspect="9:16")

    assert html.count('data-empty="true"') == 366 - 91


@needs_node
def test_heatmap_all_zero_shows_a_caveat(tmp_path: Path, cards_payload) -> None:
    """全年 0 事件: 全暗但页面不崩, 并明确说明空格外形表示未发生。"""
    payload = copy.deepcopy(cards_payload)
    daily = insight_of(payload, DAILY)
    daily["series"]["values"] = [0.0] * len(daily["series"]["keys"])
    story, insights = write_inputs(tmp_path, payload, [CARDS[1]])

    html = render_document(story, str(insights), aspect="9:16")

    assert "heatmap__caveat" in html
    assert "没有事件" in html


@needs_node
def test_clock_zero_hour_degrades_to_a_line(tmp_path: Path, cards_payload) -> None:
    """某小时为 0: 该段退化成线, 其余 23 段照常。"""
    payload = copy.deepcopy(cards_payload)
    hour = insight_of(payload, HOUR)
    hour["series"]["values"] = [0.0 if index == 3 else 1 / 23 for index in range(24)]
    story, insights = write_inputs(tmp_path, payload, [CARDS[2]])

    html = render_document(story, str(insights), aspect="9:16")

    assert html.count('class="clock__zero"') == 1


@needs_node
def test_clock_all_zero_draws_a_ring(tmp_path: Path, cards_payload) -> None:
    """全 0 的 clock 画均匀细环 + caveat, 不画 24 条线冒充分布。"""
    payload = copy.deepcopy(cards_payload)
    hour = insight_of(payload, HOUR)
    hour["series"] = {
        "axis": "hour",
        "keys": [str(index) for index in range(24)],
        "values": [0.0] * 24,
        "unit": "count",
    }
    story, insights = write_inputs(tmp_path, payload, [CARDS[2]])

    html = render_document(story, str(insights), aspect="9:16")

    assert "clock__ring" in html
    assert "细环表示全零" in html


@needs_node
def test_ranking_single_row_is_legal(tmp_path: Path, cards_payload) -> None:
    """只有 1 项是合法输入, 不补空行、不拉伸。"""
    payload = copy.deepcopy(cards_payload)
    conc = insight_of(payload, CONC)
    conc["facts"] = [fact for fact in conc["facts"] if fact["key"] == "rank_1"]
    story, insights = write_inputs(tmp_path, payload, [CARDS[0]])

    html = render_document(story, str(insights), aspect="9:16")

    assert html.count('class="ranking__row"') == 1


@needs_node
def test_summary_grid_with_three_facts(tmp_path: Path, cards_payload) -> None:
    """3 个 fact 也照常渲染: 一主两副, 不补空位。"""
    payload = copy.deepcopy(cards_payload)
    for ident in (TOTAL, CONC, HOUR):
        insight_of(payload, ident)["facts"] = []
    story, insights = write_inputs(tmp_path, payload, [CARDS[3]])

    html = render_document(story, str(insights), aspect="9:16")

    assert html.count('class="summary-grid__cell') == 3
    assert "summary-grid__cell--hero" in html


@needs_node
def test_ranking_overflow_names_the_card_and_row(tmp_path: Path, cards_payload) -> None:
    """放不下的名称必须报错, 不能静默截断。"""
    payload = copy.deepcopy(cards_payload)
    conc = insight_of(payload, CONC)
    conc["facts"][0]["label"] = "超长仓库名" * 8
    story, insights = write_inputs(tmp_path, payload, [CARDS[0]])

    with pytest.raises(RecapError, match="卡片 r 的 ranking 第 1 行名称"):
        render_document(story, str(insights), aspect="9:16")
