"""netflix ViewingActivity.csv: 多文件合并、续播去重、逐文件记账与写库。

解析细节在 `netflix_parse.py`。本模块负责三件在单行层面看不出来的事:

1. **档案合并。** 一个家庭可能有多份 `ViewingActivity.csv` (每个档案一份、目录
   各不相同)。默认合并成一个源; 报告只说「合并了 N 个档案」, 不写档案名。
2. **续播去重。** 同一 (档案哈希, 剧名, 开始时间) 可能有多行, 只保留**最大时长**;
   被合并掉的行进 `resume_duplicate`, 账仍然对得上。
3. **文件级容错。** 一份文件读不出来只记警告, 其余文件照常导入。
"""

import csv
import hashlib
import io
import sqlite3
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

from recapkits.adapters.base import FileLedger, IngestReport
from recapkits.adapters.netflix_parse import (
    FILE_NAME,
    KNOWN_COLUMNS,
    REQUIRED_COLUMNS,
    SKIP_BAD_ROW,
    SKIP_BLANK,
    SKIP_DUPLICATE,
    SKIP_WINDOW,
    SOURCE,
    candidate,
    decode,
    profile_hash,
    row_hash,
)
from recapkits.db import Event, insert_events
from recapkits.tz import resolve_local


@dataclass(frozen=True)
class _Candidate:
    """一条可计入的观看, 以及它来自哪个文件 (记账要按文件分组)。"""

    file: str
    key: tuple[str, str, str]
    event: Event
    duration_s: float


@dataclass
class _FileResult:
    """一个文件的解析结果; 行的最终归属要等全局去重之后才能定。"""

    name: str
    candidates: list[_Candidate] = field(default_factory=list)
    reasons: Counter[str] = field(default_factory=Counter)
    warnings: list[str] = field(default_factory=list)
    profiles: set[str] = field(default_factory=set)
    problem: str | None = None


def find_files(root: Path) -> list[Path]:
    """目录下所有 ViewingActivity.csv, 按路径排序。"""
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob(FILE_NAME) if path.is_file())


def _display_name(root: Path, file: Path) -> str:
    """文件标识用相对路径: 每个档案都有自己的 ViewingActivity.csv, 不能按 basename 合并。"""
    try:
        return file.relative_to(root).as_posix()
    except ValueError:
        return file.name


def _parse_file(
    path: Path, *, name: str, since: date | None, until: date | None, tz: str
) -> _FileResult:
    """读一份 CSV: 表头按列名校验, 行按口径过滤, 逐条记账。"""
    try:
        payload = path.read_bytes()
    except OSError as exc:
        return _FileResult(name=name, problem=f"读取失败 ({exc.__class__.__name__})")

    text, _encoding, bad_bytes = decode(payload)
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = [cell.strip() for cell in next(reader)]
    except StopIteration:
        return _FileResult(name=name, problem="空文件")
    except csv.Error:
        return _FileResult(name=name, problem="CSV 结构错误")

    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise ValueError(f"{name}: 缺少必需列 {', '.join(missing)}")

    result = _FileResult(name=name)
    unknown = sorted(set(header) - KNOWN_COLUMNS)
    if unknown:
        result.warnings.append(f"{name}: 未知列 {', '.join(unknown)}")
    if bad_bytes:
        result.warnings.append(f"{name}: 含无法解码的字节, 相关行已跳过")

    index = {name: position for position, name in enumerate(header)}
    try:
        for cells in reader:
            if not cells or all(not cell.strip() for cell in cells):
                result.reasons[SKIP_BLANK] += 1
                continue
            if len(cells) != len(header):
                result.reasons[SKIP_BAD_ROW] += 1
                continue
            row = {name: cells[position] for name, position in index.items()}
            profile = row.get("Profile Name", "").strip()
            if profile:
                result.profiles.add(profile_hash(profile))

            parsed, reason = candidate(row)
            if parsed is None:
                result.reasons[reason or "unknown"] += 1
                continue
            key, event, duration = parsed
            local_day, _ = resolve_local(event.ts_utc, None, tz)
            if (since is not None and local_day < since.isoformat()) or (
                until is not None and local_day > until.isoformat()
            ):
                result.reasons[SKIP_WINDOW] += 1
                continue
            result.candidates.append(_Candidate(name, key, event, duration))
    except csv.Error:
        return _FileResult(name=name, problem="CSV 结构错误")
    return result


def _merge(results: list[_FileResult]) -> tuple[list[Event], list[FileLedger], int]:
    """按 (档案, 剧名, 开始时间) 保留最大时长, 并给每个文件出一份账。"""
    flat = [cand for result in results for cand in result.candidates]
    best: dict[tuple[str, str, str], int] = {}
    for position, cand in enumerate(flat):
        current = best.get(cand.key)
        if current is None or cand.duration_s > flat[current].duration_s:
            best[cand.key] = position

    kept_per_file = Counter(flat[position].file for position in best.values())
    candidates_per_file = Counter(cand.file for cand in flat)
    ledgers: list[FileLedger] = []
    for result in results:
        if result.problem:
            ledgers.append(FileLedger(name=result.name, problem=result.problem))
            continue
        reasons = Counter(result.reasons)
        dropped = candidates_per_file[result.name] - kept_per_file[result.name]
        if dropped:
            reasons[SKIP_DUPLICATE] += dropped
        ledgers.append(
            FileLedger(
                name=result.name,
                rows=kept_per_file[result.name],
                skipped=sum(reasons.values()),
                reasons=dict(reasons),
            )
        )

    events = [
        replace(
            flat[position].event,
            row_hash=row_hash(flat[position].key, flat[position].duration_s),
        )
        for position in sorted(best.values())
    ]
    profiles = len({profile for result in results for profile in result.profiles})
    return events, ledgers, profiles


class NetflixAdapter:
    """Netflix 观看记录适配器。"""

    id = SOURCE
    description = "Netflix 观看记录 (ViewingActivity.csv)"

    def detect(self, path: Path) -> float:
        """目录里有 CSV 为 1.0, 只在子目录里找到为 0.8, 否则 0.0。"""
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
        """逐文件解析、全局去重后写入; 单个文件坏掉不影响其余文件。"""
        files = find_files(path)
        if not files:
            raise FileNotFoundError(
                f"{path} 下没有 {FILE_NAME}: Netflix 导出里应包含这个文件 "
                "(非美区账号可能只提供汇总 CSV, 不含逐条观看记录)"
            )

        results = [
            _parse_file(file, name=_display_name(path, file), since=since, until=until, tz=tz)
            for file in files
        ]
        events, ledgers, profiles = _merge(results)
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
            warnings=[warning for result in results for warning in result.warnings],
            files=ledgers,
            notes=[f"已合并 {profiles} 个档案，未写入档案名"],  # noqa: RUF001
        )
