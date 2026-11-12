"""洞察 id 必须能被 story 引用: 用户提供的实体名先转义再进 id。

中文仓库名、大写字母、空格、点号都会让 id 落在 V1 的字符集之外 —— 那样的洞察能算出来、
能出现在 insights.md 里, 却**永远无法被任何 story 引用**。这条测试守的是"数据能进,
故事能引"这条链路, 不是某个正则。
"""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from recapkits.db import Event, insert_events
from recapkits.emit import render
from recapkits.insights import engine
from recapkits.insights.detectors import generic
from recapkits.story.refs import build_refs
from recapkits.story.schema import Story
from recapkits.story.validate import STRICT_PLACEHOLDER, validate_story
from recapkits.tz import rebuild_local, to_utc_iso

TZ = "Asia/Shanghai"
YEAR = 2024
EAST_EIGHT = timezone(timedelta(hours=8))
ENTITY = "龘 Repo.v2"


def seed(conn: sqlite3.Connection, entity: str, *, source: str = "git") -> None:
    """3 个活跃日 x 20 条, 刚好越过集中度检测器的 50 条门槛。"""
    kind = "commit" if source == "git" else "play"
    offset = 480 if source == "git" else None
    events = [
        Event(
            source=source,
            kind=kind,
            ts_utc=to_utc_iso(datetime(2024, 3, 10 + day, 9 + index % 10, tzinfo=EAST_EIGHT)),
            tz_offset_min=offset,
            title="记录",
            subtitle=entity,
            value=1.0,
            row_hash=f"{source}{day * 20 + index:012x}",
        )
        for day in range(3)
        for index in range(20)
    ]
    insert_events(conn, events)
    rebuild_local(conn, TZ)


def payload_of(conn: sqlite3.Connection, source: str = "git") -> dict:
    selected = engine.select(engine.run(conn, tz=TZ, year=YEAR), top=10)
    return render(selected, sources=[source], event_count=60, tz=TZ)


def test_entity_names_are_escaped_into_ids(conn: sqlite3.Connection) -> None:
    """id 是标识: 中文/大写/空格/点号都按字节转义; label 仍是原名。"""
    seed(conn, ENTITY)

    found = engine.run(conn, tz=TZ, year=YEAR)
    conc = next(item for item in found if item.kind == "conc.top_entity")

    assert STRICT_PLACEHOLDER.match(conc.id), conc.id
    assert "龘" not in conc.id and " " not in conc.id and "%2e" in conc.id
    assert any(fact.label == ENTITY for fact in conc.facts)


def ranking_story(insight_id: str) -> dict:
    """一张引用给定洞察的 ranking 卡; 用来验证 id 真的能被 V1 接受。"""
    return {
        "version": 1,
        "meta": {
            "year": YEAR,
            "locale": "zh-CN",
            "theme": "neon",
            "tone": "deadpan",
            "tz": TZ,
            "build_id": "",
        },
        "cards": [
            {
                "id": "ranking",
                "type": "ranking",
                "insight": insight_id,
                "copy": {
                    "headline": "出现最多的项目",
                    "sub": "首位占 {{" + insight_id + ".share}}",
                },
            }
        ],
    }


def test_story_can_reference_the_escaped_id(conn: sqlite3.Connection) -> None:
    """端到端: 这条洞察能被 ranking 卡引用并通过 V1-V7。"""
    seed(conn, ENTITY)
    payload = payload_of(conn)
    conc = next(item for item in payload["insights"] if item["kind"] == "conc.top_entity")
    story = ranking_story(str(conc["id"]))

    errors = validate_story(Story.from_dict(story), build_refs(payload))

    assert errors == []


def test_spotify_artist_ids_are_referenceable(conn: sqlite3.Connection) -> None:
    """艺人名里的生僻字同样要被转义, 并且转义后的 id 仍能被故事引用。"""
    seed(conn, ENTITY, source="spotify")
    payload = payload_of(conn, source="spotify")
    conc = next(item for item in payload["insights"] if item["kind"] == "conc.top_entity")

    assert str(conc["id"]).startswith("conc.top_entity:artist:")
    assert STRICT_PLACEHOLDER.match(str(conc["id"]))
    errors = validate_story(Story.from_dict(ranking_story(str(conc["id"]))), build_refs(payload))

    assert errors == []


def test_ids_are_stable_across_runs(conn: sqlite3.Connection) -> None:
    """同一条数据两次算出的 id 必须相同, 否则 story 引用会随机失效。"""
    seed(conn, ENTITY)

    first = [item.id for item in engine.run(conn, tz=TZ, year=YEAR)]
    second = [item.id for item in engine.run(conn, tz=TZ, year=YEAR)]

    assert first == second


def test_escape_keeps_plain_names_untouched() -> None:
    """小写 ASCII 名一个字节都不变: 已有 id 与快照因此不受影响。"""
    assert generic._escape_entity("recapkits-2024_v2") == "recapkits-2024_v2"


@pytest.mark.parametrize(
    ("left", "right"),
    [("A", "a"), ("龘", "龘2"), ("a%41", "A"), ("x y", "x%20y"), ("a.b", "a-b")],
)
def test_escape_is_injective(left: str, right: str) -> None:
    """两个不同的实体名不能撞成同一个 id; 转义字符本身也要被转义。"""
    escaped_left = generic._escape_entity(left)
    escaped_right = generic._escape_entity(right)

    assert escaped_left != escaped_right
    assert STRICT_PLACEHOLDER.match(escaped_left)
    assert STRICT_PLACEHOLDER.match(escaped_right)
