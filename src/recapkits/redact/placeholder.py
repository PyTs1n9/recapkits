"""去名的 agent 载荷: `minimize` → `redact` → (载荷, 还原表)。

三份产物由调用方写: 完整版原样、agent 最小版、restore 表。这里只做数据变换,
不碰磁盘上的完整版 —— 「原样」由调用方保证。

复用同一本 `redactions.json`: 同一次工作区里, `recap redact` 与 agent 载荷必须给
同一个实体同一个假名, 否则"两份脱敏导出可以比对"这条承诺就断了。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from recapkits.errors import RecapError
from recapkits.payload import minimize
from recapkits.redact import pseudonym, restore
from recapkits.redact.apply import redact_insights
from recapkits.redact.checks import check_unique_ids
from recapkits.redact.pseudonym import Book, PseudonymError

BOOK_FILE = "redactions.json"


@dataclass(frozen=True)
class PlaceholderPayload:
    """交给磁盘的两份内容; `restore` 含原名, 不能分享。"""

    insights: dict[str, Any]
    restore: dict[str, Any]


def book_for(root: Path) -> Book:
    """读工作区的盐; 不存在就新建一个, 落盘由调用方决定。"""
    try:
        loaded = pseudonym.load(root / BOOK_FILE)
    except PseudonymError as exc:
        raise RecapError(str(exc)) from exc
    return loaded if loaded is not None else Book(salt=pseudonym.new_salt())


def build(
    payload: dict[str, Any], *, root: Path, words: list[str]
) -> tuple[PlaceholderPayload, Book]:
    """先最小化再去名: 反过来的话, `evidence_sql` 也会被扫一遍 PII, 白做功。"""
    book = book_for(root)
    result = redact_insights(minimize(payload), book=book, words=words)
    check_unique_ids(result.insights)
    # id_map 是"真 -> 假"; 还原表要的是"假 -> 真", 方向反了等于没有还原。
    # 被抑制表整体移除的 id 不进表: 顺着 id 还原会把用户点名要消失的实体带回画面。
    table = restore.build(
        salt=book.salt,
        ids={
            fake: real for real, fake in result.id_map.items() if real not in result.suppressed_ids
        },
        names=result.names,
    )
    return PlaceholderPayload(insights=result.insights, restore=table), book
