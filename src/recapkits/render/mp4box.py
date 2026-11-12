"""MP4 顶层 box 的最小解析: 只回答四个问题, 不做完整解码。

    - `moov` 是否在 `mdat` 之前 (`+faststart` 生效, 手机上拖进度条才不先卡一下)
    - `mvhd` 的 timescale / duration 是否与时间轴一致 (编码有没有丢帧)
    - `tkhd` 的宽高是否就是 1080x1920 (yuv420p 的偶数约束不许改分辨率)
    - `udta` 里是否真的有元数据条目, 以及全文是否含 `encoder` / `©too`

关于最后一条: ffmpeg 8.1.1 的 mp4 muxer **无条件**写一个空的
`udta/meta/hdlr(mdirappl)/ilst` 容器, 任何 `-map_metadata -1` 组合都去不掉;
删掉它需要重写 `stco` 的 chunk 偏移 (moov 在 mdat 之前), 代价远大于收益。
所以断言落在"容器里没有条目", 而不是"没有容器" —— 空的容器不携带路径或版本。

写法对齐 `png.py::image_size`: 只读需要的 box, 不做完整解码。不引入 ffprobe ——
一个"检查产物结构"的动作不该再依赖第二个外部命令。
"""

import struct
from dataclasses import dataclass

from recapkits.errors import RecapError

#: 顶层 box 里必须出现的两个; 其余 (free / mdat 之外的) 不参与判定。
REQUIRED = ("ftyp", "moov", "mdat")

#: 元数据标记; `©too` 是 ffmpeg 写 encoder 标签时用的键。
METADATA_MARKERS = (b"encoder", b"\xa9too")


@dataclass(frozen=True)
class Mp4Info:
    """产物结构的只读快照; 判定在 `verify()` 里, 解析本身不抛业务错误。"""

    boxes: tuple[str, ...]
    timescale: int
    duration: float
    width: int
    height: int
    udta_items: int
    has_metadata: bool


def _walk(data: bytes, start: int, end: int) -> list[tuple[str, int, int]]:
    """把一个区间切成 box; 返回 (类型, 负载起点, box 终点)。"""
    boxes: list[tuple[str, int, int]] = []
    position = start
    while position + 8 <= end:
        size = struct.unpack(">I", data[position : position + 4])[0]
        kind = data[position + 4 : position + 8].decode("latin-1")
        header = 8
        if size == 1:
            if position + 16 > end:
                raise RecapError(f"MP4 box {kind!r} 的 largesize 越界")
            size = struct.unpack(">Q", data[position + 8 : position + 16])[0]
            header = 16
        elif size == 0:
            size = end - position
        if size < header or position + size > end:
            raise RecapError(f"MP4 box {kind!r} 声明 {size} 字节, 超出文件范围")
        boxes.append((kind, position + header, position + size))
        position += size
    return boxes


def _mvhd(data: bytes, start: int) -> tuple[int, int]:
    """mvhd 的 (timescale, 原始 duration); version 0/1 的字段偏移不同。"""
    version = data[start]
    if version == 0:
        timescale = struct.unpack(">I", data[start + 12 : start + 16])[0]
        duration = struct.unpack(">I", data[start + 16 : start + 20])[0]
    elif version == 1:
        timescale = struct.unpack(">I", data[start + 20 : start + 24])[0]
        duration = struct.unpack(">Q", data[start + 24 : start + 32])[0]
    else:
        raise RecapError(f"MP4 mvhd 的版本 {version} 不受支持")
    return timescale, duration


def _tkhd_size(data: bytes, start: int) -> tuple[int, int]:
    """tkhd 末尾的宽高, 16.16 定点; 取整到像素。"""
    version = data[start]
    offset = 76 if version == 0 else 88
    width = struct.unpack(">I", data[start + offset : start + offset + 4])[0]
    height = struct.unpack(">I", data[start + offset + 4 : start + offset + 8])[0]
    return round(width / 65536), round(height / 65536)


