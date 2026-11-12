"""调用 Node 侧的渲染器: 输入是已烘焙的 JSON, 输出是单文件 HTML 字符串。

环境里必须能找到 `node`。这里的错误信息要说清三件事: 需要什么版本、当前检测到
什么、以及不装 Node 还能做什么。因为"渲染失败"这种话对用户没有信息量。

**快速失败是契约的一部分。** `require_node()` 必须在读取输入、导入数据之前调用:
一条跑了三分钟解析、写完 61 MB 数据库才在最后一步报"找不到 node"的命令, 比直接
拒绝更糟。
"""

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from recapkits.errors import RecapError

#: 构建产物目录; 与 `renderer/dist/` 由 scripts/sync-renderer.py 对齐。
ASSETS = Path(__file__).parent / "assets"
BUNDLE = ASSETS / "cli.mjs"

#: D2 的运行时下限; 低于它就明确报错, 不要等到 bundle 解析失败。
MIN_NODE_MAJOR = 22
_VERSION = re.compile(r"v?(\d+)\.")


@dataclass(frozen=True)
class NodeInfo:
    """一次 node 探测的结果; `major=0` 表示找到了文件但读不出版本。"""

    path: str
    version: str
    major: int


def node_info() -> NodeInfo | None:
    """找到 node 并读出版本; 找不到时返回 None, 不做任何写入。"""
    path = shutil.which("node")
    if path is None:
        return None
    completed = subprocess.run(
        [path, "--version"], capture_output=True, text=True, encoding="utf-8", check=False
    )
    version = (completed.stdout or completed.stderr or "").strip() or "unknown"
    match = _VERSION.match(version)
    return NodeInfo(path=path, version=version, major=int(match.group(1)) if match else 0)


def require_node() -> NodeInfo:
    """确认 node 存在且版本够用; 否则抛出一句可操作的话。

    这是命令路径上的第一道闸门: 调用方必须在解析任何输入之前调用它。
    """
    info = node_info()
    if info is None:
        raise RecapError(
            "渲染需要 Node 22+。检测未通过：找不到 node。\n"  # noqa: RUF001
            "装好后再跑一次；或先用 `recap insights` 拿到数据结论（不需要 Node）。"  # noqa: RUF001
        )
    if info.major < MIN_NODE_MAJOR:
        raise RecapError(
            f"渲染需要 Node 22+。检测未通过：当前 {info.version}（{info.path}）。\n"  # noqa: RUF001
            "升级后再跑一次；或先用 `recap insights` 拿到数据结论（不需要 Node）。"  # noqa: RUF001
        )
    return info


def node_binary() -> str:
    """找到 node; 找不到或版本过低就给出可操作的错误。"""
    return require_node().path


def render_html(payload: dict[str, Any], *, aspect: str, theme: str) -> str:
    """把已烘焙的故事渲染成 HTML; 渲染器的报错原样传给用户。"""
    if not BUNDLE.is_file():
        raise RecapError(
            f"渲染器未构建: 缺少 {BUNDLE}\n"
            "构建一次即可: pnpm --dir renderer install && pnpm --dir renderer build "
            "&& python scripts/sync-renderer.py"
        )

    with tempfile.TemporaryDirectory(prefix="recapkits-render-") as tmp:
        story_path = Path(tmp) / "story.json"
        out_path = Path(tmp) / "recap.html"
        story_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        completed = subprocess.run(
            [
                node_binary(),
                str(BUNDLE),
                "--story",
                str(story_path),
                "--out",
                str(out_path),
                "--aspect",
                aspect,
                "--theme",
                theme,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip() or "未知错误"
            raise RecapError(f"渲染失败: {detail}")
        return out_path.read_text(encoding="utf-8")
