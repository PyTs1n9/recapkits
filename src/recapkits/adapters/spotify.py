"""spotify 扩展流媒体历史: 逐文件记账、口径过滤与写库。

解析细节在 `spotify_parse.py`: 一行怎么变成 Event、哪些字段丢弃、哪些行跳过。
本模块只负责把多个文件串起来, 并保证每个文件的账都对得上:

- `rows + skipped == 数组元素数`; 每个跳过都有原因
- 一个文件坏掉只记警告, 其余文件照常导入
- 同一目录导入两次, 事件数不变
"""

import hashlib
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path

from recapkits.adapters.base import FileLedger, IngestReport
from recapkits.adapters.spotify_parse import (
    FILE_GLOB,
    KNOWN_FIELDS,
    SKIP_MS,
    SKIP_ROW,
    SKIP_TS,
    SKIP_WINDOW,
    SOURCE,
    find_files,
    load,
    row_event,
)
from recapkits.db import Event, insert_events
from recapkits.tz import resolve_local


def _ingest_file(
    path: Path, *, since: date | None, until: date | None, tz: str
) -> tuple[FileLedger, list[Event], list[str]]:
    """解析一个文件; 坏文件只记警告, 不中断整次导入。"""
    items, problem = load(path)
    if items is None:
        return FileLedger(name=path.name, problem=problem), [], [f"{path.name}: {problem}"]

    events: list[Event] = []
    reasons: Counter[str] = Counter()
    unknown: set[str] = set()
    for row in items:
        if not isinstance(row, dict):
            reasons[SKIP_ROW] += 1
            continue
        unknown.update(set(row) - KNOWN_FIELDS)
        event, reason = row_event(row)
        if event is None:
            reasons[reason or "unknown"] += 1
            continue
        local_day, _ = resolve_local(event.ts_utc, None, tz)
        if (since is not None and local_day < since.isoformat()) or (
            until is not None and local_day > until.isoformat()
        ):
            reasons[SKIP_WINDOW] += 1
            continue
        events.append(event)

    if items and not events and reasons and set(reasons) <= {SKIP_MS, SKIP_TS}:
        # 合法 JSON 但一行都解析不出来: 这不是「跳过几行」, 是字段契约不成立。
        # 只需要点名一个字段: 两个都缺时先说时间戳, 它更能定位问题。
        missing = "ts" if reasons[SKIP_TS] else "ms_played"
        raise ValueError(f"{path.name}: 缺少必需字段 {missing}, 不像 Spotify 扩展流媒体历史")

    ledger = FileLedger(
        name=path.name, rows=len(events), skipped=sum(reasons.values()), reasons=dict(reasons)
    )
    warnings = [f"{path.name}: 未知字段 {', '.join(sorted(unknown))}"] if unknown else []
    return ledger, events, warnings


class SpotifyAdapter:
    """Spotify 扩展流媒体历史适配器。"""

    id = SOURCE
    description = "Spotify 扩展流媒体历史 (Streaming_History_Audio_*.json)"

    def detect(self, path: Path) -> float:
        """目录里有导出文件为 1.0, 只在子目录里找到为 0.8, 否则 0.0。"""
        files = find_files(path)
        if not files:
            return 0.0
        return 1.0 if any(file.parent == path for file in files) else 0.8

    def ingest(
        self,
        path: Path,
        conn: sqlite3.Connection,
        *,
        since: date | None = None,
        until: date | None = None,
        tz: str = "UTC",
    ) -> IngestReport:
        """逐文件解析并写入; 单个文件坏掉不影响其余文件。"""
        files = find_files(path)
        if not files:
            raise FileNotFoundError(f"{path} 下没有 {FILE_GLOB}: 需要 Spotify 扩展流媒体历史导出")

        events: list[Event] = []
        ledgers: list[FileLedger] = []
        warnings: list[str] = []
        for file in files:
            ledger, found, notes = _ingest_file(file, since=since, until=until, tz=tz)
            ledgers.append(ledger)
            events.extend(found)
            warnings.extend(notes)

        insert_events(conn, events)
        stamps = [event.ts_utc for event in events]
        return IngestReport(
            source=SOURCE,
            units=len(files),
            rows=len(events),
            skipped=sum(ledger.skipped for ledger in ledgers),
            first_ts=min(stamps) if stamps else None,
            last_ts=max(stamps) if stamps else None,
            src_hash=hashlib.sha256(
                "\n".join(sorted(event.row_hash for event in events)).encode()
            ).hexdigest()[:16],
            warnings=warnings,
            files=ledgers,
        )
