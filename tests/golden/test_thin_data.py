"""薄数据闸门: 4 条事件、1 个活跃日, 只能出一条 vol.total。

这个用例锁死 4a 的修复。没有闸门时, "单日 4 条、占比 100%" 会以 +0.900 排第一:
concentration 恒为 0.40, discontinuity 靠 "只有一天" 必中 record 再拿 0.50 ——
两个分量都在奖励"数据少"。
"""

import sqlite3
from datetime import datetime, timedelta, timezone

from recapkits.db import Event, insert_events
from recapkits.emit import render
from recapkits.insights import engine
from recapkits.tz import rebuild_local, to_utc_iso

TZ = "Asia/Shanghai"
YEAR = 2024
EAST_EIGHT = timezone(timedelta(hours=8))


def seed(conn: sqlite3.Connection) -> None:
    """同一个晚上 4 条 commit。"""
    base = datetime(2024, 3, 11, 22, 0, tzinfo=EAST_EIGHT)
    events = [
        Event(
            source="git",
            kind="commit",
            ts_utc=to_utc_iso(base + timedelta(minutes=7 * index)),
            tz_offset_min=480,
            title=f"commit {index}",
            subtitle="alpha",
            value=1.0,
            row_hash=f"{index:016x}",
        )
        for index in range(4)
    ]
    insert_events(conn, events)
    rebuild_local(conn, TZ)


def test_thin_corpus_keeps_only_volume(conn: sqlite3.Connection) -> None:
    """数据不足时只留一条体量洞察, 且两个分量都被明确关闭。"""
    seed(conn)

    found = engine.run(conn, tz=TZ, year=YEAR)

    assert [insight.kind for insight in found] == ["vol.total"]
    assert found[0].data_sufficiency == "insufficient"
    assert found[0].gated == ["concentration", "discontinuity"]
    assert found[0].score == -0.45
    assert found[0].score_parts["concentration"] == 0.0
    assert found[0].score_parts["discontinuity"] == 0.0
    assert any("数据量不足" in caveat for caveat in found[0].caveats)


def test_thin_payload_exposes_gates(conn: sqlite3.Connection) -> None:
    """insights.json 里必须能看到充足度与被关闭的分量。"""
    seed(conn)

    payload = render(engine.run(conn, tz=TZ, year=YEAR), sources=["git"], event_count=4, tz=TZ)
    insight = payload["insights"][0]

    assert insight["data_sufficiency"] == "insufficient"
    assert insight["gated"] == ["concentration", "discontinuity"]
    assert insight["score"] == -0.45
