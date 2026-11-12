"""ffmpeg 探测: 与 `node.py::require_node()` 同构的快速失败。

ffmpeg 按 node 的待遇处理 —— 系统依赖, 不是 pip 依赖。不引入 `imageio-ffmpeg`:
那是把一份二进制塞进依赖, 与"运行时零第三方包"的约束直接冲突。

`-fps_mode` 需要 ffmpeg >= 5.1 (本机 8.1.1, ubuntu-latest 高于此)。只报版本,
不为老版本维护 `-vsync` 分支: 少一条分支就少一处没人测的代码。
"""

import re
import shutil
import subprocess
from dataclasses import dataclass

from recapkits.errors import RecapError

#: 运行期下限; `-fps_mode` 是 5.1 引入的。
MIN_FFMPEG = (5, 1)
_VERSION = re.compile(r"ffmpeg version (\d+\.\d+(?:\.\d+)?)")
_PARTS = re.compile(r"(\d+)\.(\d+)")


@dataclass(frozen=True)
class FfmpegInfo:
    """一次 ffmpeg 探测的结果; `major=0` 表示找到了文件但读不出版本。"""

    path: str
    version: str
    major: int
    minor: int

    def __str__(self) -> str:
        return f"{self.version}  {self.path}"


def ffmpeg_info() -> FfmpegInfo | None:
    """找到 ffmpeg 并读出版本; 找不到时返回 None, 不做任何写入。"""
    path = shutil.which("ffmpeg")
    if path is None:
        return None
    completed = subprocess.run(
        [path, "-version"], capture_output=True, text=True, encoding="utf-8", check=False
    )
    first = (completed.stdout or "").splitlines()[0] if completed.stdout else ""
    match = _VERSION.search(first)
    if match is None:
        return FfmpegInfo(path=path, version="unknown", major=0, minor=0)
    parts = _PARTS.match(match.group(1))
    return FfmpegInfo(
        path=path,
        version=match.group(1),
        major=int(parts.group(1)) if parts else 0,
        minor=int(parts.group(2)) if parts else 0,
    )


def require_ffmpeg() -> FfmpegInfo:
    """确认 ffmpeg 存在且版本够用; 否则抛出一句可操作的话。

    这是 mp4 路径的第一道闸门: 调用方必须在读取 `story.json` 之前调用它。
    """
    info = ffmpeg_info()
    if info is None:
        raise RecapError(
            "视频输出需要 ffmpeg 5.1+。检测未通过：找不到 ffmpeg。\n"  # noqa: RUF001
            "装好后再跑一次；或改用 recap render --format png（不需要 ffmpeg）。"  # noqa: RUF001
        )
    if (info.major, info.minor) < MIN_FFMPEG:
        raise RecapError(
            f"视频输出需要 ffmpeg 5.1+。检测未通过：当前 {info.version}（{info.path}）。\n"  # noqa: RUF001
            "升级后再跑一次；-fps_mode 参数需要 5.1 及以上。"  # noqa: RUF001
        )
    return info
