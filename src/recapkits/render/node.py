"""调用 Node 侧的渲染器: 输入是已烘焙的 JSON, 输出是单文件 HTML 字符串。

环境里必须能找到 `node`。这里的错误信息要说清两件事: 需要什么、去哪儿装,
因为"渲染失败"这种话对用户没有信息量。
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from recapkits.errors import RecapError

#: 构建产物目录; 与 `renderer/dist/` 由 scripts/sync-renderer.py 对齐。
ASSETS = Path(__file__).parent / "assets"
BUNDLE = ASSETS / "cli.mjs"


def node_binary() -> str:
    """找到 node; 找不到就给出可操作的错误。"""
    node = shutil.which("node")
    if node is None:
        raise RecapError("渲染需要 Node 22+: 装好 node 后重试 (HTML 由 renderer/dist/cli.mjs 产出)")
    return node


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
