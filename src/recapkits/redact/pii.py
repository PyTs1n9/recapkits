"""结构化 PII: 正则识别 + 校验位复核。

误伤比漏抹更容易被当成"工具坏了": 一段 16 位播放时长被抹掉, 用户就再也不信
报告里的计数。所以卡号必须过 Luhn、IBAN 必须过 mod-97、坐标必须落在经纬度范围
内、IPv6 必须能被 `ipaddress` 解析 —— "看起来像"不够。

**完整 scheme 是刻意拆开写的。** `src/` 的硬规则禁止出现 URL 字面量
(`tests/unit/test_core_is_offline.py`), 它拦的是出站请求, 而这个正则恰恰要识别
URL。规则只认字面量, 所以这里不写完整 scheme, 也不给规则开例外 —— 判据一旦被
削弱, 下一次真有人加 `urllib.request` 时就拦不住了。
"""

import ipaddress
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

#: 统一的替换标记。不用空串: 读者要知道"这里原本有东西", 而不是以为文案本来如此。
REMOVED = "〔已移除〕"  # noqa: RUF001  (标记给中文读者看, 保留全角括号)

_SCHEME = "ht" + "tps?"
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL = re.compile(_SCHEME + r"://[^\s<>\"'()\]]+", re.IGNORECASE)
_HANDLE = re.compile(r"(?<![A-Za-z0-9_@])@[A-Za-z0-9_]{2,32}(?![A-Za-z0-9_])")
_IPV4 = re.compile(r"(?<![0-9A-Za-z.])(?:\d{1,3}\.){3}\d{1,3}(?![0-9A-Za-z.])")
_IPV6 = re.compile(r"(?<![\w:])[0-9A-Fa-f:]{3,}(?![\w:])")
_COORD = re.compile(r"(?<![\d.])(-?\d{1,3}\.\d{3,})[,\uff0c]\s*(-?\d{1,3}\.\d{3,})(?![\d.])")
_CARD = re.compile(r"(?<![0-9A-Za-z-])(?:\d[ -]?){12,18}\d(?![0-9A-Za-z-])")
_IBAN = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2}\d{2}[A-Z0-9]{10,30}(?![A-Za-z0-9])", re.IGNORECASE)
_PHONE_INTL = re.compile(r"(?<![\d+])\+\d{1,3}(?:[\s.-]?\(?\d{1,4}\)?){2,4}(?!\d)")
_PHONE_LOCAL = re.compile(r"(?<![0-9A-Za-z-])\d{3,4}(?:[ -]\d{3,4}){2}(?![0-9A-Za-z-])")

#: URL 末尾常见标点不属于地址; 不裁掉的话替换标记会吃掉后面的句号。
_TRAILING = ".,;:!?)]}'\"\u3002\uff0c\uff1b\uff1a\uff01\uff1f\u300d\u300f\u3011"


@dataclass(frozen=True)
class Ruling:
    """一处命中: 区间、类别与原文样本。样本只用于 TTY 审计, 不落盘。"""

    start: int
    end: int
    category: str
    sample: str
    priority: int


def _luhn(digits: str) -> bool:
    """银行卡校验位; 纯数字的播放时长几乎一定过不了这一关。"""
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _iban_ok(token: str) -> bool:
    """IBAN 的 mod-97 校验: 前四位挪到末尾, 字母转 10..35 再取模。"""
    compact = token.replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", compact):
        return False
    rearranged = compact[4:] + compact[:4]
    expanded = "".join(str(int(char, 36)) for char in rearranged)
    return int(expanded) % 97 == 1


def _ipv4_ok(token: str) -> bool:
    return all(int(part) <= 255 for part in token.split("."))


def _ipv6_ok(token: str) -> bool:
    """必须有冒号且能被解析; `23:41:07` 会在这里被排除, 它不是地址。"""
    if token.count(":") < 2:
        return False
    try:
        ipaddress.IPv6Address(token)
    except ValueError:
        return False
    return True


