"""`recap story --check` 的实现: 读 story.json 与 insights.json, 打印结构化错误。"""

import argparse
import sys
from pathlib import Path

from recapkits.story.load import load_json, resolve_insights_path
from recapkits.story.schema import Story, StorySchemaError, format_errors
from recapkits.story.validate import build_refs, validate_story


def cmd_story(args: argparse.Namespace) -> int:
    """校验 story.json; 通过返回 0, 有任何错误返回 1。"""
    story_path = Path(args.check).expanduser()
    try:
        story = Story.from_dict(load_json(story_path, "story.json"))
    except StorySchemaError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    refs = build_refs(load_json(resolve_insights_path(args.insights, story_path), "insights.json"))
    errors = validate_story(
        story,
        refs,
        allow_sensitive=bool(args.allow_sensitive),
        allow_unknown_names=bool(args.allow_unknown_names),
    )
    if not errors:
        print(f"通过: {story_path.name} 共 {len(story.cards)} 张卡")
        return 0
    print(f"{story_path.name} {format_errors(errors)}", file=sys.stderr)
    return 1
