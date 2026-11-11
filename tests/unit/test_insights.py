"""检测器门槛、打分分量、选卡全序; 都属于确定性逻辑, 不依赖 git。"""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

import pytest

from recapkits.db import Event, insert_events
from recapkits.insights import engine, scoring
from recapkits.tz import rebuild_local, to_utc_iso

TZ = "Asia/Shanghai"
YEAR = 2024
FULL_KINDS = {
    "vol.total",
    "vol.busiest_day",
    "conc.top_entity",
    "time.hour_rhythm",
    "time.weekday_rhythm",
    "disc.longest_streak",
    "disc.longest_gap",
}


def seed(conn, day_offsets: Iterable[int], per_day: int = 2) -> None:
    """在 2024-01-01 起的指定天偏移上播种事件; 时间与仓库都错开。"""
    base = datetime(2024, 1, 1, tzinfo=UTC)
    events = []
    for day in day_offsets:
        for slot in range(per_day):
            moment = base + timedelta(days=day, hours=(slot * 5) % 24, minutes=slot)
            events.append(
                Event(
                    source="git",
                    kind="commit",
                    ts_utc=to_utc_iso(moment),
                    tz_offset_min=480,
                    title=f"c{day}-{slot}",
                    subtitle=f"repo-{slot % 3}",
                    value=1.0,
                    row_hash=f"{day:04d}{slot:04d}00000000",
                )
            )
    insert_events(conn, events)
    rebuild_local(conn, TZ)


def kinds_of(insights: list) -> set[str]:
    """取 kind 集合, 便于按门槛断言。"""
    return {insight.kind for insight in insights}


def test_thin_data_yields_only_volume(conn) -> None:
    """只有 5 个活跃日、10 条事件: 充足度 insufficient, 只剩一条 vol.total。"""
    seed(conn, range(5))

    found = engine.run(conn, tz=TZ, year=YEAR)

    assert kinds_of(found) == {"vol.total"}
    assert found[0].data_sufficiency == "insufficient"
    assert found[0].gated == ["concentration", "discontinuity"]
    assert any("数据量不足" in caveat for caveat in found[0].caveats)


def test_thin_level_keeps_detectors_but_gates_discontinuity(conn) -> None:
    """20 个活跃日、40 条事件: 充足度 thin, 体量类保留, 但 discontinuity 被关掉。"""
    seed(conn, range(20))

    found = engine.run(conn, tz=TZ, year=YEAR)

    assert kinds_of(found) == {"vol.total", "vol.busiest_day"}
    assert {item.data_sufficiency for item in found} == {"thin"}
    assert {tuple(item.gated) for item in found} == {("discontinuity",)}
    for item in found:
        assert item.score_parts["discontinuity"] == 0.0


def test_forty_active_days_yield_all_seven_kinds(conn) -> None:
    """40 个活跃日、80 条事件, 中间留 10 天空档: 7 个 kind 全部出现。"""
    seed(conn, list(range(20)) + list(range(30, 50)))

    found = engine.run(conn, tz=TZ, year=YEAR)

    assert kinds_of(found) == FULL_KINDS


def test_concentration_respects_fifty_event_floor(conn) -> None:
    """30 个活跃日但只有 30 条事件: 集中度被门槛挡住, 时间与断裂类照常。"""
    seed(conn, range(30), per_day=1)

    found = kinds_of(engine.run(conn, tz=TZ, year=YEAR))

    assert "conc.top_entity" not in found
    assert {"time.hour_rhythm", "time.weekday_rhythm"} <= found


def test_future_year_is_rejected(conn) -> None:
    """尚未开始的年份不给窗口。"""
    with pytest.raises(ValueError, match="尚未开始"):
        engine.build_period(conn, tz=TZ, year=2999, today="2026-11-11")


def test_score_parts_sum_to_score(conn) -> None:
    """score 必须等于六个已加权分量之和, 且老套惩罚落在 vol.total 上。"""
    seed(conn, list(range(20)) + list(range(30, 50)))

    for insight in engine.run(conn, tz=TZ, year=YEAR):
        assert sum(insight.score_parts.values()) == pytest.approx(insight.score)
        assert set(insight.score_parts) == {
            "deviation",
            "rarity",
            "discontinuity",
            "concentration",
            "obviousness",
            "sensitivity",
        }

    parts = scoring.score_parts(
        kind="vol.total", novelty="constant", top1_share=0.0, sensitivity="low"
    )
    assert parts["obviousness"] == -0.45
    assert parts["discontinuity"] == 0.0
    assert scoring.total(parts) == -0.45


def test_absence_scores_higher_than_constant(conn) -> None:
    """没有发生(absence)与首次出现(record)拿满分不连续性, 平稳为 0。"""
    assert scoring.discontinuity("absence") == 1.0
    assert scoring.discontinuity("record") == 1.0
    assert scoring.discontinuity("shift") == 0.5
    assert scoring.discontinuity("constant") == 0.0


def test_select_is_total_order_with_one_per_kind(conn) -> None:
    """选卡: 全序 (score desc, kind, id), 同一 kind 只取 1 个。"""
    seed(conn, list(range(20)) + list(range(30, 50)))
    candidates = engine.run(conn, tz=TZ, year=YEAR)

    picked = engine.select(candidates, top=10)

    keys = [(-item.score, item.kind, item.id) for item in picked]
    assert keys == sorted(keys)
    assert len({item.kind for item in picked}) == len(picked)
    with pytest.raises(ValueError, match="大于 0"):
        engine.select(candidates, top=0)


def test_every_evidence_sql_runs_and_matches_row_count(conn) -> None:
    """evidence_sql 必须能直接执行, 且行数等于 evidence_rows。"""
    seed(conn, list(range(20)) + list(range(30, 50)))

    for insight in engine.run(conn, tz=TZ, year=YEAR):
        rows = conn.execute(insight.evidence_sql).fetchall()
        assert len(rows) == insight.evidence_rows
        assert rows, insight.id


def test_streak_and_gap_are_computed_on_local_dates(conn) -> None:
    """连续 20 天后空 10 天: streak 20 天, gap 10 天。"""
    seed(conn, list(range(20)) + list(range(30, 50)))

    found = {insight.kind: insight for insight in engine.run(conn, tz=TZ, year=YEAR)}

    assert found["disc.longest_streak"].headline_fact.value == 20
    assert found["disc.longest_gap"].headline_fact.value == 10
    assert found["disc.longest_gap"].novelty == "absence"
    gap_start = next(f for f in found["disc.longest_gap"].facts if f.key == "start")
    assert gap_start.display == "2024-01-21"
