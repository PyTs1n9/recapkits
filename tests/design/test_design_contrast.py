"""设计断言三: WCAG 对比度。

正文 (<48px) 要求 4.5:1, 展示字 (>=48px) 要求 3:1。

背景不用祖先链上的 background-color 硬拼 —— 舞台是渐变, 拼出来的值会偏。做法是
在"文字全部透明"的那张图上取文字包围盒内的真实像素, 取其中最亮的一个作为基准:
浅色字最怕的就是压到亮背景, 取最大值即最坏情况。

半透明文字 (`--skin-muted` / `--skin-faint`) 先与背景合成再算比值, 否则会把
"实际显示的颜色"算得比真实更亮。
"""

import design_harness as harness
import pytest

pytestmark = pytest.mark.design


def _linear(channel: float) -> float:
    value = channel / 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def _luminance(rgb: tuple[float, float, float] | list[float]) -> float:
    r, g, b = rgb
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def _composite(color: tuple[float, float, float], alpha: float, bg: list[float]) -> list[float]:
    return [alpha * c + (1 - alpha) * b for c, b in zip(color, bg, strict=True)]


def contrast_ratio(color: tuple[float, float, float], alpha: float, bg: list[float]) -> float:
    """文字与背景的 WCAG 对比度; 文字先按 alpha 与背景合成。"""
    text = _luminance(_composite(color, alpha, bg))
    back = _luminance(bg)
    high, low = max(text, back), min(text, back)
    return (high + 0.05) / (low + 0.05)


def required_ratio(size: float) -> float:
    return 3.0 if size >= harness.LARGE_TEXT_PX else 4.5


def test_contrast_meets_wcag(deck: list[dict]) -> None:
    problems: list[str] = []
    for entry in deck:
        shot = entry["shot"]
        for slot, sampled in zip(shot.slots, entry["analysis"]["slots"], strict=True):
            if sampled["bgLum"] < 0:
                problems.append(f"卡片 {shot.card_id} 的 {slot.slot}: 取不到背景像素")
                continue
            ratio = contrast_ratio(slot.color, slot.alpha, sampled["bg"])
            need = required_ratio(slot.size)
            if ratio < need:
                problems.append(
                    f"卡片 {shot.card_id} ({shot.aspect}) 的 {slot.slot}: "
                    f"{ratio:.2f}:1 < {need}:1 (字号 {slot.size:.0f}px, 背景 {sampled['bg']})"
                )
    assert not problems, "对比度不足:\n" + "\n".join(problems)


def test_contrast_math_matches_wcag_examples() -> None:
    """断言自身的自检: 纯黑对纯白的比值必须落在 WCAG 的 21:1。"""
    assert contrast_ratio((0, 0, 0), 1.0, [255, 255, 255]) == pytest.approx(21.0, rel=1e-3)
    assert contrast_ratio((255, 255, 255), 1.0, [255, 255, 255]) == pytest.approx(1.0)
