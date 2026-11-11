"""槽位长度度量: 先给 v0 估算, 渲染器落地后换成真实字体度量, 签名不变。

    Measure = Callable[[str, str, str], float]   # (slot, text, theme) -> px

校验器只依赖这个签名, 所以替换实现时 validate.py 一行都不用改。
"""

import unicodedata
from collections.abc import Callable

Measure = Callable[[str, str, str], float]

#: 各槽位字号与可用宽度(px); 画布宽 1080, 左右各留 72。
SLOT_FONT_PX = {"headline": 64, "sub": 36, "kicker": 28}
SLOT_BUDGET_PX = {"headline": 1080 - 2 * 72, "sub": 1080 - 2 * 72, "kicker": 480}


def _is_wide(char: str) -> bool:
    """全角/宽字符按 1em 计, 其余按 0.55em 计。"""
    return unicodedata.east_asian_width(char) in {"W", "F"}


def default_measure(slot: str, text: str, theme: str) -> float:
    """v0 估算: CJK 字符计 1.0em, 拉丁字符计 0.55em, 按槽位字号折算成 px。"""
    size = SLOT_FONT_PX.get(slot, 40)
    ems = sum(1.0 if _is_wide(char) else 0.55 for char in text)
    return ems * size
