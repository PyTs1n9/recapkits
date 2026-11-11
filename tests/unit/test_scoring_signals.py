"""打分二期的回归锁: signal 锚点、单调性、闸门语义与不变量。

这个文件存在的理由只有一个: 一期公式让 `time.*` 恒为 0, 而且那种"恒为 0"是结构性的
—— 它们没有 top1_share、没有 novelty=record、没有上一期, 于是六个分量全部归零。
下面第一条测试就是防止这种退化再次发生。
"""

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


def seed(conn, days: Iterable[int], *, hours: Iterable[int] = (2,), per_day: int = 1) -> None:
    """在 2024-01-01 起的指定天偏移上播种事件; 小时集合循环取用。"""
    base = datetime(2024, 1, 1, tzinfo=UTC)
    hour_list = list(hours)
    events = []
    for day in days:
        for slot in range(per_day):
            hour = hour_list[slot % len(hour_list)]
            moment = base + timedelta(days=day, hours=hour - 8)  # 本地小时 = hour
            events.append(
                Event(
                    source="git",
                    kind="commit",
                    ts_utc=to_utc_iso(moment),
                    tz_offset_min=480,
                    title=f"c{day}-{slot}",
                    subtitle="alpha",
                    value=1.0,
                    row_hash=f"{day:04d}{slot:04d}{hour:02d}0000",
                )
            )
    insert_events(conn, events)
    rebuild_local(conn, TZ)


def by_kind(conn) -> dict:
    """一次跑完引擎, 按 kind 取洞察。"""
    return {item.kind: item for item in engine.run(conn, tz=TZ, year=YEAR)}


def test_time_kinds_no_longer_score_zero(conn) -> None:
    """回归锁: 深夜占比与星期偏向必须真的把分数抬起来。

    两个检测器分开造语料, 因为它们的 signal 来自不同事实: 一个看小时分布,
    一个看星期分布。任意一个重新变成恒 0, 这条测试就会失败。
    """
    seed(conn, range(40), hours=(2,))
    hour = by_kind(conn)["time.hour_rhythm"]

    assert hour.signal == pytest.approx(1.0)
    assert hour.score == pytest.approx(1.0)
    assert hour.score > 0.0


def test_weekday_rhythm_scores_when_a_weekday_dominates(conn) -> None:
    """全部事件落在周一: 最活跃星期占比 100%, signal 满格。"""
    seed(conn, [index * 7 for index in range(30)], hours=(10,))
    weekday = by_kind(conn)["time.weekday_rhythm"]

    assert weekday.signal == pytest.approx(1.0)
    assert weekday.score == pytest.approx(1.0)


def test_score_equals_sum_of_parts_for_every_candidate(conn) -> None:
    """不变量: score 恒等于 score_parts 之和, 对全部候选逐条断言。"""
    seed(conn, list(range(20)) + list(range(30, 50)), hours=(2, 14), per_day=2)

    candidates = engine.run(conn, tz=TZ, year=YEAR)

    assert {item.kind for item in candidates} == FULL_KINDS
    for insight in candidates:
        assert sum(insight.score_parts.values()) == pytest.approx(insight.score, abs=1e-9)
        assert set(insight.score_parts) == {"signal", "deviation", "discontinuity", "sensitivity"}


def test_busiest_day_signal_is_zero_at_one_point_two_six_times_average(conn) -> None:
    """峰值 = 1.26x 日均时没有信号: 1.5x 才是起点, 恒真的"每年都有一个最忙的日子"不该拿分。"""
    daily_avg = 100.0
    peak = round(1.26 * daily_avg)

    assert scoring.signal_busiest_day(peak, daily_avg) == 0.0
    assert scoring.signal_busiest_day(150, daily_avg) == 0.0
    assert scoring.signal_busiest_day(1000, daily_avg) == 1.0
    assert 0.0 < scoring.signal_busiest_day(500, daily_avg) < 1.0


@pytest.mark.parametrize(("days", "expected"), [(10, 0.1667), (30, 0.5), (60, 1.0)])
def test_streak_signal_is_monotonic(days: int, expected: float) -> None:
    """连续天数 10 -> 30 -> 60, signal 严格递增, 60 天封顶。"""
    assert scoring.signal_streak(days) == pytest.approx(expected, abs=1e-4)


def test_streak_signal_strictly_increases() -> None:
    """单调性的方向不能反: 天数越多, signal 只会更大。"""
    values = [scoring.signal_streak(days) for days in (10, 30, 60)]

    assert values == sorted(values)
    assert len(set(values)) == 3


def test_no_previous_period_gates_both_comparison_components() -> None:
    """没有上一期时, deviation 与 discontinuity 都必须被明确关闭。"""
    assert scoring.gated_components(has_previous=False) == ["deviation", "discontinuity"]
    assert scoring.gated_components(has_previous=True) == []

    parts = scoring.score_parts(
        signal=1.0,
        novelty="record",
        sensitivity="low",
        gated=scoring.gated_components(has_previous=False),
    )

    assert parts["deviation"] == 0.0
    assert parts["discontinuity"] == 0.0
    assert parts["signal"] == 1.0


def test_deviation_uses_robust_z_when_previous_exists() -> None:
    """有上一期时 deviation 才真的算: |z|/3 封顶, 并为阶段 6 留好接口。"""
    parts = scoring.score_parts(
        signal=0.0,
        novelty="shift",
        sensitivity="low",
        deviation_z=-1.5,
        gated=scoring.gated_components(has_previous=True),
    )

    assert parts["deviation"] == pytest.approx(0.2)
    assert parts["discontinuity"] == pytest.approx(0.15)
    assert scoring.total(parts) == pytest.approx(0.35)


def test_every_detector_reports_signal_in_unit_interval(conn) -> None:
    """遍历全部检测器: signal 必须落在 [0, 1], 且与已加权分量一致。"""
    seed(conn, list(range(20)) + list(range(30, 50)), hours=(2, 14), per_day=2)

    candidates = engine.run(conn, tz=TZ, year=YEAR)

    assert {item.kind for item in candidates} == FULL_KINDS
    for insight in candidates:
        assert 0.0 <= insight.signal <= 1.0, insight.id
        assert insight.score_parts["signal"] == pytest.approx(insight.signal, abs=1e-4)


def test_high_sensitivity_still_subtracts_a_full_point() -> None:
    """高敏惩罚维持 1.00 的权重, 不受公式换血影响。"""
    parts = scoring.score_parts(signal=0.6, novelty="constant", sensitivity="high")

    assert parts["sensitivity"] == -1.0
    assert scoring.total(parts) == pytest.approx(-0.4)
