"""校验器的对抗用例: 每条规则至少一个正例与一个反例。"""

import json
from pathlib import Path
from typing import Any

import pytest

from recapkits.cli import main
from recapkits.story.schema import Story
from recapkits.story.validate import build_refs, validate_story

FIXTURES = Path(__file__).parent.parent / "fixtures"
META = {
    "year": 2024,
    "locale": "zh-CN",
    "theme": "neon",
    "tone": "deadpan",
    "tz": "Asia/Shanghai",
    "build_id": "b3:fixture1",
}
TOTAL = "vol.total:git:2024"
ALPHA = "conc.top_entity:repo:alpha:2024"
HEALTH = "conc.top_entity:repo:health:2024"


def refs() -> dict[str, Any]:
    """fixtures/insights.json 里的三条洞察。"""
    payload = json.loads((FIXTURES / "insights.json").read_text(encoding="utf-8"))
    return build_refs(payload)


def story(*cards: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"version": 1, "meta": META, "cards": list(cards), **extra}


def card(
    card_type: str,
    copy: dict[str, str],
    *,
    insight: str | None = None,
    evidence: tuple[str, ...] = (),
    ident: str = "c1",
) -> dict[str, Any]:
    body: dict[str, Any] = {"id": ident, "type": card_type, "copy": copy}
    if insight is not None:
        body["insight"] = insight
    if evidence:
        body["evidence"] = list(evidence)
    return body


def codes(payload: dict[str, Any], **kwargs: Any) -> list[str]:
    return [error.code for error in validate_story(Story.from_dict(payload), refs(), **kwargs)]


def test_valid_story_passes() -> None:
    """占位符全部解析、无手写数字、名字都在实体表里。"""
    payload = story(
        card("cover", {"headline": "2024", "kicker": "本地生成 · 未上传"}),
        card(
            "big-number",
            {"headline": "{{vol.total:git:2024.events}} 次提交", "sub": "一天不落"},
            insight=TOTAL,
            evidence=(TOTAL,),
        ),
    )

    assert codes(payload) == []


def test_placeholder_to_missing_insight() -> None:
    """V1: 引用一个不存在的洞察 id。"""
    payload = story(card("big-number", {"headline": "{{nope.events}} 次"}, insight=TOTAL))

    assert "PLACEHOLDER_UNKNOWN_INSIGHT" in codes(payload)


def test_placeholder_not_referenced_by_card() -> None:
    """V1: 洞察存在, 但没写进本卡的 insight / evidence。"""
    payload = story(card("big-number", {"headline": "{{vol.total:git:2024.events}} 次"}))

    assert codes(payload) == ["PLACEHOLDER_NOT_REFERENCED"]


def test_placeholder_unknown_fact() -> None:
    """V1: id 对了, fact key 是编的。"""
    payload = story(
        card("big-number", {"headline": "{{vol.total:git:2024.nope}} 次"}, insight=TOTAL)
    )

    assert codes(payload) == ["PLACEHOLDER_UNKNOWN_FACT"]


def test_malformed_placeholder() -> None:
    """V1: 少了点号或带大写, 直接判畸形。"""
    payload = story(card("big-number", {"headline": "{{vol total}} 次"}, insight=TOTAL))

    assert codes(payload) == ["PLACEHOLDER_MALFORMED"]


def test_arabic_digits_rejected() -> None:
    """V2: 手写阿拉伯数字。"""
    payload = story(card("big-number", {"headline": "共 1234 次提交"}, insight=TOTAL))

    assert codes(payload) == ["NUMBER_NOT_IN_PLACEHOLDER"]


def test_fullwidth_digits_rejected() -> None:
    """V2: 全角数字同样不行。"""
    payload = story(
        card("big-number", {"headline": "\u5171 \uff11\uff12\uff13\uff14 \u6b21"}, insight=TOTAL)
    )

    assert codes(payload) == ["NUMBER_NOT_IN_PLACEHOLDER"]


def test_chinese_numeral_rejected() -> None:
    """V2: 数词 + 量词。"""
    payload = story(card("big-number", {"headline": "三次提交"}, insight=TOTAL))

    assert codes(payload) == ["NUMBER_NOT_IN_PLACEHOLDER"]


