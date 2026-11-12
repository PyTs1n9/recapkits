"""第 1、2 阶段的文本变换, 以及它们留下的账。

`Audit` 放在这里而不是 `apply`, 是因为它只记文本变换的计数: 结构化 PII 的类别
与样本、抑制表的命中、实体按类别的名单。报告模块只读它, 不需要认识遍历逻辑。
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from recapkits.redact import pii

REMOVED = pii.REMOVED

#: 抑制表的文件名; redact 与 agent 载荷读的是同一份。
SUPPRESSION_FILE = "redact.txt"


@dataclass
class Audit:
    """审计所需的全部计数与样本; 样本是原文, 只在 TTY 上打印。"""

    pii_counts: dict[str, int] = field(default_factory=dict)
    pii_samples: dict[str, list[str]] = field(default_factory=dict)
    suppressed: dict[str, int] = field(default_factory=dict)
    entity_kinds: dict[str, list[str]] = field(default_factory=dict)
    removed: list[str] = field(default_factory=list)
    pseudonyms: int = 0

    @property
    def entity_total(self) -> int:
        return sum(len(names) for names in self.entity_kinds.values())


class Suppressor:
    """抑制表: 一次编译, 长词先匹配, 单遍替换。

    单遍很重要: 替换出来的标记不该被另一条词再匹配一次。交替式按长度降序排列,
    所以「张三丰」一定先于「张三」命中。
    """

    def __init__(self, words: list[str]) -> None:
        self.words = words
        self.hits: dict[str, int] = {}
        self._by_lower = {word.lower(): word for word in words}
        if words:
            alternatives = "|".join(
                re.escape(word) for word in sorted(words, key=len, reverse=True)
            )
            self._pattern: re.Pattern[str] | None = re.compile(alternatives, re.IGNORECASE)
        else:
            self._pattern = None

    def matches(self, text: str) -> list[str]:
        """命中的词 (按表里的拼写); 只查不计数, 供实体整体移除时记账。"""
        if self._pattern is None:
            return []
        return [self._by_lower[match.group(0).lower()] for match in self._pattern.finditer(text)]

    def record(self, words: list[str]) -> None:
        for word in words:
            self.hits[word] = self.hits.get(word, 0) + 1

    def hits_on(self, text: str) -> bool:
        return bool(self.matches(text))

    def apply(self, text: str) -> str:
        if self._pattern is None:
            return text

        def replace(match: re.Match[str]) -> str:
            word = self._by_lower[match.group(0).lower()]
            self.hits[word] = self.hits.get(word, 0) + 1
            return REMOVED

        return self._pattern.sub(replace, text)


def read_words(path: Path) -> list[str]:
    """`./redact.txt`: 一行一个词, `#` 开头忽略, 大小写不敏感; 去重保序。"""
    if not path.is_file():
        return []
    words: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        word = line.strip()
        key = word.lower()
        if not word or word.startswith("#") or key in seen:
            continue
        seen.add(key)
        words.append(word)
    return words


def scrub(text: str, suppressor: Suppressor, audit: Audit) -> str:
    """第 1、2 阶段: 结构化 PII, 再抑制表。"""
    scrubbed, rulings = pii.redact(text)
    for ruling in rulings:
        audit.pii_counts[ruling.category] = audit.pii_counts.get(ruling.category, 0) + 1
        samples = audit.pii_samples.setdefault(ruling.category, [])
        if ruling.sample not in samples and len(samples) < 5:
            samples.append(ruling.sample)
    return suppressor.apply(scrubbed)


def replace_entities(text: str, replacements: dict[str, str]) -> str:
    """按长度降序替换; ASCII 名字要整词匹配, 中文名没有词边界可用。"""
    for name in sorted(replacements, key=len, reverse=True):
        target = replacements[name]
        if not name.strip() or target == name:
            continue
        if name.isascii():
            pattern = re.compile(
                r"(?<![0-9A-Za-z_])" + re.escape(name) + r"(?![0-9A-Za-z_])", re.IGNORECASE
            )
        else:
            pattern = re.compile(re.escape(name), re.IGNORECASE)
        text = pattern.sub(target, text)
    return text
