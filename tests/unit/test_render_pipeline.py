"""渲染器落地的端到端约定: 单文件、无外链、无占位符、顺序固定。

渲染本身由 Node 侧的构建产物完成, 所以这些用例依赖 `node` 与
`src/recapkits/render/assets/cli.mjs`。两者缺一时跳过而不是失败 ——
纯 Python 环境 (没有装 Node) 仍然应该能跑完其余测试。
"""

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from recapkits.errors import RecapError
from recapkits.render import node
from recapkits.render.pipeline import RenderInput, build_html, load_input, render_document
from recapkits.story.schema import Story, StorySchemaError
from recapkits.story.validate import build_refs, validate_story

FIXTURES = Path(__file__).parent.parent / "fixtures"
STORY = FIXTURES / "story-render.json"

_NODE = node.node_info()
needs_node = pytest.mark.skipif(
    _NODE is None or _NODE.major < node.MIN_NODE_MAJOR or not node.BUNDLE.is_file(),
    reason="需要 Node 22+ 与已构建的 renderer assets",
)


def test_unvalidated_story_never_reaches_bake(tmp_path: Path) -> None:
    """校验不通过时直接报错, 不会烘焙出一个"看起来能用"的结构。"""
    bad = tmp_path / "story.json"
    bad.write_text(
        json.dumps(
            {
                "version": 1,
                "meta": {
                    "year": 2024,
                    "locale": "zh-CN",
                    "theme": "neon",
                    "tone": "deadpan",
                    "tz": "Asia/Shanghai",
                    "build_id": "",
                },
                "cards": [{"id": "c1", "type": "big-number", "copy": {"headline": "共 1234 次"}}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(RecapError, match="NUMBER_NOT_IN_PLACEHOLDER"):
        load_input(bad, str(FIXTURES / "insights.json"))


def test_bad_schema_is_reported_as_recap_error(tmp_path: Path) -> None:
    """结构错误也要变成一句话错误, 不能让 traceback 冒到用户面前。"""
    bad = tmp_path / "story.json"
    bad.write_text('{"version": 2}', encoding="utf-8")

    with pytest.raises(RecapError, match="结构不合法"):
        load_input(bad, str(FIXTURES / "insights.json"))


def test_hyphenated_insight_id_is_referenceable() -> None:
    """回归锁: disc.* 的 id 带日期 (含连字符), 占位符字符集必须放行。"""
    payload = json.loads((FIXTURES / "insights.json").read_text(encoding="utf-8"))
    payload["insights"].append(
        {
            "id": "disc.longest_gap:git:2024:2024-03-10",
            "kind": "disc.longest_gap",
            "sensitivity": "low",
            "headline_fact": {
                "key": "days",
                "label": "空档天数",
                "value": 7,
                "unit": "count",
                "display": "7 天",
            },
            "facts": [
                {
                    "key": "start",
                    "label": "起始日",
                    "value": "2024-03-10",
                    "unit": "date",
                    "display": "2024-03-10",
                }
            ],
        }
    )
    story = Story.from_dict(
        {
            "version": 1,
            "meta": {
                "year": 2024,
                "locale": "zh-CN",
                "theme": "neon",
                "tone": "deadpan",
                "tz": "Asia/Shanghai",
                "build_id": "",
            },
            "cards": [
                {
                    "id": "c1",
                    "type": "big-number",
                    "copy": {"sub": "从 {{disc.longest_gap:git:2024:2024-03-10.start}} 起"},
                    "evidence": ["disc.longest_gap:git:2024:2024-03-10"],
                }
            ],
        }
    )

    errors = validate_story(story, build_refs(payload))

    assert [error.code for error in errors] == []


@needs_node
def test_render_produces_self_contained_html(tmp_path: Path) -> None:
    """单文件: 无外链、无残留占位符、CSS 内联, 且文案真的进去了。"""
    html = render_document(STORY, str(FIXTURES / "insights.json"), aspect="9:16")

    assert "http://" not in html
    assert "https://" not in html
    assert "{{" not in html and "}}" not in html
    assert "<style>" in html
    assert 'class="stage"' in html
    assert "提交总数" in html
    assert "覆盖 46 个活跃日" in html
    assert "62%" in html
    assert "--stage-w:1080;--stage-h:1920" in html


@needs_node
def test_four_by_five_changes_stage_height() -> None:
    """4:5 只换舞台高度, 宽度不变。"""
    html = render_document(STORY, str(FIXTURES / "insights.json"), aspect="4:5")

    assert "--stage-w:1080;--stage-h:1350" in html


@needs_node
def test_renderer_rejects_unbaked_placeholders(tmp_path: Path) -> None:
    """直接把未烘焙的文本交给渲染器: 必须显式失败, 而不是把字面量画出来。"""
    payload = {
        "version": 1,
        "meta": {
            "year": 2024,
            "locale": "zh-CN",
            "theme": "neon",
            "tone": "deadpan",
            "buildId": "b3:x",
        },
        "cards": [
            {"id": "c1", "type": "cover", "copy": {"headline": "{{vol.total:git:2024.events}}"}}
        ],
    }
    story_path = tmp_path / "baked.json"
    story_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [
            node.node_binary(),
            str(node.BUNDLE),
            "--story",
            str(story_path),
            "--out",
            str(tmp_path / "o.html"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 1
    assert "未烘焙" in completed.stderr
    assert "c1" in completed.stderr


@needs_node
def test_unbaked_payload_surfaces_as_recap_error(tmp_path: Path) -> None:
    """Python 侧也要把渲染器的拒绝翻译成一句话错误。"""
    payload = {
        "version": 1,
        "meta": {"year": 2024, "locale": "zh-CN", "theme": "neon", "tone": "d", "buildId": "x"},
        "cards": [{"id": "c1", "type": "cover", "copy": {"headline": "{{a.b}}"}}],
    }

    with pytest.raises(RecapError, match="未烘焙"):
        node.render_html(payload, aspect="9:16", theme="neon")


def test_story_schema_error_type_is_exposed() -> None:
    """StorySchemaError 仍是 ValueError 的子类, 调用方可以按需捕获。"""
    assert issubclass(StorySchemaError, ValueError)


@needs_node
def test_headline_overflow_is_an_error() -> None:
    """放不下的 headline 必须报错, 不能静默截断或悄悄换行挤掉数字。"""
    source = load_input(STORY, str(FIXTURES / "insights.json"))
    card = replace(source.story.cards[1], copy={"headline": "很" * 12})
    broken = RenderInput(story=replace(source.story, cards=[card]), refs=source.refs)

    with pytest.raises(RecapError, match="只允许 1 行"):
        build_html(broken, aspect="9:16")
