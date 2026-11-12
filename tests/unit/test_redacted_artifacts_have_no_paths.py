"""脱敏产物可能被单独分享: 全部字符串值里不得出现 URL、绝对路径或家目录。

这条不是"扫一遍看看": 先往输入里塞一个 URL 与三条路径, 再断言产物里一个都不剩。
否则测试只能证明 fixture 本来就很干净。
"""

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from recapkits.redact.apply import Redaction, redact_pair
from recapkits.redact.pseudonym import Book

FIXTURES = Path(__file__).parent.parent / "fixtures"
URL = re.compile(r"https?://", re.IGNORECASE)
DRIVE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
HOME = re.compile(r"(?:/Users/|/home/|\\Users\\)")
TILDE = re.compile(r"(?:^|\s)~[/\\]")


def strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def redacted() -> Redaction:
    insights = json.loads((FIXTURES / "insights.json").read_text(encoding="utf-8"))
    story = json.loads((FIXTURES / "story-render.json").read_text(encoding="utf-8"))
    story["cards"][0]["copy"]["kicker"] = "C:\\Users\\alice\\recap\\story.json"
    story["cards"][0]["copy"]["sub"] = "见 https://example.com/recap 与 ~/Downloads/export.json"
    insights["insights"][0]["caveats"] = ["源文件 /home/alice/recap.db"]
    return redact_pair(insights, story, book=Book(salt="ab" * 16), words=[])


def test_redacted_pair_has_no_urls_paths_or_home_dirs() -> None:
    result = redacted()

    leaked = [
        text
        for text in [*strings(result.insights), *strings(result.story)]
        if URL.search(text) or DRIVE.search(text) or HOME.search(text) or TILDE.search(text)
    ]

    assert leaked == []


def test_the_injections_were_actually_redacted() -> None:
    """证明上一条不是空转: 注入的四个样本都进了审计计数。"""
    result = redacted()

    assert result.audit.pii_counts.get("URL") == 1
    assert result.audit.pii_counts.get("路径") == 3
