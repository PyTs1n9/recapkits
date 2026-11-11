"""黄金语料: 220 条事件、46 个活跃日, 7 个检测器全部出结果。

语料直接构造成 `events` 行, 不经过 git 适配器 —— 适配器有自己的测试,
这里要测的是洞察与打分。所有时间戳硬编码, 不依赖"今天", 因此快照跨平台稳定。

语料的形状是写死的: 03-10..03-16 是唯一 7 天空档, 05-01..05-21 是 21 天连续,
alpha 占 62%, 深夜 38%, 周末 12%。
"""

import json
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from recapkits.db import Event, count_events, insert_events
from recapkits.emit import render
from recapkits.insights import engine
from recapkits.tz import rebuild_local, to_utc_iso

TZ = "Asia/Shanghai"
YEAR = 2024
SNAPSHOT = Path(__file__).parent / "snapshots" / "corpus_2024.insights.json"

#: 七段活跃区间, 合起来 46 天。
BLOCKS = (
    ("2024-03-09", 1),
    ("2024-03-17", 5),
    ("2024-03-25", 4),
    ("2024-04-02", 4),
    ("2024-04-11", 5),
    ("2024-04-19", 6),
    ("2024-05-01", 21),
)

TOTAL_EVENTS = 220
ALPHA_EVENTS = 137
LATE_NIGHT_EVENTS = 84
LATE_HOURS = (22, 23, 0, 1, 2, 3)
DAY_HOURS = (9, 10, 11, 13, 14, 15, 16, 17)
REPOS = ("beta", "gamma", "delta", "epsilon")
EAST_EIGHT = timezone(timedelta(hours=8))
FULL_KINDS = {
    "vol.total",
    "vol.busiest_day",
    "conc.top_entity",
    "time.hour_rhythm",
    "time.weekday_rhythm",
    "disc.longest_streak",
    "disc.longest_gap",
}


def _bresenham(total: int, hits: int) -> list[bool]:
    """把 hits 个 True 均匀撒进 total 个位置, 数量精确。"""
    flags: list[bool] = []
    acc = 0
    for _ in range(total):
        acc += hits
        if acc >= total:
            acc -= total
            flags.append(True)
        else:
            flags.append(False)
    return flags


def active_days() -> list[date]:
    """46 个活跃本地日期, 升序。"""
    days: list[date] = []
    for start, length in BLOCKS:
        first = date.fromisoformat(start)
        days.extend(first + timedelta(days=offset) for offset in range(length))
    return days


def _quota(days: list[date]) -> list[int]:
    """每个活跃日的事件数: 周中 6/5 条, 周末 3/2 条, 合计 220。"""
    weekdays = [day for day in days if day.weekday() < 5]
    weekends = [day for day in days if day.weekday() >= 5]
    quota = {day: 6 if index < 24 else 5 for index, day in enumerate(weekdays)}
    quota.update({day: 3 if index < 2 else 2 for index, day in enumerate(weekends)})
    return [quota[day] for day in days]


def build_events() -> list[Event]:
    """按固定规则构造 220 条 commit 事件。"""
    days = active_days()
    slots = [
        (day, index)
        for day, quota in zip(days, _quota(days), strict=True)
        for index in range(quota)
    ]
    if len(slots) != TOTAL_EVENTS:
        raise AssertionError(f"语料事件数应为 {TOTAL_EVENTS}, 实际 {len(slots)}")

    late_flags = _bresenham(TOTAL_EVENTS, LATE_NIGHT_EVENTS)
    alpha_flags = _bresenham(TOTAL_EVENTS, ALPHA_EVENTS)
    late_seen = day_seen = other_seen = 0
    events: list[Event] = []

    for position, (day, index) in enumerate(slots):
        if late_flags[position]:
            hour = LATE_HOURS[late_seen % len(LATE_HOURS)]
            late_seen += 1
        else:
            hour = DAY_HOURS[day_seen % len(DAY_HOURS)]
            day_seen += 1

        if alpha_flags[position]:
            repo = "alpha"
        else:
            repo = REPOS[other_seen % len(REPOS)]
            other_seen += 1

        local = datetime(day.year, day.month, day.day, hour, index * 11 % 60, tzinfo=EAST_EIGHT)
        events.append(
            Event(
                source="git",
                kind="commit",
                ts_utc=to_utc_iso(local),
                tz_offset_min=480,
                title=f"commit {position:03d}",
                subtitle=repo,
                value=1.0,
                row_hash=f"{position:016x}",
            )
        )
    return events


