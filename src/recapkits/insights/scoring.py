"""惊喜度打分 (二期): 完全确定, 无随机, 无学习权重。

    score = 1.00*signal + 0.40*deviation + 0.30*discontinuity - 1.00*sensitivity

一期的公式是六个"通用分量", 但每个检测器能被激活的分量不同, 结果只有二值的
`novelty` 真正在工作, `time.*` 恒为 0、`disc.*` 恒为 0.5、`conc.*` 被自己的
惩罚项封顶为负。二期改成"每个检测器自己报告 signal":

- `signal`     检测器自报的 0..1 强度, 必填, 锚点见 `docs/insights.md`
- `deviation`  `clamp(|稳健 z| / 3)`, 与上一期比; **没有上一期时为 0 并记入 gated**
- `discontinuity` 有上一期且与上期不同: record/absence=1.0, shift=0.5;
                **没有上一期时为 0 并记入 gated**
- `sensitivity` high -> 1.0

`score_parts` 里存的是**已加权**的分量, 因此 `score` 就是四个分量之和,
`--explain` 可以直接逐项打印而不会被质疑口径。

`novelty` 字段保留 (文案要用, 也要显示给用户看), 但不再以二值标签的形式驱动打分。
"""

from collections.abc import Sequence

WEIGHT_SIGNAL = 1.00
WEIGHT_DEVIATION = 0.40
WEIGHT_DISCONTINUITY = 0.30
WEIGHT_SENSITIVITY = 1.00

#: signal 锚点。改这几个数就等于改排序, 所以集中放在这里, 并有 docs/insights.md 对照。
SIGNAL_VOL_TOTAL = 0.05
"""`vol.total` 恒定 0.05: 只作开场卡锚点, 不参与竞争。"""

SIGNAL_BUSIEST_DAY_FLOOR = 1.5
SIGNAL_BUSIEST_DAY_SPAN = 8.5
"""`vol.busiest_day`: 峰值 1.5x 日均 = 无信号, 10x = 满格。"""

SIGNAL_TOP_ENTITY_FLOOR = 0.20
SIGNAL_TOP_ENTITY_SPAN = 0.60
"""`conc.top_entity`: 20% = 没有集中, 80% = 极端集中。"""

SIGNAL_LATE_NIGHT_FLOOR = 0.10
SIGNAL_LATE_NIGHT_SPAN = 0.40
"""`time.hour_rhythm`: 10% 深夜 ≈ 均匀分布, 50% = 极端夜行。"""

SIGNAL_WEEKDAY_FLOOR = 1 / 7
SIGNAL_WEEKDAY_CEILING = 0.40
SIGNAL_WEEKDAY_SPAN = SIGNAL_WEEKDAY_CEILING - SIGNAL_WEEKDAY_FLOOR
"""`time.weekday_rhythm`: 1/7 = 完全均匀, 40% = 极端偏向某一天。"""

SIGNAL_STREAK_FULL_DAYS = 60
"""`disc.longest_streak`: 连续 60 天 = 满格。"""

SIGNAL_GAP_FULL_DAYS = 21
"""`disc.longest_gap`: 空档 21 天 = 满格。"""

#: 稳健 z 的饱和点; |z| 超过它就满分。
DEVIATION_Z_CLAMP = 3.0

#: 数据充足度阈值。
INSUFFICIENT_MAX_DAYS = 3
INSUFFICIENT_MAX_EVENTS = 20
THIN_MAX_DAYS = 30


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """把数值夹到 [lo, hi] 闭区间。"""
    return max(lo, min(hi, value))


def signal_vol_total() -> float:
    """体量总数: 恒定锚点, 让开场卡有一个非负底分。"""
    return SIGNAL_VOL_TOTAL


def signal_busiest_day(peak_events: int, daily_avg: float) -> float:
    """单日峰值相对日均的倍数; 1.5x 以下没有信号, 10x 满格。"""
    if daily_avg <= 0:
        return 0.0
    ratio = peak_events / daily_avg
    return clamp((ratio - SIGNAL_BUSIEST_DAY_FLOOR) / SIGNAL_BUSIEST_DAY_SPAN)


def signal_top_entity(top1_share: float) -> float:
    """首位实体占比; 20% 以下等于没有集中, 80% 满格。"""
    return clamp((top1_share - SIGNAL_TOP_ENTITY_FLOOR) / SIGNAL_TOP_ENTITY_SPAN)


def signal_hour_rhythm(late_night_share: float) -> float:
    """深夜占比; 10% 约等于均匀分布, 50% 满格。"""
    return clamp((late_night_share - SIGNAL_LATE_NIGHT_FLOOR) / SIGNAL_LATE_NIGHT_SPAN)


def signal_weekday_rhythm(busiest_share: float) -> float:
    """最活跃星期的占比; 1/7 是均匀分布的下界, 40% 满格。"""
    return clamp((busiest_share - SIGNAL_WEEKDAY_FLOOR) / SIGNAL_WEEKDAY_SPAN)


def signal_streak(days: int) -> float:
    """连续活跃天数; 60 天满格。"""
    return clamp(days / SIGNAL_STREAK_FULL_DAYS)


def signal_gap(days: int) -> float:
    """空档天数; 21 天满格。"""
    return clamp(days / SIGNAL_GAP_FULL_DAYS)


def discontinuity(novelty: str) -> float:
    """不连续性: 首次出现与"没有发生"最高, 转折次之, 平稳为 0。

    这里只回答"标签本身有多不连续"; 没有上一期时由 `score_parts` 把它归零,
    因为"与上期不同"这个前提根本不成立。
    """
    if novelty in {"record", "absence"}:
        return 1.0
    return 0.5 if novelty == "shift" else 0.0


def sufficiency(events: int, active_days: int) -> str:
    """数据充足度: insufficient | thin | ok。

    这一项管的是"该不该出卡", 与二期的"出了卡怎么排序"是两件事, 判定维持 4a 不变。
    """
    if active_days < INSUFFICIENT_MAX_DAYS or events < INSUFFICIENT_MAX_EVENTS:
        return "insufficient"
    if active_days < THIN_MAX_DAYS:
        return "thin"
    return "ok"


def gated_components(*, has_previous: bool) -> list[str]:
    """列出被闸门关闭的分量; 顺序固定, 便于快照与解释输出比对。

    本期 (阶段 5) 没有同比数据, 所以 deviation 与 discontinuity 一律关闭,
    并在解释输出里说明"为什么是 0"。后续接入上一期后传 True 即可解除。
    """
    return [] if has_previous else ["deviation", "discontinuity"]


def score_parts(
    *,
    signal: float,
    novelty: str,
    sensitivity: str,
    deviation_z: float | None = None,
    gated: Sequence[str] = (),
) -> dict[str, float]:
    """返回四个已加权分量; 被闸门关闭的分量保留键、值置 0.0。"""
    deviation = 0.0 if deviation_z is None else clamp(abs(deviation_z) / DEVIATION_Z_CLAMP)
    parts = {
        "signal": WEIGHT_SIGNAL * clamp(signal),
        "deviation": WEIGHT_DEVIATION * deviation,
        "discontinuity": WEIGHT_DISCONTINUITY * discontinuity(novelty),
        "sensitivity": -WEIGHT_SENSITIVITY if sensitivity == "high" else 0.0,
    }
    for name in gated:
        if name in parts:
            parts[name] = 0.0
    return {key: round(value, 4) for key, value in parts.items()}


def total(parts: dict[str, float]) -> float:
    """把分量求和, 保留 4 位小数, 保证快照逐字节稳定。"""
    return round(sum(parts.values()), 4)
