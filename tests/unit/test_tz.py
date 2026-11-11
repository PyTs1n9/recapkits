"""tz.py 的边界测试: 夏令时、闰年、午夜、跨年、源偏移优先。

前六个用例逐条对应 docs 里的验收表, 后两个是属性测试。
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from recapkits.tz import local_datetime, parse_utc, resolve_local, to_utc_iso, utc_now_iso

ZONES = (
    "UTC",
    "Asia/Shanghai",
    "Asia/Kolkata",
    "Europe/Berlin",
    "America/New_York",
    "Australia/Sydney",
)


def test_spring_forward_skips_0200() -> None:
    """美国春季前进日: 02:00 本地不存在, 前后两次分别落在 1 点和 3 点。"""
    before = resolve_local("2026-03-08T06:59:00Z", None, "America/New_York")
    after = resolve_local("2026-03-08T07:00:00Z", None, "America/New_York")

    assert before == ("2026-03-08", 1)
    assert after == ("2026-03-08", 3)


def test_fall_back_repeats_hour_one() -> None:
    """美国秋季回退日: 本地 1 点出现两次, 两个 UTC 时刻的小时都是 1。"""
    first = resolve_local("2026-11-01T05:30:00Z", None, "America/New_York")
    second = resolve_local("2026-11-01T06:30:00Z", None, "America/New_York")

    assert first == ("2026-11-01", 1)
    assert second == ("2026-11-01", 1)


def test_leap_day_survives() -> None:
    """闰日不会被抹成 03-01。"""
    assert resolve_local("2028-02-29T12:00:00Z", None, "Asia/Shanghai") == ("2028-02-29", 20)


def test_midnight_boundary_in_shanghai() -> None:
    """UTC 16:00 是上海次日 00:00, 差一秒则仍是当天 23 点。"""
    assert resolve_local("2026-03-11T15:59:00Z", None, "Asia/Shanghai") == ("2026-03-11", 23)
    assert resolve_local("2026-03-11T16:00:00Z", None, "Asia/Shanghai") == ("2026-03-12", 0)


def test_source_offset_beats_configured_zone() -> None:
    """源自带 +09:00 时, 即便配置成 UTC 也按 +09:00 落本地时间。"""
    with_offset = resolve_local("2026-01-01T00:00:00Z", 540, "UTC")
    without_offset = resolve_local("2026-01-01T00:00:00Z", None, "UTC")

    assert with_offset == ("2026-01-01", 9)
    assert without_offset == ("2026-01-01", 0)


def test_year_boundary_in_shanghai() -> None:
    """UTC 年末 16:30 已经是上海次年 1 月 1 日 0 点。"""
    assert resolve_local("2026-12-31T16:30:00Z", None, "Asia/Shanghai") == ("2027-01-01", 0)


def test_local_datetime_keeps_minutes_and_seconds() -> None:
    """精确版本保留分秒, 不打折扣。"""
    local = local_datetime("2026-11-01T05:30:45Z", None, "America/New_York")

    assert (local.hour, local.minute, local.second) == (1, 30, 45)


def test_parse_utc_rejects_naive_and_accepts_offset() -> None:
    """无时区信息必须报错, 带偏移必须归一为 UTC。"""
    assert parse_utc("2026-03-11T23:41:07+08:00") == datetime(2026, 3, 11, 15, 41, 7, tzinfo=UTC)
    with pytest.raises(ValueError, match="缺少时区信息"):
        parse_utc("2026-03-11T23:41:07")


def test_to_utc_iso_normalizes() -> None:
    """带偏移的输入统一写成 Z 结尾、秒级精度。"""
    moment = datetime(2026, 3, 11, 23, 41, 7, 999999, tzinfo=ZoneInfo("Asia/Shanghai"))

    assert to_utc_iso(moment) == "2026-03-11T15:41:07Z"


def test_utc_now_iso_is_parseable_and_ends_with_z() -> None:
    """系统时钟入口自身也要过一遍解析。"""
    now = utc_now_iso()

    assert now.endswith("Z")
    assert abs(
        parse_utc(now) - datetime.fromtimestamp(datetime.now().timestamp(), UTC)
    ) < timedelta(seconds=5)


@settings(max_examples=200, deadline=None)
@given(
    moment=st.datetimes(
        min_value=datetime(1970, 1, 2),
        max_value=datetime(2099, 12, 30),
        timezones=st.just(UTC),
    ),
    tz_name=st.sampled_from(ZONES),
)
def test_round_trip_utc_local_utc(moment: datetime, tz_name: str) -> None:
    """随机时刻 + 随机时区: 本地时间重新按该时区解释, 必须回到原 UTC 时刻。

    `resolve_local` 只保留到小时, 所以精确回环用 `local_datetime` 验证;
    回退日的本地墙钟时间有两个候选, 命中其一即算正确。
    """
    ts_utc = to_utc_iso(moment)
    assert parse_utc(ts_utc) == moment.replace(microsecond=0)

    local = local_datetime(ts_utc, None, tz_name)
    assert local.second == moment.second
    assert local.microsecond == 0

    zone = ZoneInfo(tz_name)
    candidates = set()
    for fold in (0, 1):
        wall = local.replace(tzinfo=zone, fold=fold)
        offset = wall.utcoffset()
        assert offset is not None
        candidates.add((wall.replace(tzinfo=None) - offset).replace(tzinfo=UTC))

    assert parse_utc(ts_utc) in candidates


@settings(max_examples=200, deadline=None)
@given(
    moment=st.datetimes(
        min_value=datetime(1970, 1, 2),
        max_value=datetime(2099, 12, 30),
        timezones=st.just(UTC),
    ),
    tz_name=st.sampled_from(ZONES),
)
def test_resolve_local_invariants(moment: datetime, tz_name: str) -> None:
    """小时恒在 0..23, 日期恒可解析, 且与精确版本一致。"""
    local_date, local_hour = resolve_local(to_utc_iso(moment), None, tz_name)

    assert 0 <= local_hour <= 23
    assert (
        date.fromisoformat(local_date) == local_datetime(to_utc_iso(moment), None, tz_name).date()
    )


@settings(max_examples=100, deadline=None)
@given(
    moment=st.datetimes(
        min_value=datetime(1970, 1, 2),
        max_value=datetime(2099, 12, 30),
        timezones=st.just(UTC),
    ),
    offset_min=st.integers(min_value=-720, max_value=840),
)
def test_source_offset_always_wins(moment: datetime, offset_min: int) -> None:
    """只要源给了偏移, 换算就是纯平移, 与所选时区无关。"""
    shifted = moment.replace(microsecond=0) + timedelta(minutes=offset_min)

    assert resolve_local(to_utc_iso(moment), offset_min, "Asia/Shanghai") == (
        shifted.date().isoformat(),
        shifted.hour,
    )