def test_english_numeral_rejected() -> None:
    """V2: 英文数词。"""
    payload = story(card("big-number", {"headline": "three commits"}, insight=TOTAL))

    assert codes(payload) == ["NUMBER_NOT_IN_PLACEHOLDER"]


def test_idiom_is_not_a_number() -> None:
    """V2 防误伤: 「一天不落」不是数量。"""
    payload = story(card("big-number", {"sub": "一天不落"}, insight=TOTAL))

    assert codes(payload) == []


def test_year_is_allowed() -> None:
    """V2 防误伤: 年份是白名单。"""
    payload = story(card("cover", {"headline": "2026", "kicker": "2026 年回顾"}))

    assert codes(payload) == []


def test_allow_sensitive_in_json_is_ignored() -> None:
    """V5: 写进 story.json 的 allow_sensitive 不算授权。"""
    payload = story(
        card(
            "ranking",
            {"headline": "{{conc.top_entity:repo:health:2024.share}} 集中"},
            insight=HEALTH,
        ),
        allow_sensitive=True,
    )

    assert "SENSITIVE_REQUIRES_CONSENT" in codes(payload)
    assert codes(payload, allow_sensitive=True) == []


def test_proper_noun_outside_evidence() -> None:
    """V6: 文案里出现实体表外的专有名词。"""
    payload = story(card("big-number", {"headline": "Spotify 年度提交"}, insight=TOTAL))

    assert codes(payload) == ["NAME_NOT_IN_EVIDENCE"]
    assert codes(payload, allow_unknown_names=True) == []


def test_quoted_name_outside_evidence() -> None:
    """V6: 中文引号里的名字同样要能追溯到事实。"""
    payload = story(card("big-number", {"headline": "《深度工作》读了很久"}, insight=TOTAL))

    assert codes(payload) == ["NAME_NOT_IN_EVIDENCE"]


def test_slot_too_long() -> None:
    """V4: 一行塞不下两百个字。"""
    payload = story(card("big-number", {"headline": "长" * 200}, insight=TOTAL))

    assert codes(payload) == ["SLOT_TOO_LONG"]


def test_card_type_mismatch() -> None:
    """V3: ranking 卡装不下 vol.total。"""
    payload = story(card("ranking", {"headline": "排名"}, insight=TOTAL))

    assert codes(payload) == ["CARD_TYPE_MISMATCH"]


def test_summary_grid_needs_three_insights() -> None:
    """V3 补充: summary-grid 至少三条证据。"""
    payload = story(card("summary-grid", {"headline": "汇总"}, insight=TOTAL))

    assert codes(payload) == ["SUMMARY_NEEDS_EVIDENCE"]


def test_causality_is_forbidden() -> None:
    """V7: 因果与诊断。"""
    payload = story(card("big-number", {"sub": "这说明你很努力"}, insight=TOTAL))

    assert codes(payload) == ["FORBIDDEN_CAUSALITY"]


def test_fixture_story_is_valid() -> None:
    """随附的 story-valid.json 必须通过。"""
    payload = json.loads((FIXTURES / "story-valid.json").read_text(encoding="utf-8"))

    assert codes(payload) == []


def test_cli_accepts_fixture(tmp_path: Path, monkeypatch, capsys) -> None:
    """裸命令也能跑: insights.json 与故事同目录。"""
    monkeypatch.chdir(tmp_path)

    assert main(["story", "--check", str(FIXTURES / "story-valid.json")]) == 0
    assert "通过" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["story-bad-sum.json", "story-bad-sensitive.json"])
def test_cli_rejects_bad_fixtures(tmp_path: Path, monkeypatch, capsys, name: str) -> None:
    """两份坏样本都必须以退出码 1 结束, 并指出问题代码。"""
    monkeypatch.chdir(tmp_path)

    assert main(["story", "--check", str(FIXTURES / name)]) == 1
    assert "[" in capsys.readouterr().err


def test_sibling_insights_wins_over_workspace(tmp_path: Path, monkeypatch, capsys) -> None:
    """同目录的 insights.json 优先于当前工作区, fixture 才不会被无关数据顶掉。"""
    monkeypatch.chdir(tmp_path)
    out = tmp_path / ".recapkits" / "out"
    out.mkdir(parents=True)
    (out / "insights.json").write_text('{"insights": []}', encoding="utf-8")

    assert main(["story", "--check", str(FIXTURES / "story-valid.json")]) == 0
    assert "通过" in capsys.readouterr().out
