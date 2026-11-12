"""12 个对抗性故事: 每条只踩一个规则, 拒绝理由必须正好是那一个码。

**JSON 没有 `//` 注释**, 所以每个 fixture 用顶层 `_comment` 写清"这条在模拟什么";
`Story.from_dict` 只读 version / meta / cards, 多余的键不会进校验。

断言用**理由码集合**而不是"有错误": 任何一条无关错误都能让"有错误"变绿, 而用户
看到的是另一个问题。样例顺带踩了别的规则时, 改样例, 不放宽断言。
"""

import json
from pathlib import Path
from typing import Any

import pytest

from recapkits.story.schema import InsightRef, Story
from recapkits.story.validate import build_refs, validate_story

ADVERSARIAL = Path(__file__).parent.parent / "fixtures" / "adversarial"

CASES = (
    ("01-placeholder-not-referenced.json", "PLACEHOLDER_NOT_REFERENCED"),
    ("02-placeholder-unknown-fact.json", "PLACEHOLDER_UNKNOWN_FACT"),
    ("03-placeholder-malformed.json", "PLACEHOLDER_MALFORMED"),
    ("04-arabic-digits.json", "NUMBER_NOT_IN_PLACEHOLDER"),
    ("05-chinese-numeral.json", "NUMBER_NOT_IN_PLACEHOLDER"),
    ("06-fullwidth-digits.json", "NUMBER_NOT_IN_PLACEHOLDER"),
    ("07-card-type-mismatch.json", "CARD_TYPE_MISMATCH"),
    ("08-card-series-missing.json", "CARD_SERIES_MISSING"),
    ("09-slot-too-long.json", "SLOT_TOO_LONG"),
    ("10-sensitive-without-consent.json", "SENSITIVE_REQUIRES_CONSENT"),
    ("11-name-not-in-evidence.json", "NAME_NOT_IN_EVIDENCE"),
    ("12-forbidden-causality.json", "FORBIDDEN_CAUSALITY"),
)


def refs() -> dict[str, InsightRef]:
    payload = json.loads((ADVERSARIAL / "insights.json").read_text(encoding="utf-8"))
    return build_refs(payload)


def story_payload(name: str) -> dict[str, Any]:
    return json.loads((ADVERSARIAL / name).read_text(encoding="utf-8"))


def codes(name: str, **kwargs: Any) -> list[str]:
    errors = validate_story(Story.from_dict(story_payload(name)), refs(), **kwargs)
    return [error.code for error in errors]


@pytest.mark.parametrize(("name", "expected"), CASES)
def test_each_story_is_rejected_for_exactly_one_reason(name: str, expected: str) -> None:
    found = codes(name)

    assert set(found) == {expected}
    assert len(found) == 1


def test_the_json_field_is_ignored_but_cli_consent_passes() -> None:
    """V5 只认命令行: 同一个故事, 传了 --allow-sensitive 才通过。"""
    name = "10-sensitive-without-consent.json"
    assert story_payload(name)["allow_sensitive"] is True

    assert codes(name) == ["SENSITIVE_REQUIRES_CONSENT"]
    assert codes(name, allow_sensitive=True) == []


def test_every_fixture_explains_itself() -> None:
    """`//` 不是合法 JSON; 顶层 `_comment` 是它的替身。"""
    for name, _ in CASES:
        assert story_payload(name)["_comment"].strip()


def test_the_matrix_is_complete() -> None:
    files = {path.name for path in ADVERSARIAL.glob("*.json")} - {"insights.json"}

    assert files == {name for name, _ in CASES}
    assert len(files) == 12
