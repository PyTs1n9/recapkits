"""PNG 输出: 用真实浏览器逐卡截图, 再把截图重编码成不含元数据的 PNG。

三条约束决定了实现形态:

1. **必须用真实浏览器。** 版式有一份实现 (Preact 组件), 截图要截的就是它; 用 Pillow
   之类重画一遍等于维护第二套几何, 一定漂移。
2. **视口与舞台同为 1080 宽, 缩放强制为 1。** 否则页面里的 fit() 会按窗口把舞台再缩
   一次, 截出来的像素对不上设计稿, 而且缩放比例随窗口变化。
3. **截图前等三件事**: 字体就绪、两帧 rAF、页面上的 `data-render-ready` 标记。缺一样
   都可能拍到回退字体或半成品布局。

**启动参数是可复现截图的前提, 不是性能调优。** `--disable-gpu` / `--disable-lcd-text`
/ `--font-render-hinting=none` / `--force-color-profile=srgb` /
`--disable-partial-raster` / `--disable-skia-runtime-opts` / `--hide-scrollbars`
一起把"这台机器的显卡、字体微调、色彩配置"三个变量从画面里拿掉。少一个, 同一份 HTML
两次渲染的 sha256 就可能不同, 而 MP4 的每一帧都是这些截图的复用。

Playwright 是可选依赖 (`uv sync --extra png`): 只出 HTML 的用户不需要它, 也就不会为
一个 40 MB 的包付出安装成本。缺失时给出可操作的错误, 而不是 ImportError。
"""

import importlib
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from recapkits.errors import RecapError

#: 截图是浏览器写的, 会带上 tEXt/zTXt (源路径、软件版本); 产物不该泄露本机路径。
TEXT_CHUNKS = frozenset({b"tEXt", b"zTXt", b"iTXt"})
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

#: 先找本机浏览器, 都没有才回落到 Playwright 自带的 chromium。
BROWSER_CHANNELS = ("chrome", "msedge")

#: 舞台尺寸; 视口必须与它一致, 缩放才是 1。
VIEWPORTS = {"9:16": (1080, 1920), "4:5": (1080, 1350)}

#: 截图用的启动参数; 见模块头的三条约束。顺序固定, 便于比对日志。
LAUNCH_ARGS = (
    "--disable-gpu",
    "--disable-lcd-text",
    "--font-render-hinting=none",
    "--force-color-profile=srgb",
    "--disable-partial-raster",
    "--disable-skia-runtime-opts",
    "--hide-scrollbars",
)

#: 截图前把舞台钉在 (0,0)。视口里的滚动条会让 translate(-50%) 落在半像素上,
#: 而截图矩形必须取整 —— 半像素进画面, 两次渲染的像素网格就差半格。
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

BUNDLED_HINT = "playwright install chromium 会再下载约 150 MB 的浏览器"


@dataclass(frozen=True)
class PngReport:
    """一次 PNG 输出的结果; `channel=None` 表示用的是自带 chromium。"""

    paths: tuple[Path, ...]
    channel: str | None

    @property
    def total_bytes(self) -> int:
        """全部 PNG 的字节数之和。"""
        return sum(path.stat().st_size for path in self.paths)


def strip_text_chunks(data: bytes) -> bytes:
    """去掉 tEXt / zTXt / iTXt 块, 其余块逐字节保留。

    保留的块原样拷贝, 所以 CRC 不用重算 —— 重算反而多一个出错的地方。
    """
    if not data.startswith(PNG_SIGNATURE):
        raise RecapError("截图不是 PNG: 文件头不符")
    out = bytearray(PNG_SIGNATURE)
    position = len(PNG_SIGNATURE)
    while position + 8 <= len(data):
        (length,) = struct.unpack(">I", data[position : position + 4])
        kind = data[position + 4 : position + 8]
        end = position + 12 + length
        if end > len(data):
            raise RecapError(f"PNG 块越界: {kind!r} 声明 {length} 字节")
        if kind not in TEXT_CHUNKS:
            out += data[position:end]
        position = end
    return bytes(out)


def image_size(data: bytes) -> tuple[int, int]:
    """从 IHDR 读宽高; 只用于断言, 不做完整解码。"""
    if not data.startswith(PNG_SIGNATURE) or data[12:16] != b"IHDR":
        raise RecapError("PNG 缺少 IHDR")
    return struct.unpack(">II", data[16:24])


