"""SKILL.md 的内容契约: 长度、小节、错误码全覆盖、语气、示例可校验。

**长度是硬约束**: 计划 §6.7 的坑是「skill 写太长被忽略」, 一份会被跳过的 skill
等于没有。**错误码覆盖是测试而不是文档承诺**: 校验器新增一个码而 skill 没跟上,
agent 会反复犯同一个错, 而我们只会在用户抱怨时才知道。
"""

import ast
import json
import re
from pathlib import Path

from recapkits.skill import read_text
from recapkits.story.rules import check_causality, check_numbers
from recapkits.story.schema import Story
from recapkits.story.validate import build_refs, validate_story

FIXTURES = Path(__file__).parent.parent / "fixtures"
SRC = Path(__file__).resolve().parent.parent.parent / "src"

MAX_LINES = 160
MAX_BYTES = 8 * 1024

SECTIONS = (
    "## 你要做什么",
    "## 循环",
    "## 七条硬规则",
    "## 卡型速查",
    "## 五种语气",
    "## 两遍法",
    "## 隐私",
    "## 错误码",
    "## 一个最小故事",
)

TONES = ("deadpan", "warm", "dry", "cinematic", "playful")

CODE_ROW = re.compile(r"^\|\s*`([A-Z][A-Z0-9_]+)`", re.MULTILINE)
JSON_BLOCK = re.compile(r"```json\n(.*?)```", re.DOTALL)


def codes_in_source() -> set[str]:
    """扫 `src/` 里所有 `StoryError("CODE", ...)` 的第一个参数。

    用 AST 而不是正则: 调用跨多行 (validate.py 里每个都是), 正则要么漏要么误伤
    注释里的示例。
    """
    codes: set[str] = set()
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if getattr(node.func, "id", None) != "StoryError" or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                codes.add(first.value)
    return codes


def test_skill_stays_within_budget() -> None:
    raw = read_text().encode("utf-8")

    assert raw.count(b"\r") == 0
    assert len(raw) <= MAX_BYTES
    assert read_text().count("\n") <= MAX_LINES


def test_frontmatter_names_the_skill() -> None:
    text = read_text()

    assert text.startswith("---\n")
    assert "name: recapkits" in text.split("---")[1]
    assert "description:" in text.split("---")[1]


def test_required_sections_are_present() -> None:
    text = read_text()

    assert [section for section in SECTIONS if section not in text] == []


def test_every_validation_code_is_documented() -> None:
    """错误码表必须与校验器一一对应: 不多写, 也不漏写。"""
    text = read_text()
    documented = set(CODE_ROW.findall(text))
    actual = codes_in_source()

    assert actual, "没有扫到 StoryError 字面量: AST 匹配失效"
    assert sorted(actual - documented) == []
    assert sorted(documented - actual) == []


def test_all_five_tones_are_taught() -> None:
    text = read_text()

    assert [tone for tone in TONES if f"`{tone}`" not in text] == []


def test_example_cards_pass_the_validator() -> None:
    """示例不是散文: 它必须真的能过 V1-V7, 否则 agent 抄的就是错的。"""
    block = JSON_BLOCK.search(read_text())
    assert block is not None
    payload = json.loads(block.group(1))
    story = Story.from_dict(payload)
    refs = build_refs(json.loads((FIXTURES / "insights.json").read_text(encoding="utf-8")))

    assert validate_story(story, refs) == []


def test_example_copy_has_no_hand_written_numbers_or_causality() -> None:
    """两条最常犯的错, 在示例里就不该出现 (示例会被照抄)。"""
    block = JSON_BLOCK.search(read_text())
    assert block is not None
    cards = json.loads(block.group(1))["cards"]

    offenders = [
        (slot, error.code)
        for index, card in enumerate(cards)
        for slot, text in card["copy"].items()
        for error in (*check_numbers(index, slot, text), *check_causality(index, slot, text))
    ]

    assert offenders == []
