"""惊喜度打分: 完全确定, 无随机, 无学习权重。

    score = 1.00*deviation + 0.60*rarity + 0.50*discontinuity + 0.40*concentration
            - 0.45*obviousness - 1.00*sensitivity

`score_parts` 里存的是**已加权**的分量, 因此 `score` 就是六个分量之和,
`--explain` 可以直接逐项打印而不会被质疑口径。

本期没有上一期数据, 所以 deviation 与 rarity 恒为 0.0; 接口保留, 不假装有值。
"""

from collections.abc import Mapping

#: 老套惩罚命中的 kind。这两类是"每个用户都会看到"的内容, 必须降权。
OBVIOUS_KINDS = frozenset({"vol.total", "conc.top_entity"})

WEIGHT_DEVIATION = 1.00
WEIGHT_RARITY = 0.60
WEIGHT_DISCONTINUITY = 0.50
WEIGHT_CONCENTRATION = 0.40
WEIGHT_OBVIOUSNESS = 0.45
WEIGHT_SENSITIVITY = 1.00


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """把数值夹到 [lo, hi] 闭区间。"""
    return max(lo, min(hi, value))


def discontinuity(novelty: str) -> float:
    """不连续性: 首次出现与"没有发生"最高, 转折次之, 平稳为 0。"""
    if novelty in {"record", "absence"}:
        return 1.0
    return 0.5 if novelty == "shift" else 0.0


def score_parts(
    *,
    kind: str,
    novelty: str,
    top1_share: float,
    sensitivity: str,
) -> dict[str, float]:
    """返回六个已加权分量; 键名与契约里的 score_parts 一致。"""
    parts = {
        "deviation": 0.0,
        "rarity": 0.0,
        "discontinuity": WEIGHT_DISCONTINUITY * discontinuity(novelty),
        "concentration": WEIGHT_CONCENTRATION * clamp(top1_share * 2.0),
        "obviousness": -WEIGHT_OBVIOUSNESS if kind in OBVIOUS_KINDS else 0.0,
        "sensitivity": -WEIGHT_SENSITIVITY if sensitivity == "high" else 0.0,
    }
    return {key: round(value, 4) for key, value in parts.items()}


def total(parts: Mapping[str, float]) -> float:
    """把分量求和, 保留 4 位小数, 保证快照逐字节稳定。"""
    return round(sum(parts.values()), 4)
