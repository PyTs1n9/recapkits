"""PNG 逐字节确定性: 同一份 HTML 渲染两次, 每个文件的 sha256 必须相同。

为什么是字节级而不是像素容差: MP4 的每一帧都是这些截图的复用。帧哈希不稳,
就问不出「这次改动有没有动画面」, 视频也就没有任何回归基线。阶段 6 的欠账
(同字节数、不同 sha256) 在这里被显式断言掉。

失败时的报错要给到「第一个不同的文件 + 首个差异像素坐标」, 而不是一句
"图片不同" —— 否则下一个人还是要自己解码两张 200 万像素的 PNG。
"""

import hashlib
import struct
import zlib
from pathlib import Path

import pytest

from recapkits.errors import RecapError
from recapkits.render import png
from recapkits.render.pipeline import render_document

FIXTURES = Path(__file__).parent.parent / "fixtures"
STORY = FIXTURES / "story-render.json"
INSIGHTS = FIXTURES / "insights.json"


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

CHANNELS = {2: 3, 6: 4}


def _decode(data: bytes) -> tuple[int, int, int, list[bytearray]]:
    """解出 8 位、非隔行的 RGB/RGBA 扫描行; 只服务于失败时的像素定位。"""
    width, height, depth, color = struct.unpack(">IIBB", data[16:26])
    interlace = data[28]
    if depth != 8 or interlace != 0 or color not in CHANNELS:
        raise ValueError(f"不支持的 PNG 形态: depth={depth} color={color} interlace={interlace}")
    channels = CHANNELS[color]

    idat = bytearray()
    position = len(png.PNG_SIGNATURE)
    while position + 8 <= len(data):
        (length,) = struct.unpack(">I", data[position : position + 4])
        kind = data[position + 4 : position + 8]
        if kind == b"IDAT":
            idat += data[position + 8 : position + 8 + length]
        position += 12 + length
    raw = zlib.decompress(bytes(idat))

    stride = width * channels
    rows: list[bytearray] = []
    previous = bytearray(stride)
    cursor = 0
    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        row = bytearray(raw[cursor : cursor + stride])
        cursor += stride
        for index in range(stride):
            left = row[index - channels] if index >= channels else 0
            up = previous[index]
            up_left = previous[index - channels] if index >= channels else 0
            if filter_type == 0:
                continue
            if filter_type == 1:
                row[index] = (row[index] + left) & 0xFF
            elif filter_type == 2:
                row[index] = (row[index] + up) & 0xFF
            elif filter_type == 3:
                row[index] = (row[index] + ((left + up) >> 1)) & 0xFF
            elif filter_type == 4:
                estimate = left + up - up_left
                distances = (abs(estimate - left), abs(estimate - up), abs(estimate - up_left))
                predictor = (left, up, up_left)[distances.index(min(distances))]
                row[index] = (row[index] + predictor) & 0xFF
            else:
                raise ValueError(f"未知的 PNG 行过滤器 {filter_type}")
        rows.append(row)
        previous = row
    return width, height, channels, rows


def _first_difference(left: bytes, right: bytes) -> str:
    """两图的首个差异像素; 只在不相等时调用。"""
    if len(left) != len(right):
        return f"字节数不同: {len(left)} vs {len(right)}"
    try:
        width, height, channels, rows_left = _decode(left)
        _, _, _, rows_right = _decode(right)
    except (ValueError, zlib.error) as exc:
        offset = next(
            index for index, pair in enumerate(zip(left, right, strict=True)) if pair[0] != pair[1]
        )
        return f"无法解码像素 ({exc}); 首个不同字节在偏移 {offset}"
    for y in range(height):
        if rows_left[y] == rows_right[y]:
            continue
        for x in range(width):
            start = x * channels
            before = rows_left[y][start : start + channels]
            after = rows_right[y][start : start + channels]
            if before != after:
                return (
                    f"首个差异像素 ({x}, {y}): {tuple(before)} vs {tuple(after)}"
                    f" (共 {width}x{height})"
                )
    return "解码后没有差异像素 (差异在非像素数据里)"


def test_decoder_round_trips_a_known_png() -> None:
    """自检: 解码器必须能从一张 1x1 的图上取回颜色, 否则失败信息本身不可信。"""
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x7f")
    chunks = [(b"IHDR", ihdr), (b"IDAT", idat), (b"IEND", b"")]

    def chunk(kind: bytes, body: bytes) -> bytes:
        crc = zlib.crc32(kind + body) & 0xFFFFFFFF
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", crc)

    data = png.PNG_SIGNATURE + b"".join(chunk(kind, body) for kind, body in chunks)

    width, height, channels, rows = _decode(data)

    assert (width, height, channels) == (1, 1, 3)
    assert rows[0] == bytearray(b"\xff\x00\x7f")


@needs_browser
def test_two_renders_are_byte_identical(tmp_path: Path) -> None:
    """同一份 HTML 渲染两次, 每个文件的 sha256 相同; 不同就指出第一处差异像素。"""
    html = render_document(STORY, str(INSIGHTS), aspect="9:16")

    first = png.render_pngs(html, aspect="9:16", out_dir=tmp_path / "a", year=2024)
    second = png.render_pngs(html, aspect="9:16", out_dir=tmp_path / "b", year=2024)

    assert [path.name for path in first.paths] == [path.name for path in second.paths]
    for left, right in zip(first.paths, second.paths, strict=True):
        before = left.read_bytes()
        after = right.read_bytes()
        if before == after:
            continue
        pytest.fail(
            f"{left.name} 两次渲染不同: "
            f"sha256 {hashlib.sha256(before).hexdigest()[:16]} vs "
            f"{hashlib.sha256(after).hexdigest()[:16]}; {_first_difference(before, after)}"
        )
