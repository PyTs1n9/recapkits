"""惊喜度打分: 完全确定, 无随机, 无学习权重。

    score = 1.00*deviation + 0.60*rarity + 0.50*discontinuity + 0.40*concentration
            - 0.45*obviousness - 1.00*sensitivity

`score_parts` 里存的是**已加权**的分量, 因此 `score` 就是六个分量之和,
`--explain` 可以直接逐项打印而不会被质疑口径。

**数据量闸门**: concentration 在只有一个活跃日时恒为 1.0, discontinuity 在
"只有一天数据"时必然命中 record, 两者都会奖励"数据少"。因此按数据量把它们
置零, 并把被关闭的分量记进 `gated`, 让解释输出能说清"为什么是 0"。

本期没有上一期数据, 所以 deviation 与 rarity 恒为 0.0; 接口保留, 不假装有值。
"""

from collections.abc import Sequence

#: 老套惩罚命中的 kind。这两类是"每个用户都会看到"的内容, 必须降权。
OBVIOUS_KINDS = frozenset({"vol.total", "conc.top_entity"})

WEIGHT_DEVIATION = 1.00
WEIGHT_RARITY = 0.60
WEIGHT_DISCONTINUITY = 0.50
WEIGHT_CONCENTRATION = 0.40
WEIGHT_OBVIOUSNESS = 0.45
WEIGHT_SENSITIVITY = 1.00

#: 数据充足度阈值。
INSUFFICIENT_MAX_DAYS = 3
INSUFFICIENT_MAX_EVENTS = 20
THIN_MAX_DAYS = 30

#: 分量闸门阈值。
CONCENTRATION_MIN_DAYS = 7
CONCENTRATION_MIN_EVENTS = 30
DISCONTINUITY_MIN_DAYS = 30


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """把数值夹到 [lo, hi] 闭区间。"""
    return max(lo, min(hi, value))


def discontinuity(novelty: str) -> float:
    """不连续性: 首次出现与"没有发生"最高, 转折次之, 平稳为 0。"""
    if novelty in {"record", "absence"}:
        return 1.0
    return 0.5 if novelty == "shift" else 0.0


def sufficiency(events: int, active_days: int) -> str:
    """数据充足度: insufficient | thin | ok。"""
    if active_days < INSUFFICIENT_MAX_DAYS or events < INSUFFICIENT_MAX_EVENTS:
        return "insufficient"
    if active_days < THIN_MAX_DAYS:
        return "thin"
    return "ok"


def gated_components(events: int, active_days: int) -> list[str]:
    """列出被数据量闸门关闭的分量; 顺序固定, 便于快照与解释输出比对。"""
    gated: list[str] = []
    if active_days < CONCENTRATION_MIN_DAYS or events < CONCENTRATION_MIN_EVENTS:
        gated.append("concentration")
    if active_days < DISCONTINUITY_MIN_DAYS:
        gated.append("discontinuity")
    return gated


def score_parts(
    *,
    kind: str,
    novelty: str,
    top1_share: float,
    sensitivity: str,
    gated: Sequence[str] = (),
) -> dict[str, float]:
    """返回六个已加权分量; 被闸门关闭的分量保留键、值置 0.0。"""
    parts = {
        "deviation": 0.0,
        "rarity": 0.0,
        "discontinuity": WEIGHT_DISCONTINUITY * discontinuity(novelty),
        "concentration": WEIGHT_CONCENTRATION * clamp(top1_share * 2.0),
        "obviousness": -WEIGHT_OBVIOUSNESS if kind in OBVIOUS_KINDS else 0.0,
        "sensitivity": -WEIGHT_SENSITIVITY if sensitivity == "high" else 0.0,
    }
    for name in gated:
        if name in parts:
            parts[name] = 0.0
    return {key: round(value, 4) for key, value in parts.items()}


def total(parts: dict[str, float]) -> float:
    """把分量求和, 保留 4 位小数, 保证快照逐字节稳定。"""
    return round(sum(parts.values()), 4)
