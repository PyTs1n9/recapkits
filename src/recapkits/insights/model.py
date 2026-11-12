"""洞察的数据结构: Fact / Period / Series / Insight。

目录表里没有单独列这个文件; 它独立出来是为了让 engine 与 detectors 都能导入
而互不依赖(否则两者循环导入)。这里只有 dataclass 与构造期校验, 没有业务逻辑。

字段与 docs/decisions/0001-contracts.md 的 `insights.json` 一一对应。
"""

import math
from dataclasses import dataclass
from datetime import date, timedelta

#: `series.axis` 的取值; 前两个的键集是固定的, day 由窗口决定。
AXES = ("hour", "weekday", "day")
UNITS = ("share", "count")
FIXED_KEYS: dict[str, tuple[str, ...]] = {
    "hour": tuple(str(hour) for hour in range(24)),
    "weekday": tuple(str(day) for day in range(7)),
}


class SeriesError(ValueError):
    """序列不满足契约: 长度、键集、日期格式或 share 求和。"""


@dataclass(frozen=True)
class Series:
    """一条供渲染使用的序列; 它是数据, 不是文案, 永远不进 `display`。"""

    axis: str
    keys: tuple[str, ...]
    values: tuple[float, ...]
    unit: str

    def __post_init__(self) -> None:
        if self.axis not in AXES:
            raise SeriesError(f"series.axis 只能是 {', '.join(AXES)}, 收到 {self.axis!r}")
        if self.unit not in UNITS:
            raise SeriesError(f"series.unit 只能是 {', '.join(UNITS)}, 收到 {self.unit!r}")
        if len(self.keys) != len(self.values):
            raise SeriesError(
                f"series 长度不一致: keys {len(self.keys)} 个, values {len(self.values)} 个"
            )
        if self.axis in FIXED_KEYS and tuple(self.keys) != FIXED_KEYS[self.axis]:
            raise SeriesError(
                f"axis={self.axis} 的 keys 必须恰为 {FIXED_KEYS[self.axis][0]}.."
                f"{FIXED_KEYS[self.axis][-1]}"
            )
        if self.axis == "day":
            self._check_days()
        for value in self.values:
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise SeriesError(f"series.values 必须是数字, 收到 {type(value).__name__}")
            if not math.isfinite(value) or value < 0:
                raise SeriesError(f"series.values 必须是非负有限数, 收到 {value!r}")
        if self.unit == "share" and abs(sum(self.values) - 1.0) > 1e-6:
            raise SeriesError(f"unit=share 的 values 之和必须为 1.0, 实际 {sum(self.values):.9f}")

    def _check_days(self) -> None:
        """day 轴: 键是升序、不重复的 ISO 日期。"""
        previous: date | None = None
        for key in self.keys:
            try:
                current = date.fromisoformat(key)
            except ValueError as exc:
                raise SeriesError(f"axis=day 的 key 必须是 YYYY-MM-DD, 收到 {key!r}") from exc
            if previous is not None and (current - previous).days <= 0:
                raise SeriesError(f"axis=day 的 keys 必须严格升序且不重复, 断在 {key!r}")
            previous = current

    def check_window(self, start: str, end: str) -> None:
        """确认 day 轴覆盖审查窗口的每一天(含零值), 长度等于窗口天数。"""
        if self.axis != "day":
            return
        expected = day_keys(start, end)
        if tuple(self.keys) != expected:
            raise SeriesError(
                f"axis=day 必须覆盖窗口 {start} 至 {end} 的每一天, "
                f"期望 {len(expected)} 个键, 实际 {len(self.keys)} 个"
            )

    def as_dict(self) -> dict[str, object]:
        """按契约的键序展开; values 保持原始数值, 不做二次取整。"""
        return {
            "axis": self.axis,
            "keys": list(self.keys),
            "values": list(self.values),
            "unit": self.unit,
        }


def day_keys(start: str, end: str) -> tuple[str, ...]:
    """窗口内每一天的 ISO 日期, 升序; 用于 day 轴的完整性校验。"""
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)
    return tuple(
        (first + timedelta(days=offset)).isoformat() for offset in range((last - first).days + 1)
    )


@dataclass(frozen=True)
class Fact:
    """一个可被文案引用的事实; `display` 是唯一允许进入文案的形态。"""

    key: str
    label: str
    value: float | str
    unit: str | None
    display: str


@dataclass(frozen=True)
class Period:
    """统计窗口: 本地日期的闭区间, 加上覆盖率 0..1。"""

    start: str
    end: str
    tz: str
    coverage: float


@dataclass(frozen=True)
class Insight:
    """一条候选洞察; 分数与分项由 scoring 填充, 检测器只负责事实与自报强度。

    `signal` 是检测器自报的 0..1 强度, 与 `score_parts["signal"]` 数值相同
    (权重为 1.00), 但语义不同: 前者是未加权的原始强度, 后者是已加权分量。

    `series` 只在需要渲染序列的洞察上出现 (hour/weekday/day); 它不参与打分,
    也不允许被塞进 `display`。
    """

    id: str
    kind: str
    source: str
    period: Period
    headline_fact: Fact
    facts: list[Fact]
    evidence_sql: str
    evidence_rows: int
    signal: float
    score: float
    score_parts: dict[str, float]
    novelty: str
    sensitivity: str
    data_sufficiency: str
    gated: list[str]
    caveats: list[str]
    series: Series | None = None
