"""文本规则: V2 手写数字、V6 专有名词、V7 因果与诊断。

单独成文, 是因为这里的正则与词表最长, 而 validate.py 只负责调度。
"""

import re

from recapkits.story.schema import InsightRef, StoryError

PLACEHOLDER = re.compile(r"\{\{([^{}]*)\}\}")
YEAR = re.compile(r"\b(19|20)\d{2}\b")
LATIN_DIGITS = re.compile(r"[0-9]+")
FULLWIDTH_DIGITS = re.compile("[\\uff10-\\uff19]+")
ARABIC_INDIC_DIGITS = re.compile("[\\u0660-\\u0669]+")
PERSIAN_DIGITS = re.compile("[\\u06f0-\\u06f9]+")
CHINESE_NUMBER = re.compile(
    r"(第)?([零一二三四五六七八九十百千万亿两]+)(个|天|次|小时|分钟|秒|年|月|日|条|部|首|张|页|倍|成)"
)
ENGLISH_NUMBER = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen"
    r"|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty"
    r"|seventy|eighty|ninety|hundred|thousand|dozen)\b",
    re.IGNORECASE,
)
LATIN_NAME = re.compile(r"\b[A-Z][A-Za-z0-9&'-]*\b")
QUOTED = re.compile(r"[「『“\"《]([^」』”\"》]{1,30})[」』”\"》]")
TOKEN = re.compile(r"[0-9A-Za-z_]+")

#: 这些短语里的"一"是语气, 不是数量。
EXEMPT_PHRASES = ("一天不落",)

#: 因果与诊断词表; 命中即错, 并指出命中的词。
FORBIDDEN = (
    re.compile("导致"),
    re.compile("因为.{0,20}所以"),
    re.compile("说明你"),
    re.compile("证明你"),
    re.compile("你有.{0,10}倾向"),
    re.compile("暴露了"),
    re.compile(r"\bdepressed\b", re.IGNORECASE),
    re.compile(r"\banxious\b", re.IGNORECASE),
    re.compile(r"\bburned out\b", re.IGNORECASE),
    re.compile(r"\baddicted\b", re.IGNORECASE),
)


def _exempt_spans(text: str) -> list[tuple[int, int]]:
    """找出豁免短语在文本中的区间, 用于放过"一天不落"。"""
    spans: list[tuple[int, int]] = []
    for phrase in EXEMPT_PHRASES:
        start = text.find(phrase)
        while start != -1:
            spans.append((start, start + len(phrase)))
            start = text.find(phrase, start + 1)
    return spans


def check_numbers(card_index: int, slot: str, text: str) -> list[StoryError]:
    """V2: 除了年份, 任何手写数字都不允许 -- 数字必须来自占位符。"""
    body = PLACEHOLDER.sub("", text)
    cleaned = YEAR.sub("", body)
    found: list[tuple[str, str]] = []
    for pattern, label in (
        (FULLWIDTH_DIGITS, "全角数字"),
        (ARABIC_INDIC_DIGITS, "阿拉伯-印度数字"),
        (PERSIAN_DIGITS, "波斯数字"),
        (LATIN_DIGITS, "阿拉伯数字"),
    ):
        found.extend((match.group(0), label) for match in pattern.finditer(cleaned))

    spans = _exempt_spans(text)
    for match in CHINESE_NUMBER.finditer(text):
        if match.group(1) == "第":
            continue
        if any(start <= match.start() and match.end() <= end for start, end in spans):
            continue
        found.append((match.group(0), "中文数词"))
    found.extend((match.group(0), "英文数词") for match in ENGLISH_NUMBER.finditer(body))

    return [
        StoryError(
            "NUMBER_NOT_IN_PLACEHOLDER",
            card_index,
            slot,
            got,
            "用 {{insight.fact}} 引用数字",
            f"这是{label}; 数字只能来自占位符, 或删掉它",
        )
        for got, label in found
    ]


def _collect_names(refs: list[InsightRef]) -> tuple[set[str], set[str]]:
    strings: set[str] = set()
    tokens: set[str] = set()
    for ref in refs:
        for text in [*ref.facts.values(), *ref.labels]:
            strings.add(text.lower())
            tokens.update(token.lower() for token in TOKEN.findall(text))
    return strings, tokens


def check_names(
    card_index: int, slot: str, text: str, allowed: list[str], refs: dict[str, InsightRef]
) -> list[StoryError]:
    """V6: 文案里的专有名词必须能在被引洞察的事实或标签里找到。"""
    strings, tokens = _collect_names([refs[key] for key in allowed if key in refs])
    errors: list[StoryError] = []
    hint = "换成事实里的名字, 或加 --allow-unknown-names"

    for match in LATIN_NAME.finditer(PLACEHOLDER.sub("", text)):
        word = match.group(0)
        if word.lower() not in tokens:
            errors.append(
                StoryError(
                    "NAME_NOT_IN_EVIDENCE",
                    card_index,
                    slot,
                    word,
                    "被引洞察 facts[].display 或 label 里的词",
                    hint,
                )
            )
    for match in QUOTED.finditer(text):
        content = match.group(1).strip()
        if any(content.lower() in item for item in strings):
            continue
        content_tokens = set(TOKEN.findall(content.lower()))
        if content_tokens and content_tokens <= tokens:
            continue
        errors.append(
            StoryError(
                "NAME_NOT_IN_EVIDENCE",
                card_index,
                slot,
                content,
                "被引洞察 facts[].display 或 label 里的词",
                hint,
            )
        )
    return errors


def check_causality(card_index: int, slot: str, text: str) -> list[StoryError]:
    """V7: 数据只描述行为, 不解释人。"""
    return [
        StoryError(
            "FORBIDDEN_CAUSALITY",
            card_index,
            slot,
            match.group(0),
            "描述发生了什么, 不解释为什么",
            "删掉因果/诊断表述, 只保留可复算的事实",
        )
        for pattern in FORBIDDEN
        if (match := pattern.search(text))
    ]
