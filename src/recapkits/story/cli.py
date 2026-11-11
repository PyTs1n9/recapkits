"""`recap story --check` 的实现: 读 story.json 与 insights.json, 打印结构化错误。"""

import argparse
import json
import sys
from pathlib import Path

from recapkits.errors import RecapError
from recapkits.story.schema import Story, StoryError, StorySchemaError
from recapkits.story.validate import build_refs, validate_story
from recapkits.workspace import load_workspace


def _insights_path(explicit: str | None, story_path: Path) -> Path:
    """找 insights.json: --insights 优先, 其次当前工作区, 最后故事文件同目录。"""
    if explicit:
        return Path(explicit).expanduser()
    workspace = load_workspace()
    if workspace is not None and workspace.out_path.is_file():
        return workspace.out_path
    sibling = story_path.parent / "insights.json"
    if sibling.is_file():
        return sibling
    raise RecapError("未找到 insights.json: 先运行 recap insights, 或用 --insights 指定")


def _load_json(path: Path, label: str) -> dict[str, object]:
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


def _print_errors(errors: list[StoryError], name: str) -> None:
    """一行一条问题, 每条都带位置、实际值、期望值与提示。"""
    print(f"{name} 有 {len(errors)} 处问题:", file=sys.stderr)
    for position, error in enumerate(errors, start=1):
        slot = f" {error.slot}" if error.slot else ""
        print(f"  {position}. [{error.code}] 卡#{error.card_index + 1}{slot}", file=sys.stderr)
        print(f"     得到 {error.got!r}; 期望 {error.expected}", file=sys.stderr)
        print(f"     提示: {error.hint}", file=sys.stderr)


def cmd_story(args: argparse.Namespace) -> int:
    """校验 story.json; 通过返回 0, 有任何错误返回 1。"""
    story_path = Path(args.check).expanduser()
    try:
        story = Story.from_dict(_load_json(story_path, "story.json"))
    except StorySchemaError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    refs = build_refs(_load_json(_insights_path(args.insights, story_path), "insights.json"))
    errors = validate_story(
        story,
        refs,
        allow_sensitive=bool(args.allow_sensitive),
        allow_unknown_names=bool(args.allow_unknown_names),
    )
    if not errors:
        print(f"通过: {story_path.name} 共 {len(story.cards)} 张卡")
        return 0
    _print_errors(errors, story_path.name)
    return 1
