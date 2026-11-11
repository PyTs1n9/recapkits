"""db.py 的契约测试: 幂等、派生表重建、导入报告落库。"""

import json
import sqlite3

from recapkits.db import (
    Event,
    count_events,
    init_schema,
    insert_events,
    insert_import_report,
    list_sources,
)
from recapkits.tz import rebuild_local


def make_event(index: int, *, ts_utc: str, offset_min: int | None = 480) -> Event:
    """构造一条可预测的 git 事件, row_hash 为 16 位十六进制。"""
    return Event(
        source="git",
        kind="commit",
        ts_utc=ts_utc,
        tz_offset_min=offset_min,
        title=f"commit {index}",
        subtitle="demo-repo",
        value=1.0,
        row_hash=f"{index:016x}",
    )


def test_same_batch_twice_keeps_count(conn: sqlite3.Connection) -> None:
    """同一批事件插两次, 计数不变, 第二次新增为 0。"""
    events = [
        make_event(1, ts_utc="2026-03-11T15:59:00Z"),
        make_event(2, ts_utc="2026-03-12T01:00:00Z"),
        make_event(3, ts_utc="2026-11-01T05:30:00Z"),
    ]

    assert insert_events(conn, events) == 3
    assert insert_events(conn, events) == 0
    assert count_events(conn) == 3


def test_duplicate_row_hash_does_not_overwrite(conn: sqlite3.Connection) -> None:
    """row_hash 冲突时保留先到的那一行, 不做更新。"""
    first = Event(
        source="git", kind="commit", ts_utc="2026-01-01T00:00:00Z", title="先到", row_hash="a" * 16
    )
    second = Event(
        source="git", kind="commit", ts_utc="2026-01-01T00:00:00Z", title="后到", row_hash="a" * 16
    )

    assert insert_events(conn, [first]) == 1
    assert insert_events(conn, [second]) == 0

    row = conn.execute("SELECT title FROM events").fetchone()
    assert row["title"] == "先到"


def test_rebuild_local_is_repeatable(conn: sqlite3.Connection) -> None:
    """派生表全量重建: 行数正确, 重复重建不产生重复行。"""
    insert_events(
        conn,
        [
            make_event(1, ts_utc="2026-03-11T15:59:00Z"),
            make_event(2, ts_utc="2026-03-11T16:00:00Z"),
        ],
    )

    assert rebuild_local(conn, "Asia/Shanghai") == 2
    assert rebuild_local(conn, "Asia/Shanghai") == 2

    rows = conn.execute(
        "SELECT local_date, local_hour FROM event_local WHERE tz = 'Asia/Shanghai' "
        "ORDER BY local_date, local_hour"
    ).fetchall()
    assert [(r["local_date"], r["local_hour"]) for r in rows] == [
        ("2026-03-11", 23),
        ("2026-03-12", 0),
    ]


def test_rebuild_local_prefers_source_offset(conn: sqlite3.Connection) -> None:
    """源自带 +09:00 时, 即使配置上海时区也按 +09:00 落本地。"""
    insert_events(conn, [make_event(1, ts_utc="2026-01-01T00:00:00Z", offset_min=540)])

    rebuild_local(conn, "Asia/Shanghai")

    row = conn.execute("SELECT local_date, local_hour FROM event_local").fetchone()
    assert (row["local_date"], row["local_hour"]) == ("2026-01-01", 9)


def test_rebuild_local_scopes_to_one_zone(conn: sqlite3.Connection) -> None:
    """重建某个时区不会动另一个时区的切片。"""
    insert_events(conn, [make_event(1, ts_utc="2026-01-01T00:00:00Z", offset_min=None)])

    rebuild_local(conn, "Asia/Shanghai")
    rebuild_local(conn, "UTC")
    rebuild_local(conn, "UTC")

    counts = dict(
        (row["tz"], row["n"])
        for row in conn.execute("SELECT tz, COUNT(*) AS n FROM event_local GROUP BY tz")
    )
    assert counts == {"Asia/Shanghai": 1, "UTC": 1}


def test_import_report_is_appended(conn: sqlite3.Connection) -> None:
    """导入报告只追加, 警告以 JSON 数组存。"""
    insert_import_report(
        conn,
        source="git",
        src_hash="deadbeef",
        rows=12,
        skipped=1,
        warnings=["仓库 X 不是 git 仓库"],
        coverage=0.42,
        created_at="2026-11-11T00:00:00Z",
    )

    row = conn.execute("SELECT * FROM import_reports").fetchone()
    assert row["rows"] == 12
    assert row["skipped"] == 1
    assert row["coverage"] == 0.42
    assert json.loads(row["warnings"]) == ["仓库 X 不是 git 仓库"]


def test_init_schema_is_idempotent(conn: sqlite3.Connection) -> None:
    """重复建表不报错, 也不清空数据。"""
    insert_events(conn, [make_event(1, ts_utc="2026-01-01T00:00:00Z")])

    init_schema(conn)

    assert count_events(conn) == 1


def test_list_sources_counts_per_source(conn: sqlite3.Connection) -> None:
    """按源汇总, 供 doctor 与引擎挑源。"""
    insert_events(
        conn,
        [
            make_event(1, ts_utc="2026-01-01T00:00:00Z"),
            make_event(2, ts_utc="2026-01-02T00:00:00Z"),
        ],
    )

    assert list_sources(conn) == [("git", 2)]
    assert count_events(conn, "git") == 2
    assert count_events(conn, "spotify") == 0
