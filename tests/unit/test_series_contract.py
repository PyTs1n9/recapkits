"""series 契约: 长度、键集、share 求和、day 窗口, 以及 emit 的条件写入。

这些约束如果只在检测器里"注意一下", 外部 agent 产出的 insights.json 就会绕过它们;
所以校验必须在 `Series` 构造期, 并在 build_refs 里对 day 轴做窗口完整性检查。
"""

import pytest

from recapkits.emit import render
from recapkits.insights.detectors import generic
from recapkits.insights.model import Fact, Insight, Period, Series, SeriesError, day_keys


def _series(axis: str, keys: tuple[str, ...], values: tuple[float, ...], unit: str) -> Series:
    return Series(axis=axis, keys=keys, values=values, unit=unit)


def test_hour_keys_must_be_exactly_0_to_23() -> None:
    """hour 轴的键集是固定的, 缺一小时或多一小时都不行。"""
    with pytest.raises(SeriesError, match="keys 必须恰为"):
        _series("hour", tuple(str(hour) for hour in range(23)), (0.0,) * 23, "count")


def test_length_mismatch_is_rejected() -> None:
    """keys 与 values 长度不等是结构性错误, 不能靠渲染器兜底。"""
    with pytest.raises(SeriesError, match="长度不一致"):
        _series("weekday", ("0", "1"), (1.0,), "count")


def test_share_values_must_sum_to_one() -> None:
    """share 轴不求和就没有"占比"语义, 必须当场拒绝。"""
    keys = tuple(str(hour) for hour in range(24))
    with pytest.raises(SeriesError, match=r"之和必须为 1\.0"):
        _series("hour", keys, (0.5,) * 24, "share")


def test_day_axis_is_checked_against_the_review_window() -> None:
    """day 轴必须覆盖窗口的每一天, 含零值; 少一天都不行。"""
    keys = day_keys("2024-01-01", "2024-01-03")
    series = _series("day", keys, (1.0, 0.0, 2.0), "count")

    series.check_window("2024-01-01", "2024-01-03")
    with pytest.raises(SeriesError, match="必须覆盖窗口"):
        series.check_window("2024-01-01", "2024-01-04")


def test_emit_omits_the_key_when_there_is_no_series() -> None:
    """没有序列就不写这个键, 不写 null —— 后者会让下游多一种分支。"""
    insight = _insight(series=None)

    payload = render([insight], sources=["git"], event_count=1, tz="Asia/Shanghai")

    assert "series" not in payload["insights"][0]  # type: ignore[index]


def test_emit_writes_series_in_contract_order() -> None:
    """有序列时按 axis/keys/values/unit 写入, 数值不做二次取整。"""
    series = _series(
        "weekday", tuple(str(day) for day in range(7)), (0.2,) * 5 + (0.0, 0.0), "share"
    )
    insight = _insight(series=series)

    payload = render([insight], sources=["git"], event_count=1, tz="Asia/Shanghai")

    written = payload["insights"][0]["series"]  # type: ignore[index]
    assert list(written) == ["axis", "keys", "values", "unit"]
    assert written["values"] == [0.2] * 5 + [0.0, 0.0]


def test_daily_series_fills_days_without_events() -> None:
    """检测器把没有事件的日期补 0, 并让 signal 固定 0。"""
    period = Period(start="2024-01-01", end="2024-01-10", tz="Asia/Shanghai", coverage=0.1)

    found = generic._vol_daily_series([("2024-01-03", 2)], "git", period)

    series = found[0].series
    assert series is not None
    assert list(series.keys) == list(day_keys("2024-01-01", "2024-01-10"))
    assert series.values[2] == 2
    assert sum(series.values) == 2
    assert found[0].signal == 0.0
    assert found[0].score == 0.0


def test_payload_preview_reports_a_series_delta(capsys) -> None:
    """预览必须让用户看到 series 占了多少字节; 全 0 的差值说明没算对。"""
    from recapkits.commands import _print_payload_sizes

    payload = {
        "version": 1,
        "insights": [
            {
                "id": "vol.daily_series:git:2024",
                "series": {
                    "axis": "day",
                    "keys": list(day_keys("2024-01-01", "2024-12-31")),
                    "values": [1.0] * 366,
                    "unit": "count",
                },
            }
        ],
    }

    _print_payload_sizes(payload)

    out = capsys.readouterr().out
    assert "不含 series" in out
    assert "0.0%" not in out


def _insight(*, series: Series | None) -> Insight:
    """最小 Insight; 只测 emit, 不跑检测器。"""
    return Insight(
        id="test.insight:git:2024",
        kind="time.weekday_rhythm",
        source="git",
        period=Period("2024-01-01", "2024-12-31", "Asia/Shanghai", 0.5),
        headline_fact=Fact("busiest_weekday", "最活跃的星期", "周一", None, "周一"),
        facts=[],
        evidence_sql="SELECT 1",
        evidence_rows=1,
        signal=0.0,
        score=0.0,
        score_parts={},
        novelty="constant",
        sensitivity="low",
        data_sufficiency="ok",
        gated=[],
        caveats=[],
        series=series,
    )
