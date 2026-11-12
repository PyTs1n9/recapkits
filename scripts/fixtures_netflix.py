"""netflix ViewingActivity.csv 合成导出: 两个档案、续播重复、预览与 supplemental。

由 `make-fixtures.py` 调用; 固定 seed, 只产出字节, 不写盘。

刻意保留的脏点: 剧名自带冒号 (`Star Trek: Discovery`)、集名带逗号、法语片名、
同一 (档案, 剧名, 开始时间) 的短行排在长行之前 (锁住「保留最大时长」)、
1 秒与 2 秒预览、HOOK/RECAP/TRAILER、空标题与坏时长。
"""

import csv
import io
import random
from datetime import date, datetime, timedelta

SEED = 20241113

#: 真实导出的列顺序; Bob 的文件用另一套顺序, 逼适配器按列名取值而不是按下标。
COLUMNS = (
    "Profile Name",
    "Start Time",
    "Duration",
    "Attributes",
    "Title",
    "Supplemental Video Type",
    "Device Type",
    "Bookmark",
    "Latest Bookmark",
    "Country",
)
BOB_COLUMNS = (
    "Start Time",
    "Profile Name",
    "Title",
    "Duration",
    "Country",
    "Attributes",
    "Supplemental Video Type",
    "Device Type",
    "Bookmark",
    "Latest Bookmark",
)

SHOWS = (
    ("The Midnight Club", "Season 1", ("The Hour of the Wolf", "The Two Danvers"), 26),
    ("怪奇物语", "Season 4", ("第一章：失联", "第二章：枫树街"), 18),  # noqa: RUF001
    ("The Crown", "Season 6", ("Persona Non Grata, Part 1", "Two Photographs"), 12),
    ("Star Trek: Discovery", "Season 1", ("The Vulcan Hello", "Battle at the Binary Stars"), 8),
    ("黑镜", "Season 3", ("急转直下", "黑色博物馆"), 6),
)
MOVIES = ("The Irishman", "Amélie", "Roma", "Spirited Away")


def _duration(total_seconds: int) -> str:
    """`H:MM:SS`; Netflix 的小时不补零。"""
    hours, rest = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}"


def _timestamp(moment: datetime) -> str:
    """`YYYY-MM-DD HH:MM:SS`, 无偏移; 导出里的 Start Time 就是这个形状。"""
    return (
        f"{moment.year:04d}-{moment.month:02d}-{moment.day:02d} "
        f"{moment.hour:02d}:{moment.minute:02d}:{moment.second:02d}"
    )


def _weighted() -> list[tuple[str, str, tuple[str, ...]]]:
    """把权重展开成可 `choice` 的列表, 顺序固定。"""
    pool: list[tuple[str, str, tuple[str, ...]]] = []
    for show, season, episodes, weight in SHOWS:
        pool.extend([(show, season, episodes)] * weight)
    return pool


def _active_days(rng: random.Random) -> list[date]:
    """每周一个观看日 + 11 月一段连续 8 天。"""
    days = [date(2024, 1, 8) + timedelta(days=7 * week + rng.randint(0, 1)) for week in range(38)]
    days.extend(date(2024, 11, 1) + timedelta(days=offset) for offset in range(8))
    return sorted(set(days))


def _base_row(profile: str, moment: datetime, duration: int, title: str) -> dict[str, str]:
    """一条观看记录; supplemental / 属性由调用方覆盖。"""
    return {
        "Profile Name": profile,
        "Start Time": _timestamp(moment),
        "Duration": _duration(duration),
        "Attributes": "",
        "Title": title,
        "Supplemental Video Type": "",
        "Device Type": "Chrome",
        "Bookmark": "0:00:00",
        "Latest Bookmark": _duration(duration),
        "Country": "US",
    }


