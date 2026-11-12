"""spotify 导出的纯解析: 文件发现、JSON 读取、一行到 Event 的映射。

不碰数据库、不碰命令行。口径与边界都在这里, `spotify.py` 只负责逐文件记账与写入。
逐条理由见 `docs/adapters/spotify/KNOWN_DIVERGENCES.md`:

- 只计 `ms_played > 30000` 的播放; `incognito_mode` 一律排除
- 播客/有声书的 `master_metadata_*` 全为 null: 计入时长, 但实体为空
- `conn_country` / `ip_addr` 不读进任何字段
- 导出只带 UTC 时间戳、不带本地偏移, 所以 `tz_offset_min` 恒为 None

`row_hash` 用「源|UTC 时刻|uri|毫秒」: 同一行重复出现在两个文件里只会留一条,
但同一秒的不同播放不会被误吞。
"""

import hashlib
import json
from pathlib import Path

from recapkits.db import Event
from recapkits.tz import split_utc_and_offset

SOURCE = "spotify"
KIND = "play"
FILE_GLOB = "Streaming_History_Audio_*.json"
MIN_PLAY_MS = 30_000

#: 落进 flags 的字段; 其余字段只在解析时读, 不复制一份进数据库。
FLAG_FIELDS = ("reason_start", "reason_end", "shuffle", "skipped", "offline", "incognito_mode")

#: 已知字段。未知字段只警告, 不影响解析 —— 平台加字段不该让整次导入失败。
KNOWN_FIELDS = frozenset(
    {
        "ts",
        "platform",
        "ms_played",
        "conn_country",
        "ip_addr",
        "master_metadata_track_name",
        "master_metadata_album_artist_name",
        "master_metadata_album_album_name",
        "spotify_track_uri",
        "episode_name",
        "episode_show_name",
        "spotify_episode_uri",
        "audiobook_title",
        "audiobook_uri",
        "audiobook_chapter_uri",
        "audiobook_chapter_title",
        "reason_start",
        "reason_end",
        "shuffle",
        "skipped",
        "offline",
        "offline_timestamp",
        "incognito_mode",
        # 2023 年前的老格式
        "endTime",
        "artistName",
        "trackName",
        "msPlayed",
    }
)

SKIP_INCOGNITO = "incognito"
SKIP_SHORT = "short_play"
SKIP_MS = "missing_ms_played"
SKIP_TS = "missing_ts"
SKIP_ROW = "not_an_object"
SKIP_WINDOW = "out_of_window"


def find_files(root: Path) -> list[Path]:
    """目录下所有扩展流媒体历史文件, 按路径排序。"""
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob(FILE_GLOB) if path.is_file())


def text(row: dict[str, object], *keys: str) -> str | None:
    """按优先级取第一个非空字符串; 新版字段在前, 老版字段在后。"""
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def utc(row: dict[str, object]) -> str | None:
    """UTC 时刻文本; 无偏移的老格式按 UTC 归一 (caveat 见分歧文档)。"""
    raw = text(row, "ts", "endTime")
    if raw is None:
        return None
    try:
        return split_utc_and_offset(raw)[0]
    except ValueError:
        return None


def milliseconds(row: dict[str, object]) -> float | None:
    """播放毫秒数; 缺失、非数字、负数都返回 None。"""
    value = row.get("ms_played", row.get("msPlayed"))
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if value >= 0 else None


def row_event(row: dict[str, object]) -> tuple[Event | None, str | None]:
    """把一行导出变成事件; 不能计入时返回 (None, 原因)。"""
    if row.get("incognito_mode") is True:
        return None, SKIP_INCOGNITO
    millis = milliseconds(row)
    if millis is None:
        return None, SKIP_MS
    if millis <= MIN_PLAY_MS:
        return None, SKIP_SHORT
    ts_utc = utc(row)
    if ts_utc is None:
        return None, SKIP_TS

    # 新版字段非空才用; 老格式没有 metadata, 于是标题为空、实体为空。
    title = text(row, "master_metadata_track_name", "trackName")
    if title is None:
        subtitle = None
        category = text(row, "episode_show_name", "audiobook_title")
    else:
        subtitle = text(row, "master_metadata_album_artist_name", "artistName")
        category = text(row, "master_metadata_album_album_name")
    uri = text(row, "spotify_track_uri", "spotify_episode_uri", "audiobook_uri") or ""

    digest = hashlib.sha256(f"{SOURCE}|{ts_utc}|{uri}|{millis:.3f}".encode()).hexdigest()[:16]
    flags = {key: row[key] for key in FLAG_FIELDS if key in row}
    event = Event(
        source=SOURCE,
        kind=KIND,
        ts_utc=ts_utc,
        tz_offset_min=None,
        title=title,
        subtitle=subtitle,
        category=category,
        duration_s=round(millis / 1000.0, 3),
        value=1.0,
        flags=flags or None,
        meta={"uri": uri} if uri else None,
        row_hash=digest,
    )
    return event, None


def load(path: Path) -> tuple[list[object] | None, str | None]:
    """读一个导出文件; 返回 (数组元素, 问题)。整份读不出来时问题是原因。"""
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except UnicodeDecodeError:
        return None, "不是 UTF-8 编码"
    except OSError as exc:
        return None, f"读取失败 ({exc.__class__.__name__})"
    except json.JSONDecodeError:
        return None, "不是合法 JSON"
    if not isinstance(payload, list):
        return None, "顶层不是数组"
    return list(payload), None
