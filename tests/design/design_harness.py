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

from playwright.sync_api import Locator, Page

HERE = Path(__file__).parent
MEASURE_JS = (HERE / "measure.js").read_text(encoding="utf-8")
ANALYZE_JS = (HERE / "analyze.js").read_text(encoding="utf-8")

#: 三条边带; 与 tokens.css 的 --safe-* / --margin 同源。
SAFE_TOP = 240
SAFE_BOTTOM = 240
SAFE_SIDE = 72

#: 超过 48px 的字按"大字号"算 (WCAG 3:1), 其余 4.5:1。
LARGE_TEXT_PX: float = 48

VIEWPORTS = {"9:16": (1080, 1920), "4:5": (1080, 1350)}


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


def _shoot(stage: Locator) -> bytes:
    return stage.screenshot(animations="disabled")


def capture(page: Page, *, aspect: str) -> CardShot:
    """在当前页面上量一张卡并截三张图; 页面应当只放一张卡。"""
    page.evaluate("document.documentElement.style.setProperty('--stage-scale', '1')")
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


def analyze(analyzer: Page, shot: CardShot) -> dict:
    """在分析页里算一张卡的安全区色差与每处文字的背景像素。"""
    payload = {
        "card": data_url(shot.normal),
        "blank": data_url(shot.blank),
        "hidden": data_url(shot.text_hidden),
        "safeTop": SAFE_TOP,
        "safeBottom": SAFE_BOTTOM,
        "safeSide": SAFE_SIDE,
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
