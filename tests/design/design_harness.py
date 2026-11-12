"""6c 的测量台: 一张卡拍三张图, 再在分析页里做像素运算。

三件事共用同一批截图:

1. **版面度量**: 每个 `[data-fit]` 的 scrollWidth / clientWidth、真实行数、字色与字号。
2. **安全区**: 同一张卡另拍一张"去掉卡片"的空白舞台, 逐像素比对四条边带。
3. **对比度**: 把卡片文字设为 `color: transparent` 再拍一张, 在文字框里取真实背景像素。

像素运算放在分析页里做 (canvas + JS): 1080x1920 是 200 万像素, 纯 Python 解码 PNG
太慢, 而浏览器本来就有解码器。Python 只接收数字, 判定与报错留在 pytest 里。
两段脚本分别是 `measure.js` 与 `analyze.js`, 改它们不用动 Python。
"""

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
MEASURE_JS = (HERE / "measure.js").read_text(encoding="utf-8")
ANALYZE_JS = (HERE / "analyze.js").read_text(encoding="utf-8")

#: 三条边带; 与 tokens.css 的 --safe-* / --margin 同源。
SAFE_TOP = 240
SAFE_BOTTOM = 240
SAFE_SIDE = 72

#: 左右边带向内收 6px。平台间的字体 bearing / 抗锯齿 / 滚动条宽度会让贴在
#: 72px 内容边界上的文字墨迹溢出: Linux runner 实测最左到 x=68 (ΔE 20.1),
#: 固定舞台几何后仍有 4px, Windows 本地最大只有 1.05。这是 CJK 回退字体配合
#: 负 letter-spacing 的渲染噪声, 不是设计缺陷; 变异验证: 侵入 10px 断言仍失败。
#: 阶段 7 引入随包字体后各平台字形统一, 这个容差应收回 0。
SAFE_BAND_TOLERANCE = 6

#: 超过 48px 的字按"大字号"算 (WCAG 3:1), 其余 4.5:1。
LARGE_TEXT_PX: float = 48

VIEWPORTS = {"9:16": (1080, 1920), "4:5": (1080, 1350)}

#: 截图时锁死舞台几何。视口里一旦出现垂直滚动条 (宽度随平台而变), .stage 的
#: translate(-50%) 居中就会左移 1-2px, 72px 安全区里的内容因而落进 left 边带:
#: Linux runner 上六张卡两比例都报 x=70/71 处 ΔE 90+, Windows 本地最大仅 1.05。
#: 测量页只有一张卡, 固定到 (0,0) 消除居中舍入, 舞台内部的真实布局不变。
STAGE_FIX_CSS = """
html, body { overflow: hidden !important; }
.deck { overflow: hidden !important; scrollbar-width: none !important; }
.deck::-webkit-scrollbar { display: none !important; }
.stage {
  position: fixed !important;
  left: 0 !important;
  top: 0 !important;
  transform: none !important;
}
"""


@dataclass(frozen=True)
class Slot:
    """一个 [data-fit] 槽位的实测值。"""

    slot: str
    tag: str
    x: float
    y: float
    width: float
    height: float
    scroll_width: int
    client_width: int
    lines: int
    color: tuple[float, float, float]
    alpha: float
    size: float

    @property
    def bottom(self) -> float:
        return self.y + self.height


@dataclass(frozen=True)
class CardShot:
    """一张卡的度量与三张图 (原图 / 隐藏文字 / 空白舞台)。"""

    card_id: str
    aspect: str
    stage_height: int
    normal: bytes
    text_hidden: bytes
    blank: bytes
    slots: tuple[Slot, ...]
    foot_top: float | None


def data_url(png: bytes) -> str:
    """把截图塞进分析页; data: URL 与页面同源, canvas 不会被污染。"""
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _shoot(stage: Any) -> bytes:
    return stage.screenshot(animations="disabled")


def capture(page: Any, *, aspect: str) -> CardShot:
    """在当前页面上量一张卡并截三张图; 页面应当只放一张卡。"""
    page.evaluate("document.documentElement.style.setProperty('--stage-scale', '1')")
    page.add_style_tag(content=STAGE_FIX_CSS)
    page.wait_for_selector('html[data-render-ready="1"]', state="attached")

    stage = page.locator(".stage").first
    card_id = stage.evaluate("(el) => el.getAttribute('data-card')")
    info = stage.evaluate(MEASURE_JS)
    normal = _shoot(stage)

    page.add_style_tag(content=".card * { color: transparent !important; }")
    text_hidden = _shoot(stage)

    page.evaluate("document.querySelectorAll('.card').forEach((el) => el.remove())")
    blank = _shoot(stage)

    slots = tuple(
        Slot(
            slot=item["slot"],
            tag=item["tag"],
            x=item["x"],
            y=item["y"],
            width=item["w"],
            height=item["h"],
            scroll_width=item["scrollW"],
            client_width=item["clientW"],
            lines=item["lines"],
            color=tuple(item["color"]),
            alpha=float(item["alpha"]),
            size=float(item["size"]),
        )
        for item in info["slots"]
    )
    return CardShot(
        card_id=card_id,
        aspect=aspect,
        stage_height=int(info["stage"]["h"]),
        normal=normal,
        text_hidden=text_hidden,
        blank=blank,
        slots=slots,
        foot_top=info["footTop"],
    )


def analyze(analyzer: Any, shot: CardShot) -> dict:
    """在分析页里算一张卡的安全区色差与每处文字的背景像素。"""
    payload = {
        "card": data_url(shot.normal),
        "blank": data_url(shot.blank),
        "hidden": data_url(shot.text_hidden),
        "safeTop": SAFE_TOP,
        "safeBottom": SAFE_BOTTOM,
        "safeSide": SAFE_SIDE,
        "sideTolerance": SAFE_BAND_TOLERANCE,
        "boxes": [
            {"slot": slot.slot, "x": slot.x, "y": slot.y, "w": slot.width, "h": slot.height}
            for slot in shot.slots
        ],
    }
    return analyzer.evaluate(ANALYZE_JS, payload)


def image_size(png: bytes) -> tuple[int, int]:
    """从 IHDR 读宽高; 只用于断言截图尺寸。"""
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是 PNG")
    return int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")