def _view(rng: random.Random, day: date, index: int, profile: str, serial: int) -> dict[str, str]:
    """一条普通观看; 12% 是电影, 其余是剧集。"""
    hour = rng.choice([14, 15, 16, 17, 6, 7])
    moment = datetime(day.year, day.month, day.day, hour, (index * 17) % 60, (index * 29) % 60)
    if rng.random() < 0.12:
        title = MOVIES[serial % len(MOVIES)]
        duration = rng.choice([95, 108, 127]) * 60
    else:
        show, season, episodes = rng.choice(_weighted())
        episode = episodes[serial % len(episodes)]
        title = f'{show}: {season}: "{episode}"'
        duration = rng.choice([42, 47, 52, 58]) * 60
    row = _base_row(profile, moment, duration, title)
    if serial % 17 == 0:
        row["Attributes"] = "Autoplay"
    return row


def _edge_rows(day: date, profile: str) -> list[dict[str, str]]:
    """预览、supplemental、空标题、坏时长; 每一条都对应一个跳过原因。"""
    rows: list[dict[str, str]] = []
    for offset, seconds in enumerate((1, 1, 1, 2, 2)):
        row = _base_row(
            profile,
            datetime(day.year, day.month, day.day, 12, offset, 0),
            seconds,
            'The Midnight Club: Season 1: "The Hour of the Wolf"',
        )
        rows.append(row)
    for offset, (kind, seconds) in enumerate(
        (("HOOK", 45), ("HOOK", 30), ("RECAP", 70), ("TRAILER", 140), ("TRAILER", 95))
    ):
        row = _base_row(
            profile,
            datetime(day.year, day.month, day.day, 11, offset, 0),
            seconds,
            '怪奇物语: Season 4: "第一章：失联"',  # noqa: RUF001
        )
        row["Supplemental Video Type"] = kind
        rows.append(row)
    rows.append(_base_row(profile, datetime(day.year, day.month, day.day, 10, 0, 0), 1800, ""))
    broken = _base_row(profile, datetime(day.year, day.month, day.day, 10, 30, 0), 1800, "Roma")
    broken["Duration"] = "1:2:3"
    rows.append(broken)
    return rows


def _insert_resume_pairs(rows: list[dict[str, str]], picks: list[int]) -> None:
    """在长行之前插一条同 key 的短行: 「保留最大时长」不能靠先到先得。"""
    for pick in sorted(picks, reverse=True):
        if pick >= len(rows):
            continue
        original = rows[pick]
        short = {**original, "Duration": _duration(180), "Latest Bookmark": _duration(180)}
        rows.insert(pick, short)


def _dump(rows: list[dict[str, str]], columns: tuple[str, ...]) -> bytes:
    """按给定列序写 CSV; LF 行尾, 全部字段加引号 (真实导出就是这样)。"""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n", quoting=csv.QUOTE_ALL)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row[column] for column in columns])
    return buffer.getvalue().encode()


def build() -> dict[str, bytes]:
    """返回 {相对 tests/fixtures: 文件字节}。"""
    rng = random.Random(SEED)
    days = _active_days(rng)

    alice: list[dict[str, str]] = []
    serial = 0
    for day in days:
        for index in range(rng.choice([2, 3, 3, 4])):
            alice.append(_view(rng, day, index, "Alice", serial))
            serial += 1
    alice.extend(_edge_rows(days[0], "Alice"))
    alice.sort(key=lambda row: row["Start Time"])
    _insert_resume_pairs(alice, [12, 55, 98, 140])

    bob: list[dict[str, str]] = []
    for day in days[::3]:
        for index in range(rng.choice([2, 2, 3])):
            bob.append(_view(rng, day, index, "Bob", serial + index))
        serial += 3
    bob.sort(key=lambda row: row["Start Time"])
    _insert_resume_pairs(bob, [8, 18])

    return {
        "netflix/ViewingActivity.csv": _dump(alice, COLUMNS),
        "netflix/Profiles/Bob/ViewingActivity.csv": _dump(bob, BOB_COLUMNS),
    }