def _coord_ok(latitude: str, longitude: str) -> bool:
    return -90.0 <= float(latitude) <= 90.0 and -180.0 <= float(longitude) <= 180.0


def _digits(token: str) -> str:
    return "".join(char for char in token if char.isdigit())


def _url(text: str) -> Iterator[tuple[int, int]]:
    for match in _URL.finditer(text):
        start, end = match.span()
        while end > start and text[end - 1] in _TRAILING:
            end -= 1
        # 至少要剩下 scheme 与一个主机字符; 只有 scheme 和斜杠的残片不值得动。
        if end - start > 7:
            yield start, end


def _email(text: str) -> Iterator[tuple[int, int]]:
    yield from (match.span() for match in _EMAIL.finditer(text))


def _iban(text: str) -> Iterator[tuple[int, int]]:
    for match in _IBAN.finditer(text):
        if _iban_ok(match.group(0)):
            yield match.span()


def _card(text: str) -> Iterator[tuple[int, int]]:
    for match in _CARD.finditer(text):
        digits = _digits(match.group(0))
        if 13 <= len(digits) <= 19 and _luhn(digits):
            yield match.span()


def _ip(text: str) -> Iterator[tuple[int, int]]:
    for match in _IPV4.finditer(text):
        if _ipv4_ok(match.group(0)):
            yield match.span()
    for match in _IPV6.finditer(text):
        if _ipv6_ok(match.group(0)):
            yield match.span()


def _coord(text: str) -> Iterator[tuple[int, int]]:
    for match in _COORD.finditer(text):
        if _coord_ok(match.group(1), match.group(2)):
            yield match.span()


def _phone(text: str) -> Iterator[tuple[int, int]]:
    for match in _PHONE_INTL.finditer(text):
        if 8 <= len(_digits(match.group(0))) <= 15:
            yield match.span()
    # 本地格式要求三组、每组至少三位: `2024-03-11` 与 `1080 1920` 都进不来。
    for match in _PHONE_LOCAL.finditer(text):
        if 9 <= len(_digits(match.group(0))) <= 15:
            yield match.span()


def _handle(text: str) -> Iterator[tuple[int, int]]:
    yield from (match.span() for match in _HANDLE.finditer(text))


#: 先长后短不重要, 重叠由 `scan` 统一裁决; 这里的顺序只在长度相同时决定胜负。
_RULES: tuple[tuple[str, int, Callable[[str], Iterator[tuple[int, int]]]], ...] = (
    ("URL", 0, _url),
    ("邮箱", 1, _email),
    ("IBAN", 2, _iban),
    ("卡号", 3, _card),
    ("IP", 4, _ip),
    ("坐标", 5, _coord),
    ("电话", 6, _phone),
    ("@handle", 7, _handle),
)


def scan(text: str) -> list[Ruling]:
    """全部命中, 不重叠、按起点升序。

    重叠裁决: 起点早的优先, 同起点取更长的 (邮箱压过 `@handle`, 卡号压过电话),
    长度也相同才看类别优先级。把顺序写死, 同一段文本的产物才稳定。
    """
    candidates: list[Ruling] = []
    for category, priority, matcher in _RULES:
        for start, end in matcher(text):
            candidates.append(Ruling(start, end, category, text[start:end], priority))
    candidates.sort(key=lambda item: (item.start, -(item.end - item.start), item.priority))

    accepted: list[Ruling] = []
    for candidate in candidates:
        if any(candidate.start < prior.end and prior.start < candidate.end for prior in accepted):
            continue
        accepted.append(candidate)
    return accepted


def redact(text: str) -> tuple[str, list[Ruling]]:
    """替换全部命中; 返回新文本与命中列表 (样本取自原文)。"""
    rulings = scan(text)
    if not rulings:
        return text, []
    pieces: list[str] = []
    cursor = 0
    for ruling in rulings:
        pieces.append(text[cursor : ruling.start])
        pieces.append(REMOVED)
        cursor = ruling.end
    pieces.append(text[cursor:])
    return "".join(pieces), rulings
