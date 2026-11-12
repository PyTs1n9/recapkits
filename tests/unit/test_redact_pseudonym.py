"""假名: 稳定、无碰撞、序号不带数字; 盐丢了就重排。"""

import json
from pathlib import Path

import pytest

from recapkits.redact.pseudonym import Book, PseudonymError, load, new_salt, save, stem

FIXED = "0123456789abcdef" * 2


def test_same_salt_and_name_get_the_same_pseudonym() -> None:
    first = Book(salt=FIXED)
    second = Book(salt=FIXED)

    first.assign({"alpha": "repo"})
    second.assign({"alpha": "repo"})

    assert first.map["alpha"] == second.map["alpha"] == "项目甲"


def test_prefixes_follow_entity_kinds() -> None:
    book = Book(salt=FIXED)

    book.assign({"r": "repo", "a": "artist", "s": "show", "x": "other"})

    prefixes = {name: value[:2] for name, value in book.map.items()}
    assert prefixes == {"r": "项目", "a": "艺人", "s": "剧集", "x": "实体"}


def test_fifty_entities_get_fifty_distinct_names_without_digits() -> None:
    book = Book(salt=FIXED)

    book.assign({f"name-{index}": "repo" for index in range(50)})

    values = list(book.map.values())
    assert len(set(values)) == 50
    assert all(not any(char.isdigit() for char in value) for value in values)


def test_stem_is_unique_and_digit_free_beyond_ten() -> None:
    labels = [stem(index) for index in range(100)]

    assert labels[0] == "甲"
    assert labels[9] == "癸"
    assert labels[10] == "甲甲"
    assert labels[19] == "甲癸"
    assert labels[20] == "乙甲"
    assert len(set(labels)) == 100
    assert all(not any(char.isdigit() for char in label) for label in labels)


def test_existing_mapping_survives_a_larger_run() -> None:
    """第二次多看到一个实体, 前两个的名字不能变 —— 这是"两次产物可比"的前提。"""
    first = Book(salt=FIXED)
    first.assign({"a": "repo", "b": "repo"})
    before = dict(first.map)

    second = Book(salt=first.salt, map=dict(first.map))
    second.assign({"c": "repo", "a": "repo", "b": "repo"})

    assert {name: second.map[name] for name in before} == before
    assert second.map["c"] not in before.values()


def test_order_is_not_the_lexical_order() -> None:
    """按原名排序会泄露字典序; HMAC 排序键必须把它打乱。"""
    names = [f"repo-{index:02d}" for index in range(20)]
    book = Book(salt=FIXED)

    book.assign({name: "repo" for name in names})

    lexical = sorted(names)
    expected = {name: "项目" + stem(index) for index, name in enumerate(lexical)}
    assert book.map != expected


def test_a_different_salt_reshuffles_names() -> None:
    names = [f"repo-{index:02d}" for index in range(20)]
    first = Book(salt=FIXED)
    second = Book(salt="fedcba9876543210" * 2)

    first.assign({name: "repo" for name in names})
    second.assign({name: "repo" for name in names})

    assert first.map != second.map


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "redactions.json"
    book = Book(salt=FIXED)
    book.assign({"alpha": "repo"})

    save(path, book)
    restored = load(path)

    assert restored == book
    assert json.loads(path.read_text(encoding="utf-8"))["salt"] == FIXED


def test_missing_file_is_not_an_error(tmp_path: Path) -> None:
    assert load(tmp_path / "nope.json") is None


@pytest.mark.parametrize(
    "payload",
    [
        {"salt": "abc", "map": {}},
        {"salt": FIXED, "map": {"a": 1}},
        {"salt": FIXED},
        [],
    ],
)
def test_broken_mapping_file_is_rejected(tmp_path: Path, payload: object) -> None:
    path = tmp_path / "redactions.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PseudonymError):
        load(path)


def test_new_salt_is_hex_and_random() -> None:
    first = new_salt()
    second = new_salt()

    assert len(first) == 32
    assert first != second
    assert int(first, 16) >= 0
