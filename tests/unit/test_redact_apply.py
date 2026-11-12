"""数据层脱敏: id 与占位符同步重写, 两份 JSON 一致, 原文件不动。"""

import json
import re
from pathlib import Path

import pytest

from recapkits.errors import RecapError
from recapkits.redact import pii
from recapkits.redact.apply import check_resolvable, redact_pair, write_pair
from recapkits.redact.pseudonym import Book
from recapkits.redact.text import read_words
from recapkits.story.schema import Story
from recapkits.story.validate import build_refs, validate_story

FIXTURES = Path(__file__).parent.parent / "fixtures"
FIXED = "0123456789abcdef" * 2
ALPHA = "conc.top_entity:repo:alpha:2024"


def pair() -> tuple[dict, dict]:
    """insights 与一份真的引用了实体名的故事; 每次重新读, 避免测试之间互相污染。"""
    insights = json.loads((FIXTURES / "insights.json").read_text(encoding="utf-8"))
    story = json.loads((FIXTURES / "story-render.json").read_text(encoding="utf-8"))
    return insights, story


def dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def test_original_entity_names_disappear() -> None:
    insights, story = pair()

    result = redact_pair(insights, story, book=Book(salt=FIXED), words=[])

    text = dump(result.insights) + dump(result.story)
    assert "alpha" not in text
    assert "health" not in text
    assert result.id_map == {
        ALPHA: result.insights["insights"][1]["id"],
        "conc.top_entity:repo:health:2024": result.insights["insights"][2]["id"],
    }


def test_ids_and_placeholders_move_together() -> None:
    insights, story = pair()

    result = redact_pair(insights, story, book=Book(salt=FIXED), words=[])

    new_alpha = result.id_map[ALPHA]
    assert new_alpha.startswith("conc.top_entity:repo:%")
    assert re.fullmatch(r"[a-z0-9_.:%-]+", new_alpha)
    ranking = result.story["cards"][2]
    assert ranking["insight"] == new_alpha
    assert f"{{{{{new_alpha}." in ranking["copy"]["sub"]
    assert ALPHA not in dump(result.story)


def test_redacted_pair_passes_the_full_validator() -> None:
    """脱敏后仍要能过 `story --check`, 否则用户拿到的是两份互相矛盾的文件。"""
    insights, story = pair()

    result = redact_pair(insights, story, book=Book(salt=FIXED), words=[])

    errors = validate_story(
        Story.from_dict(result.story), build_refs(result.insights), allow_sensitive=False
    )
    assert errors == []


def test_copy_text_is_rewritten_too() -> None:
    """V6 允许文案里出现实体名, 所以 copy 里的名字也必须跟着换。"""
    insights, story = pair()

    result = redact_pair(insights, story, book=Book(salt=FIXED), words=[])

    sub = result.story["cards"][2]["copy"]["sub"]
    assert sub.endswith(result.insights["insights"][1]["facts"][0]["label"])


def test_suppression_list_removes_the_entity_entirely() -> None:
    insights, story = pair()

    result = redact_pair(insights, story, book=Book(salt=FIXED), words=["alpha"])

    assert result.audit.removed == ["alpha"]
    assert result.audit.pseudonyms == 1
    # 两处命中: 实体标题一次, 故事文案里的 "alpha" 又一次; 审计按出现次数计。
    assert result.audit.suppressed == {"alpha": 2}
    new_alpha = result.insights["insights"][1]["id"]
    assert "alpha" not in new_alpha
    assert result.insights["insights"][1]["facts"][0]["label"] == pii.REMOVED
    assert "alpha" not in dump(result.story)


def test_longest_suppression_word_wins() -> None:
    """「张三丰」不能被「张三」先吃掉, 否则会剩下「丰的作品」。"""
    insights, story = pair()
    insights["insights"][0]["facts"][1]["label"] = "张三丰的作品"

    result = redact_pair(insights, story, book=Book(salt=FIXED), words=["张三", "张三丰"])

    assert result.insights["insights"][0]["facts"][1]["label"] == pii.REMOVED + "的作品"


def test_pii_is_removed_from_copy_and_counted() -> None:
    insights, story = pair()
    story["cards"][0]["copy"]["kicker"] = "联系 alice@example.com"

    result = redact_pair(insights, story, book=Book(salt=FIXED), words=[])

    assert result.story["cards"][0]["copy"]["kicker"] == "联系 " + pii.REMOVED
    assert result.audit.pii_counts == {"邮箱": 1}
    assert result.audit.pii_samples == {"邮箱": ["alice@example.com"]}


def test_entity_names_are_not_replaced_inside_placeholders() -> None:
    """占位符是数据坐标: 先换 id, 再只处理占位符之外的文字。"""
    insights, story = pair()
    story["cards"][2]["copy"]["kicker"] = "{{" + ALPHA + ".share}} alpha"

    result = redact_pair(insights, story, book=Book(salt=FIXED), words=[])

    kicker = result.story["cards"][2]["copy"]["kicker"]
    assert "{{" + result.id_map[ALPHA] + ".share}}" in kicker
    assert kicker.endswith(" " + result.insights["insights"][1]["facts"][0]["label"])


def test_two_runs_write_identical_bytes(tmp_path: Path) -> None:
    book = Book(salt=FIXED)
    first_insights, first_story = pair()
    first = redact_pair(first_insights, first_story, book=book, words=[])
    first_paths = write_pair(tmp_path / "one", first.insights, first.story)

    second_insights, second_story = pair()
    second = redact_pair(second_insights, second_story, book=book, words=[])
    second_paths = write_pair(tmp_path / "two", second.insights, second.story)

    assert [path.read_bytes() for path in first_paths] == [
        path.read_bytes() for path in second_paths
    ]
    assert not list((tmp_path / "one").glob("*.tmp"))


def test_source_files_are_never_written() -> None:
    before = {
        name: (FIXTURES / name).read_bytes() for name in ("insights.json", "story-render.json")
    }

    insights, story = pair()
    redact_pair(insights, story, book=Book(salt=FIXED), words=[])

    after = {
        name: (FIXTURES / name).read_bytes() for name in ("insights.json", "story-render.json")
    }
    assert before == after


def test_check_resolvable_rejects_a_dangling_reference() -> None:
    insights, story = pair()
    story["cards"][1]["insight"] = "vol.total:git:1999"

    with pytest.raises(RecapError):
        check_resolvable(insights, story)


def test_two_suppressed_entities_cannot_collapse_into_one_id() -> None:
    """两个实体都被整体移除时, id 段会撞车; 宁可失败也不让一条洞察凭空消失。"""
    insights, story = pair()

    with pytest.raises(RecapError):
        redact_pair(insights, story, book=Book(salt=FIXED), words=["alpha", "health"])


def test_read_words_ignores_comments_blank_lines_and_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "redact.txt"
    path.write_text("\ufeff# 注释\n\n alpha \nALPHA\nbeta\n", encoding="utf-8")

    assert read_words(path) == ["alpha", "beta"]


def test_missing_suppression_file_is_empty(tmp_path: Path) -> None:
    assert read_words(tmp_path / "nope.txt") == []