@pytest.fixture
def corpus(conn: sqlite3.Connection) -> sqlite3.Connection:
    """220 条事件 + 已重建的本地日派生表。"""
    inserted = insert_events(conn, build_events())
    assert inserted == TOTAL_EVENTS
    rebuild_local(conn, TZ)
    return conn


def payload_of(conn: sqlite3.Connection, top: int = 10) -> dict[str, object]:
    """跑一遍引擎并渲染成 insights.json 的结构。"""
    selected = engine.select(engine.run(conn, tz=TZ, year=YEAR), top=top)
    return render(selected, sources=["git"], event_count=count_events(conn), tz=TZ)


def test_all_seven_kinds_appear(corpus: sqlite3.Connection) -> None:
    """样本量够, 7 个 kind 一个不少。"""
    found = engine.run(corpus, tz=TZ, year=YEAR)

    assert {insight.kind for insight in found} == FULL_KINDS


def test_sufficiency_is_ok_and_nothing_gated(corpus: sqlite3.Connection) -> None:
    """46 个活跃日 / 220 条事件: 充足度 ok, 没有分量被闸门关闭。"""
    for insight in engine.run(corpus, tz=TZ, year=YEAR):
        assert insight.data_sufficiency == "ok"
        assert insight.gated == []


def test_streak_and_gap_values(corpus: sqlite3.Connection) -> None:
    """最长连续 21 天, 最长空档 7 天, 与语料声明一致。"""
    found = {insight.kind: insight for insight in engine.run(corpus, tz=TZ, year=YEAR)}

    assert found["disc.longest_streak"].headline_fact.value == 21
    assert found["disc.longest_gap"].headline_fact.value == 7
    assert found["disc.longest_gap"].novelty == "absence"


def test_corpus_shape_matches_declaration(corpus: sqlite3.Connection) -> None:
    """语料自检: alpha 62%, 深夜 38%, 周末 12%。"""
    found = {insight.kind: insight for insight in engine.run(corpus, tz=TZ, year=YEAR)}

    assert found["conc.top_entity"].headline_fact.display == "62%"
    assert found["conc.top_entity"].headline_fact.value == pytest.approx(137 / 220, abs=1e-4)

    hour_facts = {fact.key: fact for fact in found["time.hour_rhythm"].facts}
    assert hour_facts["late_night_share"].display == "38%"

    weekday_facts = {fact.key: fact for fact in found["time.weekday_rhythm"].facts}
    weekend = weekday_facts["wd_6"].value + weekday_facts["wd_7"].value
    assert weekend / TOTAL_EVENTS == pytest.approx(0.12, abs=0.005)


def test_three_runs_are_byte_identical(corpus: sqlite3.Connection) -> None:
    """连跑三次, 渲染结果逐字节一致; 排序必须是全序。"""
    runs = [json.dumps(payload_of(corpus), ensure_ascii=False, indent=2) + "\n" for _ in range(3)]

    assert len(set(runs)) == 1


def test_every_evidence_sql_runs(corpus: sqlite3.Connection) -> None:
    """每条 evidence_sql 都能直接执行, 行数与 evidence_rows 一致。"""
    for insight in engine.run(corpus, tz=TZ, year=YEAR):
        rows = corpus.execute(insight.evidence_sql).fetchall()
        assert len(rows) == insight.evidence_rows
        assert rows, insight.id


def test_snapshot_matches(corpus: sqlite3.Connection) -> None:
    """整份 insights.json 与快照逐字节比对。"""
    actual = json.dumps(payload_of(corpus), ensure_ascii=False, indent=2) + "\n"

    if os.environ.get("RECAP_UPDATE_SNAPSHOT") == "1":
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(actual, encoding="utf-8")

    assert actual == SNAPSHOT.read_text(encoding="utf-8")
