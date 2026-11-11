"""读 story.json / insights.json 并定位数据源。

单独成文, 是因为 `story --check` 与 `render` 都需要同一套查找顺序:
`--insights` → 故事文件同目录 → 当前工作区。同目录优先, 是为了让 fixture 自成一体。
"""

import json
from pathlib import Path

from recapkits.errors import RecapError
from recapkits.workspace import load_workspace


def load_json(path: Path, label: str) -> dict[str, object]:
    """读一个顶层为对象的 JSON, 出错时给出行号。"""
    if not path.is_file():
        raise RecapError(f"{label} 不存在: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RecapError(f"{label} 不是合法 JSON: {exc.msg} (第 {exc.lineno} 行)") from exc
    if not isinstance(data, dict):
        raise RecapError(f"{label} 顶层必须是对象")
    return data


def resolve_insights_path(explicit: str | None, story_path: Path) -> Path:
    """找 insights.json: --insights 优先, 其次故事文件同目录, 最后当前工作区。"""
    if explicit:
        return Path(explicit).expanduser()
    sibling = story_path.parent / "insights.json"
    if sibling.is_file():
        return sibling
    workspace = load_workspace()
    if workspace is not None and workspace.out_path.is_file():
        return workspace.out_path
    raise RecapError("未找到 insights.json: 先运行 recap insights, 或用 --insights 指定")
