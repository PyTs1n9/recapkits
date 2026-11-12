"""story.json 的结构定义, 以及校验用的错误/引用类型。

这里只负责解析成 dataclass, 不做语义校验 —— 语义在 validate.py 与 rules.py。

`allow_sensitive` 不是字段, 因此写进 JSON 也不会被读到: 授权只认 CLI 参数。
"""

from dataclasses import dataclass, field
from typing import Any

from recapkits.insights.model import Series

CARD_TYPES = ("cover", "big-number", "ranking", "heatmap", "clock", "summary-grid")
COPY_SLOTS = ("headline", "sub", "kicker")


class StorySchemaError(ValueError):
    """结构不合法: 缺字段、类型不对、枚举越界。"""


@dataclass(frozen=True)
class StoryError:
    """一处校验问题; hint 决定 agent 是自愈还是放弃, 所以不是可选项。"""

    code: str
    card_index: int
    slot: str | None
    got: str
    expected: str
    hint: str

    def as_dict(self) -> dict[str, Any]:
        """展开成可直接打印或序列化的结构。"""
        return {
            "code": self.code,
            "card_index": self.card_index,
            "slot": self.slot,
            "got": self.got,
            "expected": self.expected,
            "hint": self.hint,
        }


@dataclass(frozen=True)
class RefFact:
    """被引洞察里的一个事实; 渲染 ranking / summary-grid 需要结构化字段。"""

    key: str
    label: str
    value: float | str
    unit: str | None
    display: str


@dataclass(frozen=True)
class InsightRef:
    """校验只需要洞察的这几样: 身份、类型、敏感度、事实与标签。

    `headline` 是被引洞察 `headline_fact.display` 的原文, 渲染 `big-number` 时
    作为巨型数字使用 —— 它已经过校验, 可以直接进产物。

    `fact_list` 保留事实的完整结构与顺序, `facts` 只保留 key -> display 的映射,
    供占位符校验使用; 两者来自同一份输入, 不允许各算一套。
    """

    id: str
    kind: str
    sensitivity: str
    facts: dict[str, str]
    labels: list[str]
    headline: str = ""
    fact_list: tuple[RefFact, ...] = ()
    series: Series | None = None


def format_errors(errors: list[StoryError]) -> str:
    """把错误列表排成逐行可读的文本; CLI 与 render 共用, 免得两处各写一遍格式。"""
    lines = [f"有 {len(errors)} 处问题:"]
    for position, error in enumerate(errors, start=1):
        slot = f" {error.slot}" if error.slot else ""
        lines.append(f"  {position}. [{error.code}] 卡#{error.card_index + 1}{slot}")
        lines.append(f"     得到 {error.got!r}; 期望 {error.expected}")
        lines.append(f"     提示: {error.hint}")
    return "\n".join(lines)


def _field(mapping: dict[str, Any], key: str, where: str) -> Any:
    if key not in mapping:
        raise StorySchemaError(f"{where} 缺少字段 {key}")
    return mapping[key]


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str):
        raise StorySchemaError(f"{where} 必须是字符串, 收到 {type(value).__name__}")
    return value


def _object(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StorySchemaError(f"{where} 必须是对象, 收到 {type(value).__name__}")
    return value


@dataclass(frozen=True)
class Meta:
    """故事元信息; build_id 把故事绑回具体的 insights.json。"""

    year: int
    locale: str
    theme: str
    tone: str
    tz: str
    build_id: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Meta":
        year = _field(raw, "year", "meta")
        if not isinstance(year, int) or isinstance(year, bool):
            raise StorySchemaError("meta.year 必须是整数")
        return cls(
            year=year,
            locale=_text(_field(raw, "locale", "meta"), "meta.locale"),
            theme=_text(_field(raw, "theme", "meta"), "meta.theme"),
            tone=_text(_field(raw, "tone", "meta"), "meta.tone"),
            tz=_text(_field(raw, "tz", "meta"), "meta.tz"),
            build_id=_text(raw.get("build_id", ""), "meta.build_id"),
        )


@dataclass(frozen=True)
class Card:
    """一张卡: 类型 + 文案槽位 + 证据链。"""

    id: str
    type: str
    copy: dict[str, str]
    insight: str | None = None
    evidence: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any], index: int) -> "Card":
        where = f"cards[{index}]"
        card_type = _text(_field(raw, "type", where), f"{where}.type")
        if card_type not in CARD_TYPES:
            raise StorySchemaError(f"{where}.type 只能是 {', '.join(CARD_TYPES)}, 收到 {card_type}")

        copy: dict[str, str] = {}
        for slot, value in _object(_field(raw, "copy", where), f"{where}.copy").items():
            if slot not in COPY_SLOTS:
                raise StorySchemaError(f"{where}.copy 出现未知槽位 {slot}")
            copy[slot] = _text(value, f"{where}.copy.{slot}")

        evidence = raw.get("evidence", [])
        if not isinstance(evidence, list) or any(not isinstance(item, str) for item in evidence):
            raise StorySchemaError(f"{where}.evidence 必须是字符串数组")

        insight = raw.get("insight")
        if insight is not None and not isinstance(insight, str):
            raise StorySchemaError(f"{where}.insight 必须是字符串")

        return cls(
            id=_text(_field(raw, "id", where), f"{where}.id"),
            type=card_type,
            copy=copy,
            insight=insight,
            evidence=list(evidence),
        )


@dataclass(frozen=True)
class Story:
    """一整份故事; version 目前只接受 1。"""

    version: int
    meta: Meta
    cards: list[Card]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Story":
        version = _field(raw, "version", "story")
        if version != 1:
            raise StorySchemaError(f"story.version 只支持 1, 收到 {version!r}")
        cards = _field(raw, "cards", "story")
        if not isinstance(cards, list) or not cards:
            raise StorySchemaError("story.cards 必须是非空数组")
        return cls(
            version=1,
            meta=Meta.from_dict(_object(_field(raw, "meta", "story"), "meta")),
            cards=[
                Card.from_dict(_object(item, f"cards[{index}]"), index)
                for index, item in enumerate(cards)
            ],
        )
