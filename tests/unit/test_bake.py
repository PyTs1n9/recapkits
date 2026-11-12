"""烘焙: 占位符只在 Python 侧解析一次, 渲染器拿到的是最终字符串。

这组测试守的是二期最关键的结构决定 —— 如果有一天 bake 被绕过, 或者渲染器自己
开始识别 `{{...}}`, 失败模式会是"校验通过但页面显示占位符", 而不是崩溃。
"""

import json
from pathlib import Path

import pytest

from recapkits.story.bake import BakeError, bake, bake_card
from recapkits.story.schema import Card, Story
from recapkits.story.validate import build_refs

FIXTURES = Path(__file__).parent.parent / "fixtures"
TOTAL = "vol.total:git:2024"


@pytest.fixture
def refs() -> dict:
    payload = json.loads((FIXTURES / "insights.json").read_text(encoding="utf-8"))
    return build_refs(payload)


def meta() -> dict:
    return {
        "year": 2024,
        "locale": "zh-CN",
        "theme": "neon",
        "tone": "deadpan",
        "tz": "Asia/Shanghai",
        "build_id": "b3:fixture1",
    }


def test_placeholders_are_replaced_with_display_strings(refs) -> None:
    """`{{id.fact}}` 换成 facts[].display, 周围文字原样保留。"""
    card = Card.from_dict(
        {
            "id": "c1",
            "type": "big-number",
            "insight": TOTAL,
            "copy": {"sub": "覆盖 {{vol.total:git:2024.active_days}} 个活跃日"},
            "evidence": [TOTAL],
        },
        0,
    )

    baked = bake_card(card, refs)

    assert baked["copy"]["sub"] == "覆盖 46 个活跃日"
    assert "{{" not in baked["copy"]["sub"]


def test_number_comes_from_headline_fact(refs) -> None:
    """big-number 的巨型数字取自主角洞察的 headline_fact.display。"""
    card = Card.from_dict(
        {"id": "c1", "type": "big-number", "insight": TOTAL, "copy": {"headline": "提交总数"}},
        0,
    )

    assert bake_card(card, refs)["number"] == "220"


def test_number_does_not_fall_back_to_evidence(refs) -> None:
    """ranking 上线后, big-number 不再借 evidence 承载数字; 没有 insight 就没有数字。"""
    card = Card.from_dict(
        {
            "id": "c1",
            "type": "big-number",
            "copy": {"headline": "提交集中度"},
            "evidence": ["conc.top_entity:repo:alpha:2024"],
        },
        0,
    )

    assert bake_card(card, refs)["number"] is None


def test_cover_has_no_number(refs) -> None:
    """cover 不引洞察, 因此没有巨型数字。"""
    card = Card.from_dict({"id": "c1", "type": "cover", "copy": {"headline": "2024"}}, 0)

    assert bake_card(card, refs)["number"] is None


def test_residual_braces_are_rejected(refs) -> None:
    """烘焙后仍有花括号 = 内部矛盾; 宁可失败也不能把字面量画出去。"""
    card = Card.from_dict(
        {
            "id": "c1",
            "type": "big-number",
            "insight": TOTAL,
            "copy": {"sub": "前置 {{vol.total:git:2024.events}} 后置 {{nope.x}}"},
        },
        0,
    )

    with pytest.raises(BakeError):
        bake_card(card, refs)


def test_unknown_insight_is_rejected(refs) -> None:
    """引用不存在的洞察: 报出卡片与槽位, 而不是静默留空。"""
    card = Card.from_dict({"id": "c1", "type": "big-number", "copy": {"sub": "{{nope.events}}"}}, 0)

    with pytest.raises(BakeError, match="nope"):
        bake_card(card, refs)


def test_baked_story_keeps_meta_and_card_order(refs) -> None:
    """整份故事: 卡片顺序不变, meta 转成渲染器使用的 camelCase。"""
    story = Story.from_dict(
        {
            "version": 1,
            "meta": meta(),
            "cards": [
                {"id": "c1", "type": "cover", "copy": {"headline": "2024"}},
                {
                    "id": "c2",
                    "type": "big-number",
                    "insight": TOTAL,
                    "copy": {"headline": "提交总数"},
                },
            ],
        }
    )

    baked = bake(story, refs)

    assert [card["id"] for card in baked["cards"]] == ["c1", "c2"]
    assert baked["meta"]["buildId"] == "b3:fixture1"
    assert baked["meta"]["year"] == 2024
    assert baked["version"] == 1
