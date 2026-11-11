"""`recap render` 的内部顺序: **load → validate (V1-V7) → bake → render**。

四步的顺序是固定的, 不是实现细节:
- validate 必须在 bake 之前, 否则报错信息只能指向"替换后的字符串", 用户无从修起;
- bake 必须在 render 之前, 否则渲染器会看见占位符, 于是它得再实现一遍占位符语法;
- render 只接收已烘焙的字符串, 因此它对任何输入都是安全的。

`render` 阶段不认识占位符这件事, 让"校验通过但页面显示 `{{...}}`"这个失败模式
在结构上不可能发生。
"""

from dataclasses import dataclass
from pathlib import Path

from recapkits.errors import RecapError
from recapkits.render import node
from recapkits.story.bake import bake
from recapkits.story.load import load_json, resolve_insights_path
from recapkits.story.schema import (
    InsightRef,
    Story,
    StorySchemaError,
    format_errors,
)
from recapkits.story.validate import build_refs, validate_story


@dataclass(frozen=True)
class RenderInput:
    """一份通过校验的故事, 连同它的洞察引用表。"""

    story: Story
    refs: dict[str, InsightRef]


def load_input(
    story_path: Path,
    insights_path: str | None = None,
    *,
    allow_sensitive: bool = False,
    allow_unknown_names: bool = False,
) -> RenderInput:
    """load + validate; 任何一处不通过都抛 `RecapError`, 不带病往下走。"""
    try:
        story = Story.from_dict(load_json(story_path, "story.json"))
    except StorySchemaError as exc:
        raise RecapError(f"story.json 结构不合法: {exc}") from exc

    refs = build_refs(load_json(resolve_insights_path(insights_path, story_path), "insights.json"))
    errors = validate_story(
        story,
        refs,
        allow_sensitive=allow_sensitive,
        allow_unknown_names=allow_unknown_names,
    )
    if errors:
        raise RecapError(f"{story_path.name} 未通过校验, 不能出图:\n{format_errors(errors)}")
    return RenderInput(story=story, refs=refs)


def build_html(source: RenderInput, *, aspect: str) -> str:
    """bake + render; 顺序与模块文档一致。"""
    payload = bake(source.story, source.refs)
    return node.render_html(payload, aspect=aspect, theme=source.story.meta.theme)


def render_document(
    story_path: Path,
    insights_path: str | None = None,
    *,
    aspect: str = "9:16",
    allow_sensitive: bool = False,
    allow_unknown_names: bool = False,
) -> str:
    """一次跑完四步; CLI 与 preview 共用, 保证两边看到的产物完全一致。"""
    source = load_input(
        story_path,
        insights_path,
        allow_sensitive=allow_sensitive,
        allow_unknown_names=allow_unknown_names,
    )
    return build_html(source, aspect=aspect)