def _sync_playwright() -> Any:
    """延迟导入: 只出 HTML 的用户不该因为缺 Playwright 而跑不起来。

    走 importlib 而不是字面 import: playwright 是可选依赖, CI 的 test job 只装
    `uv sync`, 字面静态导入会让 pyright 报 reportMissingImports 而整条 check 变红。
    """
    try:
        module = importlib.import_module("playwright.sync_api")
    except ImportError as exc:  # pragma: no cover - 取决于安装环境
        raise RecapError(
            "PNG 输出需要 Playwright: 先装可选依赖 (uv sync --extra png)。\n"
            "只出 HTML 的话不需要它: recap render --format html"
        ) from exc
    return module.sync_playwright


def _launch(playwright: Any) -> tuple[Any, str | None]:
    """按 chrome → msedge → 自带 chromium 的顺序找一个能用的浏览器。

    参数对所有候选一致: 换浏览器是回退, 不该顺带换掉渲染条件。
    """
    failures: list[str] = []
    for channel in BROWSER_CHANNELS:
        try:
            return playwright.chromium.launch(channel=channel, args=list(LAUNCH_ARGS)), channel
        except Exception as exc:  # 只要失败就换下一个
            failures.append(f"{channel}: {str(exc).splitlines()[0]}")
    try:
        return playwright.chromium.launch(args=list(LAUNCH_ARGS)), None
    except Exception as exc:
        failures.append(f"自带 chromium: {str(exc).splitlines()[0]}")
    detail = "\n".join(f"  {line}" for line in failures)
    raise RecapError(
        "PNG 输出需要一个浏览器, 但都不可用:\n"
        f"{detail}\n"
        f"装本机 Chrome/Edge 即可; 或 {BUNDLED_HINT}。"
    )


def _wait_ready(page: Any, *, timeout_ms: int) -> None:
    """字体就绪 → 两帧 rAF → data-render-ready; 三件都等, 顺序固定。"""
    page.evaluate("document.fonts.ready")
    page.evaluate("new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))")
    # state="attached": 我们要的是属性出现, 不是"元素可见" —— 对 html 元素谈可见性没有意义。
    page.wait_for_selector('html[data-render-ready="1"]', state="attached", timeout=timeout_ms)


def render_pngs(html: str, *, aspect: str, out_dir: Path, year: int) -> PngReport:
    """把一份已烘焙的 HTML 逐卡截成 PNG, 写到 `out_dir`。

    先清掉同目录里上一轮的 `recap-*.png`: 卡片数变少时, 残留的旧图会让"文件数"撒谎。
    """
    width, height = VIEWPORTS[aspect]
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("recap-*.png"):
        stale.unlink()

    sync_playwright = _sync_playwright()
    written: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="recapkits-png-") as tmp:
        page_path = Path(tmp) / "recap.html"
        page_path.write_bytes(html.encode("utf-8"))
        with sync_playwright() as playwright:
            browser, channel = _launch(playwright)
            try:
                context = browser.new_context(
                    viewport={"width": width, "height": height}, device_scale_factor=1
                )
                page = context.new_page()
                page.goto(page_path.as_uri(), wait_until="load")
                # 强制 1: 视口与舞台同尺寸时它本来就是 1, 但窗口带滚动条或用户改了
                # 视口时 fit() 会缩, 而截图的像素尺寸必须是设计尺寸。
                page.evaluate("document.documentElement.style.setProperty('--stage-scale', '1')")
                _wait_ready(page, timeout_ms=15_000)
                count = page.locator(".stage").count()
                if count == 0:
                    raise RecapError("页面里没有 .stage: 故事没有卡片")
                for index in range(count):
                    stage = page.locator(".stage").nth(index)
                    box = stage.bounding_box()
                    if box is None:
                        raise RecapError(f"第 {index + 1} 张卡取不到包围盒")
                    if box["x"] != int(box["x"]) or box["y"] != int(box["y"]):
                        # 半像素进画面, 两次渲染的像素网格就差半格, sha256 必然不同。
                        raise RecapError(
                            f"第 {index + 1} 张卡的舞台没有落在整数像素上: "
                            f"({box['x']}, {box['y']}); 检查视口宽度与滚动条"
                        )
                    raw = Path(tmp) / f"{index:02d}.png"
                    stage.screenshot(path=str(raw), animations="disabled")
                    data = strip_text_chunks(raw.read_bytes())
                    if image_size(data) != (width, height):
                        raise RecapError(
                            f"第 {index + 1} 张截图的尺寸是 {image_size(data)}, "
                            f"应为 {(width, height)}; 舞台缩放没有固定为 1"
                        )
                    target = out_dir / f"recap-{year}-{index + 1:02d}.png"
                    target.write_bytes(data)
                    written.append(target)
            finally:
                browser.close()
    return PngReport(paths=tuple(written), channel=channel)
