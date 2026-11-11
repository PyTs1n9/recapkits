"""时间的唯一入口: 所有 UTC 与本地时间的换算只在这里发生。

对外只有四件事:

- `utc_now_iso()` 生成写入数据库的时间戳(UTC, `Z` 结尾)
- `resolve_local()` 把 UTC 时刻解析为本地日期与小时
- `local_datetime()` 同上, 但保留时分秒
- `rebuild_local()` 全量重建派生表 `event_local`

设计约束见 docs/decisions/0001-contracts.md:

- 不读系统时区; 取当前时钟只有 `utc_now_iso()` 一个入口
- UTC 到本地只有两条路: 源偏移, 或 zoneinfo 时区名
- 业务代码与 SQL 不得内联任何本地时间换算
"""

import sqlite3
import time
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


def parse_utc(text: str) -> datetime:
    """解析 ISO 8601 文本, 返回带 UTC 时区的 datetime; 缺时区信息时抛 ValueError。"""
    raw = text.strip()
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"无法解析时间戳 {text!r}, 期望 ISO 8601") from exc
    offset = parsed.utcoffset()
    if offset is None:
        raise ValueError(f"时间戳缺少时区信息 {text!r}, 无法定位 UTC 时刻")
    return (parsed.replace(tzinfo=None) - offset).replace(tzinfo=UTC)


def to_utc_iso(moment: datetime) -> str:
    """把带时区的 datetime 归一为 UTC 的 ISO 8601 文本, 秒级精度, `Z` 结尾。"""
    offset = moment.utcoffset()
    if offset is None:
        raise ValueError("to_utc_iso 需要带时区的 datetime")
    utc = moment.replace(tzinfo=None) - offset
    return (
        f"{utc.year:04d}-{utc.month:02d}-{utc.day:02d}"
        f"T{utc.hour:02d}:{utc.minute:02d}:{utc.second:02d}Z"
    )


def utc_now_iso() -> str:
    """当前 UTC 时刻, ISO 8601, `Z` 结尾。全项目唯一允许取现在的函数。"""
    return to_utc_iso(datetime.fromtimestamp(time.time(), UTC))


def split_utc_and_offset(text: str) -> tuple[str, int | None]:
    """把带偏移的 ISO 8601 拆成 (UTC 文本, 偏移分钟)。无偏移时返回 (UTC 文本, None)。

    数据源自带偏移时(如 git 的 `%aI`)应当保留它: 它比用户配置的时区更可信。
    """
    raw = text.strip()
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    offset = parsed.utcoffset()
    if offset is None:
        return to_utc_iso(parsed.replace(tzinfo=UTC)), None
    return to_utc_iso(parsed), int(offset.total_seconds() // 60)


def local_datetime(ts_utc: str, tz_offset_min: int | None, tz_name: str) -> datetime:
    """返回不带时区的本地墙钟时间; 源自带偏移时优先用偏移, 否则用 IANA 时区名。"""
    utc = parse_utc(ts_utc)
    if tz_offset_min is not None:
        return utc.replace(tzinfo=None) + timedelta(minutes=tz_offset_min)
    zone = ZoneInfo(tz_name)
    return datetime.fromtimestamp(utc.timestamp(), zone).replace(tzinfo=None)


def resolve_local(ts_utc: str, tz_offset_min: int | None, tz_name: str) -> tuple[str, int]:
    """返回 (local_date 'YYYY-MM-DD', local_hour 0-23)。

    1) `tz_offset_min` 不为 None 时用它, 源自带的偏移最可信
    2) 否则用 `zoneinfo.ZoneInfo(tz_name)` 从 UTC 转本地
    """
    local = local_datetime(ts_utc, tz_offset_min, tz_name)
    return local.date().isoformat(), local.hour


def rebuild_local(conn: sqlite3.Connection, tz_name: str, batch: int = 5000) -> int:
    """用 tz_name 全量重建 event_local 的该时区切片, 返回写入行数。"""
    conn.execute("DELETE FROM event_local WHERE tz = ?", (tz_name,))
    cursor = conn.execute("SELECT id, ts_utc, tz_offset_min FROM events ORDER BY id")
    written = 0
    while True:
        rows = cursor.fetchmany(batch)
        if not rows:
            break
        payload = []
        for row in rows:
            local_date, local_hour = resolve_local(row["ts_utc"], row["tz_offset_min"], tz_name)
            payload.append((row["id"], tz_name, local_date, local_hour))
        conn.executemany(
            "INSERT OR REPLACE INTO event_local (event_id, tz, local_date, local_hour) "
            "VALUES (?, ?, ?, ?)",
            payload,
        )
        written += len(payload)
    conn.commit()
    return written
