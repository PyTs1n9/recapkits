"""netflix ViewingActivity.csv 的纯解析: 编码试探、时长、标题与行到 Event 的映射。

不碰数据库、不碰命令行。口径与已知分歧见 `docs/adapters/netflix/KNOWN_DIVERGENCES.md`:

- `Supplemental Video Type` 为 HOOK / RECAP / TRAILER 的行排除
- 时长 <= 2 秒视为自动播放预览, 排除
- `Start Time` 无偏移, 按 UTC 解读; `tz_offset_min` 恒为 None
- `Profile Name` 只以哈希形式参与去重键, 明文不进任何字段
- `Title` 形如 `剧名: Season 2: "集名"`; `title` 存原串, `subtitle` 存**剧名**,
  季进 `category`, 集名进 `meta.episode`

为什么 subtitle 存剧名而不是季: 集中度检测器取 subtitle 优先。把季放进 subtitle,
「出现最多的项目」会变成「出现最多的季」, 与 `entity_kind=show` 直接矛盾。
"""

import hashlib
import re

from recapkits.db import Event
from recapkits.tz import split_utc_and_offset

SOURCE = "netflix"
KIND = "view"
FILE_NAME = "ViewingActivity.csv"

#: 时长 <= 2 秒一律视为自动播放预览; 真实导出的预览行通常是 1 秒。
PREVIEW_MAX_S = 2
EXCLUDED_SUPPLEMENTAL = frozenset({"HOOK", "RECAP", "TRAILER"})

REQUIRED_COLUMNS = ("Profile Name", "Start Time", "Duration", "Title")
KNOWN_COLUMNS = frozenset(
    {
        *REQUIRED_COLUMNS,
        "Attributes",
        "Supplemental Video Type",
        "Device Type",
        "Bookmark",
        "Latest Bookmark",
        "Country",
    }
)

DURATION_RE = re.compile(r"^(\d+):([0-5]\d):([0-5]\d)$")
SEASON_RE = re.compile(r"^(Season \d+|Limited Series|Part \d+|Volume \d+|Book \d+)$")
REPLACEMENT = "\ufffd"

SKIP_BAD_ENCODING = "bad_encoding"
SKIP_BAD_ROW = "bad_row"
SKIP_BLANK = "blank"
SKIP_EMPTY_PROFILE = "empty_profile"
SKIP_EMPTY_TITLE = "empty_title"
SKIP_BAD_START = "bad_start_time"
SKIP_BAD_DURATION = "bad_duration"
SKIP_SUPPLEMENTAL = "supplemental"
SKIP_PREVIEW = "preview"
SKIP_DUPLICATE = "resume_duplicate"
SKIP_WINDOW = "out_of_window"


def decode(path: bytes) -> tuple[str, str, bool]:
    """按固定顺序试探解码: utf-8-sig → cp1252 → cp1252(替换坏字节)。

    返回 (文本, 采用的编码, 是否有坏字节)。UTF-8 带不带 BOM 都由第一个候选覆盖;
    cp1252 覆盖西文导出里的重音片名; 两者都失败时才替换, 并把坏行标出来跳过。
    """
    try:
        return path.decode("utf-8-sig"), "utf-8-sig", False
    except UnicodeDecodeError:
        pass
    try:
        return path.decode("cp1252"), "cp1252", False
    except UnicodeDecodeError:
        return path.decode("cp1252", errors="replace"), "cp1252", True


def duration_seconds(text: str) -> float | None:
    """`H:MM:SS` -> 秒; 格式不对返回 None, 不猜。"""
    match = DURATION_RE.match(text.strip())
    if match is None:
        return None
    hours, minutes, seconds = (int(part) for part in match.groups())
    return float(hours * 3600 + minutes * 60 + seconds)


def parse_title(raw: str) -> tuple[str, str | None, str | None]:
    """返回 (剧名, 季标签, 集名)。

    只认尾部 `: "集名"` 与倒数第二段的季标签 (`Season 2` / `Limited Series` / ...)。
    认不出来时剧名保持原样、季为 None —— 宁可少一个字段, 也不从标题里猜口味。
    """
    text = raw.strip()
    if not text:
        return "", None, None
    show, season, episode = text, None, None
    if text.endswith('"') and ': "' in text:
        head, _, tail = text.rpartition(': "')
        episode = tail[:-1].strip() or None
        segments = head.split(": ")
        if len(segments) > 1 and SEASON_RE.match(segments[-1]):
            season = segments[-1]
            show = ": ".join(segments[:-1])
        else:
            show = head
    return show.strip() or text, season, episode


def profile_hash(name: str) -> str:
    """档案名只以哈希形式参与去重键; 明文不进任何字段。"""
    return hashlib.sha256(name.encode()).hexdigest()[:16]


def row_hash(key: tuple[str, str, str], duration_s: float) -> str:
    """`sha256(source|profile_hash|title|start_time|max_duration)` 前 16 位。"""
    profile, title, start = key
    return hashlib.sha256(
        f"{SOURCE}|{profile}|{title}|{start}|{duration_s:.3f}".encode()
    ).hexdigest()[:16]


def candidate(
    row: dict[str, str],
) -> tuple[tuple[tuple[str, str, str], Event, float] | None, str | None]:
    """把一行 CSV 变成 (去重键, Event, 时长); 不能计入时返回 (None, 原因)。

    Event 的 `row_hash` 先留空: 它依赖去重后的最大时长, 由调用方统一补。
    """
    if any(REPLACEMENT in value for value in row.values()):
        return None, SKIP_BAD_ENCODING

    profile = row.get("Profile Name", "").strip()
    if not profile:
        return None, SKIP_EMPTY_PROFILE
    title_raw = row.get("Title", "").strip()
    if not title_raw:
        return None, SKIP_EMPTY_TITLE
    try:
        start = split_utc_and_offset(row.get("Start Time", ""))[0]
    except ValueError:
        return None, SKIP_BAD_START
    duration = duration_seconds(row.get("Duration", ""))
    if duration is None:
        return None, SKIP_BAD_DURATION

    supplemental = row.get("Supplemental Video Type", "").strip().upper()
    if supplemental in EXCLUDED_SUPPLEMENTAL:
        return None, SKIP_SUPPLEMENTAL
    if duration <= PREVIEW_MAX_S:
        return None, SKIP_PREVIEW

    show, season, episode = parse_title(title_raw)
    attributes = row.get("Attributes", "").strip()
    flags: dict[str, object] = {}
    if attributes:
        flags["attributes"] = attributes
        if "autoplay" in attributes.lower():
            flags["autoplay"] = True

    key = (profile_hash(profile), title_raw, start)
    event = Event(
        source=SOURCE,
        kind=KIND,
        ts_utc=start,
        tz_offset_min=None,
        title=title_raw,
        subtitle=show,
        category=season,
        duration_s=duration,
        value=1.0,
        flags=flags or None,
        meta={"episode": episode} if episode else None,
    )
    return (key, event, duration), None