def _udta_items(data: bytes, children: list[tuple[str, int, int]]) -> int:
    """udta -> meta -> ilst 里的条目数; ffmpeg 的空容器返回 0。

    `meta` 是 FullBox (version/flags 四字节), 子 box 从 +4 开始。
    """
    udta = next(((kind, start, end) for kind, start, end in children if kind == "udta"), None)
    if udta is None:
        return 0
    _, start, end = udta
    items = 0
    for kind, meta_start, meta_end in _walk(data, start, end):
        if kind != "meta":
            continue
        for name, ilst_start, ilst_end in _walk(data, meta_start + 4, meta_end):
            if name == "ilst":
                items += len(_walk(data, ilst_start, ilst_end))
    return items


def parse(data: bytes) -> Mp4Info:
    """解析顶层结构; 缺 moov / mvhd / tkhd 时直接报错。"""
    top = _walk(data, 0, len(data))
    order = tuple(kind for kind, _, _ in top)
    for kind in REQUIRED:
        if kind not in order:
            raise RecapError(f"MP4 缺少 {kind} box: 产物不完整")

    moov = next(((kind, start, end) for kind, start, end in top if kind == "moov"), None)
    if moov is None:  # pragma: no cover - REQUIRED 已经挡住
        raise RecapError("MP4 缺少 moov box")
    _, moov_start, moov_end = moov
    children = _walk(data, moov_start, moov_end)
    by_kind = {kind: (start, end) for kind, start, end in children}

    if "mvhd" not in by_kind:
        raise RecapError("MP4 的 moov 里没有 mvhd: 读不出时长")
    timescale, raw_duration = _mvhd(data, by_kind["mvhd"][0])
    if timescale <= 0:
        raise RecapError(f"MP4 的 mvhd.timescale 是 {timescale}")

    width = height = 0
    for kind, start, end in children:
        if kind != "trak":
            continue
        track = {
            name: (inner_start, inner_end)
            for name, inner_start, inner_end in _walk(data, start, end)
        }
        if "tkhd" in track:
            width, height = _tkhd_size(data, track["tkhd"][0])
            break
    if width <= 0 or height <= 0:
        raise RecapError("MP4 的 trak 里没有可用的 tkhd 宽高")

    has_udta = any(kind == "udta" for kind, _, _ in children) or any(
        kind == "udta" for kind, _, _ in top
    )
    items = _udta_items(data, children) if has_udta else 0
    return Mp4Info(
        boxes=order,
        timescale=timescale,
        duration=raw_duration / timescale,
        width=width,
        height=height,
        udta_items=items,
        has_metadata=any(marker in data for marker in METADATA_MARKERS),
    )


def verify(
    info: Mp4Info,
    *,
    seconds: float,
    width: int,
    height: int,
    frame_seconds: float,
) -> None:
    """四条结构断言; 任何一条不成立都抛 `RecapError`, 不产出"看起来能播"的文件。"""
    problems: list[str] = []
    order = info.boxes
    if order.index("moov") > order.index("mdat"):
        problems.append("moov 在 mdat 之后: +faststart 没生效, 手机拖进度条会先卡一下")
    if abs(info.duration - seconds) > frame_seconds + 1e-6:
        problems.append(
            f"时长 {info.duration:.3f}s 与时间轴 {seconds:.3f}s 相差超过 1 帧 "
            f"({frame_seconds:.3f}s): 编码丢帧, 或帧率没归到目标值"
        )
    if (info.width, info.height) != (width, height):
        problems.append(
            f"分辨率 {info.width}x{info.height}, 应为 {width}x{height}: "
            "yuv420p 的偶数约束不该改动舞台尺寸"
        )
    if info.udta_items or info.has_metadata:
        problems.append(f"元数据没清干净: udta 条目 {info.udta_items} 条; 检查 -map_metadata")
    if problems:
        detail = "\n".join(f"  - {line}" for line in problems)
        raise RecapError(f"MP4 结构自检未通过:\n{detail}")
