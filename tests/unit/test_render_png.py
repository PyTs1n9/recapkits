"""PNG 输出: 逐卡一张、尺寸固定、命名可排序、元数据被剥掉。

这些用例需要 Playwright 与一个可用浏览器 (本机 chrome/msedge 或自带 chromium)。
CI 的 node-gate 会装好可选依赖并断言"不得跳过", 免得无浏览器时全绿。
"""

import json
import struct
import sys
import zlib
from pathlib import Path

import pytest

from recapkits.errors import RecapError
from recapkits.render import png
from recapkits.render.pipeline import render_document

FIXTURES = Path(__file__).parent.parent / "fixtures"
STORY = FIXTURES / "story-render.json"
INSIGHTS = FIXTURES / "insights.json"


def _chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def _tiny_png(*, text: bytes | None = None) -> bytes:
    """1x1 的合法 PNG; 可选带一个 tEXt 块, 供剥离逻辑的用例使用。"""
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\xff\xff")
    parts = [png.PNG_SIGNATURE, _chunk(b"IHDR", ihdr)]
    if text is not None:
        parts.append(_chunk(b"tEXt", text))
    parts += [_chunk(b"IDAT", idat), _chunk(b"IEND", b"")]
    return b"".join(parts)


def _browser_available() -> bool:
    """真的启动一次浏览器; 只看包在不在会漏掉"装了但没浏览器"。"""
    try:
        sync_playwright = png._sync_playwright()
    except RecapError:
        return False
    try:
        with sync_playwright() as playwright:
            browser, _ = png._launch(playwright)
            browser.close()
    except Exception:  # 任何失败都算"没有浏览器"
        return False
    return True


needs_browser = pytest.mark.skipif(not _browser_available(), reason="需要 Playwright 与一个浏览器")


def test_strip_text_chunks_drops_metadata_only() -> None:
    """tEXt 被剥掉, 其余块逐字节保留, 图片本身不变。"""
    original = _tiny_png(text=b"Software\x00Chrome")

    stripped = png.strip_text_chunks(original)

    assert b"tEXt" not in stripped
    assert stripped == _tiny_png()
    assert png.image_size(stripped) == (1, 1)


def test_strip_refuses_non_png() -> None:
    """不是 PNG 就明确报错, 不要产出一个半截文件。"""
    with pytest.raises(RecapError, match="不是 PNG"):
        png.strip_text_chunks(b"not a png at all")


def test_missing_playwright_says_how_to_install(monkeypatch: pytest.MonkeyPatch) -> None:
    """缺可选依赖时给一句可操作的话, 而不是 ImportError。"""
    # 只把父包设成 None 不够: 子模块已经 import 过时, `from playwright.sync_api ...`
    # 直接命中 sys.modules 缓存。两个条目都要挡住。
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)

    with pytest.raises(RecapError, match=r"uv sync --extra png"):
        png._sync_playwright()


@needs_browser
def test_one_png_per_card(tmp_path: Path) -> None:
    """三张卡 → 三个文件, 命名补零且排序等于卡片顺序, 尺寸就是舞台尺寸。"""
    html = render_document(STORY, str(INSIGHTS), aspect="9:16")

    report = png.render_pngs(html, aspect="9:16", out_dir=tmp_path, year=2024)

    assert [path.name for path in report.paths] == [
        "recap-2024-01.png",
        "recap-2024-02.png",
        "recap-2024-03.png",
    ]
    for path in report.paths:
        data = path.read_bytes()
        assert png.image_size(data) == (1080, 1920)
        assert b"tEXt" not in data and b"zTXt" not in data
    assert report.total_bytes > 0


@needs_browser
def test_four_by_five_png_is_1350_tall(tmp_path: Path) -> None:
    """4:5 只改高度; 宽度与舞台一致, 否则说明缩放没固定成 1。"""
    html = render_document(STORY, str(INSIGHTS), aspect="4:5")

    report = png.render_pngs(html, aspect="4:5", out_dir=tmp_path, year=2024)

    assert png.image_size(report.paths[0].read_bytes()) == (1080, 1350)


@needs_browser
def test_stale_cards_are_removed(tmp_path: Path) -> None:
    """上一轮的第 9 张不该留在目录里, 否则"文件数"会撒谎。"""
    stale = tmp_path / "recap-2024-09.png"
    stale.write_bytes(_tiny_png())
    keep = tmp_path / "notes.txt"
    keep.write_text("不是卡片, 不要动", encoding="utf-8")
    html = render_document(STORY, str(INSIGHTS), aspect="9:16")

    png.render_pngs(html, aspect="9:16", out_dir=tmp_path, year=2024)

    assert not stale.exists()
    assert keep.exists()


@needs_browser
def test_cli_writes_into_the_workspace_cards_dir(tmp_path: Path, monkeypatch) -> None:
    """`recap render --format png` 写 .recapkits/out/cards/, 并打印张数与总字节。"""
    from recapkits.cli import main

    workspace = tmp_path / ".recapkits"
    workspace.mkdir()
    (workspace / "config.json").write_text(
        json.dumps({"tz": "Asia/Shanghai", "year": 2024}), encoding="utf-8"
    )
    (workspace / "story.json").write_text(STORY.read_text(encoding="utf-8"), encoding="utf-8")
    (workspace / "insights.json").write_text(INSIGHTS.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert main(["render", "--format", "png", "--aspect", "4:5"]) == 0

    cards = sorted((workspace / "out" / "cards").glob("*.png"))
    assert len(cards) == 3
    assert png.image_size(cards[0].read_bytes()) == (1080, 1350)
