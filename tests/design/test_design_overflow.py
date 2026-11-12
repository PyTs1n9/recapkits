"""设计断言一: 真实布局下的溢出。

判据由三部分组成, 缺一不可:

1. **横向**: `scrollWidth <= clientWidth + 1`。这是唯一能用滚动尺寸判定的方向 ——
   块级元素不会因为文字高度而"滚出去"。
2. **纵向**: 行数 <= 槽位预算。**不能**用 `scrollHeight <= clientHeight + 1`:
   当 line-height 小于字体的墨迹比 (Windows/YaHei 约 1.32em) 时, Chrome 把字形
   墨迹溢出也计入 scrollHeight, 实测 72px/1.1 的 "137次" 是 client 79 / scroll 87,
   照搬这条判据会让每个正常文本块都报错 (结论写在 cards.css 头注释里)。
3. **不得越界**: 槽位的盒子不能压到底栏那条线, 也不能超出舞台。

预算按槽位名给定, 与组件里的估算同源: `sub` / `label` / `caveat` 允许两行,
其余 (kicker、标题、数字、序号、数值) 只允许一行。
"""

import design_harness as harness
import pytest

pytestmark = pytest.mark.design

TWO_LINE_SLOTS = {"sub", "label", "caveat"}


def line_budget(slot: str) -> int:
    """槽位允许的行数; 与 `text-fit.ts` 里各组件的检查保持一致。"""
    return 2 if slot.rsplit(".", 1)[-1] in TWO_LINE_SLOTS else 1


def test_every_slot_fits(deck: list[dict]) -> None:
    problems: list[str] = []
    for entry in deck:
        shot = entry["shot"]
        for slot in shot.slots:
            where = f"卡片 {shot.card_id} ({shot.aspect}) 的 {slot.slot}"
            if slot.scroll_width > slot.client_width + 1:
                problems.append(
                    f"{where}: 宽 {slot.scroll_width} > 槽位 {slot.client_width} (横向溢出)"
                )
            budget = line_budget(slot.slot)
            if slot.lines > budget:
                problems.append(f"{where}: 实测 {slot.lines} 行 > 预算 {budget} 行")
            if shot.foot_top is not None and slot.bottom > shot.foot_top + 1:
                problems.append(
                    f"{where}: 盒底 {slot.bottom:.1f} 压到底栏 (底栏在 {shot.foot_top:.1f})"
                )
            if slot.bottom > shot.stage_height - harness.SAFE_BOTTOM + 1:
                problems.append(
                    f"{where}: 盒底 {slot.bottom:.1f} 越过安全区 "
                    f"({shot.stage_height - harness.SAFE_BOTTOM})"
                )
    assert not problems, "真实布局下放不下:\n" + "\n".join(problems)


def test_screenshots_have_the_stage_size(deck: list[dict]) -> None:
    """截图尺寸错位说明缩放没固定成 1, 后面的像素断言也就都不成立。"""
    for entry in deck:
        shot = entry["shot"]
        width, height = harness.VIEWPORTS[shot.aspect]
        assert harness.image_size(shot.normal) == (width, height), shot.card_id


def test_deck_covers_every_card_type(deck: list[dict]) -> None:
    """断言本身也要被验证: 六种卡型、两个比例, 一个都不能少。"""
    seen = {(entry["shot"].card_id, entry["shot"].aspect) for entry in deck}
    assert len(seen) == 12, sorted(seen)
    assert len({aspect for _, aspect in seen}) == 2
