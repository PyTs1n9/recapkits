"""restore: 读表、换 id、换名、长名优先、未知项不动。

还原只做两件事, 所以这里也只测这两件事 —— 任何"顺手多还原一点"的扩展都会让
`.recapkits/agent/restore.json` 从数据变成另一种脱敏产物。
"""

import json
from pathlib import Path

import pytest

from recapkits.errors import RecapError
from recapkits.redact.restore import Restore, apply, build, load

SALT = "0123456789abcdef" * 2
REAL_ID = "conc.top_entity:repo:alpha:2024"
FAKE_ID = "conc.top_entity:repo:%e9%a1%b9%e7%9b%ae%e7%94%b2:2024"


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "restore.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _payload(**overrides: object) -> dict:
    payload: dict[str, object] = {
        "version": 1,
        "salt": SALT,
        "ids": {FAKE_ID: REAL_ID},
        "names": {"项目甲": "alpha"},
    }
    payload.update(overrides)
    return payload


def test_loads_a_valid_table(tmp_path: Path) -> None:
    table = load(_write(tmp_path, _payload()))

    assert table.salt == SALT
    assert table.ids == {FAKE_ID: REAL_ID}
    assert table.names == {"项目甲": "alpha"}


def test_a_missing_table_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(RecapError, match="不存在"):
        load(tmp_path / "missing.json")


def test_a_broken_table_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "restore.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(RecapError, match="不是合法 JSON"):
        load(path)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"version": 2}, "version"),
        ({"salt": "abc"}, "salt"),
        ({"ids": []}, "ids"),
        ({"names": {"项目甲": 1}}, "names"),
    ],
)
def test_a_wrong_field_is_rejected(tmp_path: Path, overrides: dict, message: str) -> None:
    with pytest.raises(RecapError, match=message):
        load(_write(tmp_path, _payload(**overrides)))


def test_ids_and_evidence_are_restored() -> None:
    payload = {
        "cards": [
            {"id": "c3", "insight": FAKE_ID, "evidence": [FAKE_ID, "vol.total:git:2024"]},
        ]
    }

    restored = apply(payload, Restore(salt=SALT, ids={FAKE_ID: REAL_ID}, names={}))

    assert restored["cards"][0]["insight"] == REAL_ID
    assert restored["cards"][0]["evidence"] == [REAL_ID, "vol.total:git:2024"]


def test_placeholders_are_restored() -> None:
    payload = {"cards": [{"copy": {"sub": "指向 {{" + FAKE_ID + ".rank_1}} 的提交"}}]}

    restored = apply(payload, Restore(salt=SALT, ids={FAKE_ID: REAL_ID}, names={}))

    assert restored["cards"][0]["copy"]["sub"] == "指向 {{" + REAL_ID + ".rank_1}} 的提交"


def test_names_are_restored_outside_placeholders() -> None:
    payload = {"cards": [{"copy": {"headline": "项目甲", "kicker": "项目甲 · 未上传"}}]}

    restored = apply(payload, Restore(salt=SALT, ids={}, names={"项目甲": "alpha"}))

    assert restored["cards"][0]["copy"] == {"headline": "alpha", "kicker": "alpha · 未上传"}


def test_longer_names_win() -> None:
    """`项目甲甲` 与 `项目甲` 同时存在时, 短名先换会留下 `alpha甲`。"""
    payload = {"cards": [{"copy": {"sub": "项目甲甲"}}]}
    table = Restore(salt=SALT, ids={}, names={"项目甲": "alpha", "项目甲甲": "beta"})

    restored = apply(payload, table)

    assert restored["cards"][0]["copy"]["sub"] == "beta"


def test_unknown_ids_and_names_are_left_alone() -> None:
    """agent 编的拉丁词要留给校验器报 NAME_NOT_IN_EVIDENCE, 并指出那个词。"""
    payload = {"cards": [{"insight": "conc.made_up:2024", "copy": {"sub": "艺人乙"}}]}

    restored = apply(payload, Restore(salt=SALT, ids={}, names={"项目甲": "alpha"}))

    assert restored["cards"][0]["insight"] == "conc.made_up:2024"
    assert restored["cards"][0]["copy"]["sub"] == "艺人乙"


def test_apply_does_not_touch_the_input() -> None:
    payload = {"cards": [{"insight": FAKE_ID, "copy": {"sub": "项目甲"}}]}
    snapshot = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    table = Restore(salt=SALT, ids={FAKE_ID: REAL_ID}, names={"项目甲": "alpha"})

    apply(payload, table)

    assert json.dumps(payload, ensure_ascii=False, sort_keys=True) == snapshot


def test_build_sorts_the_maps_for_a_stable_file() -> None:
    payload = build(
        salt=SALT,
        ids={"b": "1", "a": "2"},
        names={"艺人乙": "B", "艺人甲": "A"},
    )

    assert list(payload["ids"]) == ["a", "b"]
    assert list(payload["names"]) == ["艺人乙", "艺人甲"]


def test_build_output_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "agent" / "restore.json"
    path.parent.mkdir()
    text = json.dumps(build(salt=SALT, ids={FAKE_ID: REAL_ID}, names={"项目甲": "alpha"}))
    path.write_bytes((text + "\n").encode("utf-8"))

    table = load(path)

    assert table.ids == {FAKE_ID: REAL_ID}
    assert table.names == {"项目甲": "alpha"}
