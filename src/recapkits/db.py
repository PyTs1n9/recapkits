"""SQLite 契约的实现: 连接、建表、幂等写入。

表结构逐字取自 docs/decisions/0001-contracts.md, 不得增删字段。
唯一的差异: DDL 注释里的全角逗号按 lint 规则(RUF001)写成半角, 字段与类型一字未改。

本模块不含任何时间逻辑: `created_at` 由调用方经 `recapkits.tz` 生成后传入,
这样"取现在"只有一处实现, 也便于测试注入固定值。
"""

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS raw_row (
  adapter   TEXT NOT NULL,
  src_file  TEXT NOT NULL,
  src_line  INTEGER NOT NULL,
  payload   TEXT NOT NULL,
  PRIMARY KEY (adapter, src_file, src_line)
);

CREATE TABLE IF NOT EXISTS events (
  id            INTEGER PRIMARY KEY,
  source        TEXT NOT NULL,
  kind          TEXT NOT NULL,
  ts_utc        TEXT NOT NULL,          -- ISO 8601, 始终以 Z 结尾
  tz_offset_min INTEGER,                -- 仅当源自带偏移时非空
  title         TEXT,
  subtitle      TEXT,
  category      TEXT,
  duration_s    REAL,
  value         REAL,
  sensitivity   TEXT NOT NULL DEFAULT 'low',   -- low | medium | high
  flags         TEXT,                   -- JSON 对象字符串
  meta_json     TEXT,
  row_hash      TEXT NOT NULL           -- 幂等键, sha256 前 16 位
);
CREATE INDEX IF NOT EXISTS idx_ev_src_ts  ON events(source, ts_utc);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ev_rowhash ON events(row_hash);

CREATE TABLE IF NOT EXISTS event_local (
  event_id   INTEGER NOT NULL,
  tz         TEXT NOT NULL,
  local_date TEXT NOT NULL,             -- YYYY-MM-DD
  local_hour INTEGER NOT NULL,          -- 0..23
  PRIMARY KEY (event_id, tz)
);
CREATE INDEX IF NOT EXISTS idx_local_date ON event_local(tz, local_date, local_hour);

CREATE TABLE IF NOT EXISTS import_reports (
  id         INTEGER PRIMARY KEY,
  source     TEXT NOT NULL,
  src_hash   TEXT NOT NULL,
  rows       INTEGER NOT NULL,
  skipped    INTEGER NOT NULL,
  warnings   TEXT,
  coverage   REAL,                      -- 0..1, 实际覆盖天数 / 应有天数
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS build (
  build_id TEXT PRIMARY KEY,
  options  TEXT NOT NULL,
  manifest TEXT NOT NULL                -- 只存哈希, 永不存绝对路径
);
"""

INSERT_EVENT = """
INSERT OR IGNORE INTO events
  (source, kind, ts_utc, tz_offset_min, title, subtitle, category, duration_s, value,
   sensitivity, flags, meta_json, row_hash)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


@dataclass(frozen=True)
class Event:
    """events 表的一行; 字段与契约一一对应, 不增不减。

    `meta` 落到列 `meta_json`, `flags` 落到列 `flags`, 两者都以 JSON 文本存储。
    `row_hash` 是幂等键, 由适配器计算, 本模块只负责在冲突时跳过。
    """

    source: str
    kind: str
    ts_utc: str
    tz_offset_min: int | None = None
    title: str | None = None
    subtitle: str | None = None
    category: str | None = None
    duration_s: float | None = None
    value: float | None = None
    sensitivity: str = "low"
    flags: dict[str, object] | None = None
    meta: dict[str, object] | None = None
    row_hash: str = ""

    def to_row(self) -> tuple[object, ...]:
        """按 INSERT_EVENT 的占位符顺序返回绑定参数。"""
        return (
            self.source,
            self.kind,
            self.ts_utc,
            self.tz_offset_min,
            self.title,
            self.subtitle,
            self.category,
            self.duration_s,
            self.value,
            self.sensitivity,
            _dump_optional(self.flags),
            _dump_optional(self.meta),
            self.row_hash,
        )


def _dump_optional(value: dict[str, object] | None) -> str | None:
    """把可选字典序列化为稳定的 JSON 文本, 空字典视为 None。"""
    if not value:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def connect(db_path: Path) -> sqlite3.Connection:
    """打开(必要时创建)数据库, 启用 WAL 并按列名取行。"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """按契约建表建索引; 重复调用无副作用。"""
    conn.executescript(SCHEMA)
    conn.commit()


def insert_events(conn: sqlite3.Connection, events: Iterable[Event]) -> int:
    """批量写入事件, row_hash 冲突即跳过; 返回真正新增的行数。"""
    rows = [event.to_row() for event in events]
    if not rows:
        return 0
    before = conn.total_changes
    conn.executemany(INSERT_EVENT, rows)
    conn.commit()
    return conn.total_changes - before


def insert_import_report(
    conn: sqlite3.Connection,
    *,
    source: str,
    src_hash: str,
    rows: int,
    skipped: int,
    warnings: Iterable[str],
    coverage: float | None,
    created_at: str,
) -> int:
    """追加一条导入报告, 返回新行的 id。"""
    cursor = conn.execute(
        "INSERT INTO import_reports (source, src_hash, rows, skipped, warnings, coverage, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            source,
            src_hash,
            rows,
            skipped,
            json.dumps(list(warnings), ensure_ascii=False),
            coverage,
            created_at,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid or 0)


def count_events(conn: sqlite3.Connection, source: str | None = None) -> int:
    """返回事件总数; 给定 source 时只数该源。"""
    if source is None:
        row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) FROM events WHERE source = ?", (source,)).fetchone()
    return int(row[0])


def list_sources(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    """返回 [(source, 事件数)], 按 source 升序; 供 doctor 与引擎使用。"""
    rows = conn.execute(
        "SELECT source, COUNT(*) AS n FROM events GROUP BY source ORDER BY source"
    ).fetchall()
    return [(str(row["source"]), int(row["n"])) for row in rows]
