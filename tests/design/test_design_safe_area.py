"""设计断言二: 像素级安全区。

对每张 PNG 扫四条边带 (上/下各 240px、左右各 72px), 断言带内没有与背景色
ΔE (CIELAB Cie76) 超过 2 的像素。

背景基准取"同主题、同尺寸、去掉全部卡片"的空白舞台, 而不是某一个颜色值:
`--skin-bg-image` 是渐变, 任何单色基准都会在某一角误判。空白舞台与卡片图逐像素
比对, 渐变本身相互抵消, 只有真正侵入边带的东西才会留下差值。
"""

import design_harness as harness
import pytest

pytestmark = pytest.mark.design

#: Cie76 的差值 2 大致等于"肉眼几乎不可见"; 3 以上开始能被看出来。
MAX_DELTA_E = 2.0


def test_safe_bands_are_clean(deck: list[dict]) -> None:
    problems: list[str] = []
    for entry in deck:
        shot = entry["shot"]
        worst = entry["analysis"]["worst"]
        if worst["de"] > MAX_DELTA_E:
            problems.append(
                f"卡片 {shot.card_id} ({shot.aspect}) 的 {worst['band']} 边带: "
                f"({worst['x']}, {worst['y']}) 处 ΔE={worst['de']:.1f} > {MAX_DELTA_E}"
            )
    assert not problems, "内容侵入了安全区:\n" + "\n".join(problems)


def test_blank_stage_matches_the_stage(deck: list[dict]) -> None:
    """空白舞台必须与卡片图同尺寸, 否则逐像素比对没有意义。"""
    for entry in deck:
        shot = entry["shot"]
        width, height = harness.VIEWPORTS[shot.aspect]
        assert harness.image_size(shot.blank) == (width, height), shot.card_id


def test_pixels_are_measured_not_guessed(deck: list[dict]) -> None:
    """边带里至少要扫到像素: 全 0 的 ΔE 也可能是"什么都没比对"。"""
    for entry in deck:
        analysis = entry["analysis"]
        assert analysis["size"]["w"] == harness.VIEWPORTS[entry["shot"].aspect][0]
        assert analysis["size"]["h"] == harness.VIEWPORTS[entry["shot"].aspect][1]
        assert analysis["worst"]["band"] in {"top", "bottom", "left", "right", "none"}
