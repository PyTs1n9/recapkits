#!/usr/bin/env python3
"""生成合成导出 fixture: 固定 seed, 逐字节可复现。

真实导出**永不进 git**: 一行 IP、一个档案名就足够反查到具体的人。本脚本只产出
合成数据, `--check` 只比对不写盘, CI 与验收命令用它证明 fixture 没有被手改。

数据刻意做脏, 每条脏点都对应一个适配器用例:

- 新旧两套字段名 (2023 前后的 Spotify 导出格式不同)
- 播客/有声书的 master_metadata_* 为 null
- 不足 30 秒、恰好 30000 毫秒、incognito 的行
- 跨文件重复的同一行 (同一 ts、同一 uri、同一时长)
- 坏 JSON、未知字段、以及 conn_country / ip_addr 这类 PII
"""

import argparse
import hashlib
import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
SEED = 20241112

#: 每个播放至少 30 秒才计入; 恰好在边界上的行用来锁住 `>` 而不是 `>=`。
MIN_PLAY_MS = 30_000

ARTISTS = (
    ("The Midnight", "Endless Summer", 30),
    ("小岛工作室", "死亡搁浅", 12),
    ("A.B. Cee", "Dots", 10),
    ("LOONA", "[12:00]", 8),
    ("龘龘乐队", "龙吟", 6),
    ("Ólafur Arnalds", "Island Songs", 5),
)

SHOWS = (("硬地骇客", "第 12 期"), ("一天世界", "第 88 期"))

#: RFC 5737 文档保留地址; 它们看起来像 IP, 但不是任何人的真实地址。
IPS = ("203.0.113.42", "198.51.100.77", "192.0.2.15")
COUNTRIES = ("SE", "ZZ", "US")


def _iso_utc(moment: datetime) -> str:
    """`YYYY-MM-DDTHH:MM:SSZ`; 不经过本地时区, 也不依赖 strftime。"""
    return (
        f"{moment.year:04d}-{moment.month:02d}-{moment.day:02d}"
        f"T{moment.hour:02d}:{moment.minute:02d}:{moment.second:02d}Z"
    )


def _weighted() -> list[tuple[str, str]]:
    """把权重展开成可 `choice` 的列表, 顺序固定。"""
    pool: list[tuple[str, str]] = []
    for artist, album, weight in ARTISTS:
        pool.extend([(artist, album)] * weight)
    return pool


def _active_days(rng: random.Random) -> list[date]:
    """每周一个听歌日 + 11 月一段连续 8 天: 既够 30 个活跃日, 又有明显空档。"""
    days = [date(2024, 1, 3) + timedelta(days=7 * week + rng.randint(0, 1)) for week in range(34)]
    days.extend(date(2024, 11, 4) + timedelta(days=offset) for offset in range(8))
    return sorted(set(days))


def _play(
    rng: random.Random,
    day: date,
    index: int,
    *,
    track_serial: int,
) -> dict[str, object]:
    """一条新格式播放记录; 字段顺序与真实导出一致。"""
    artist, album = rng.choice(_weighted())
    hour = rng.choice([14, 15, 16, 17, 6, 7, 8])
    moment = datetime(day.year, day.month, day.day, hour, (index * 7) % 60, (index * 13) % 60)
    ms = rng.choice([180_000, 210_000, 240_000, 300_000, 45_000, 61_000])
    uri = "spotify:track:" + hashlib.sha256(f"{artist}|{track_serial}".encode()).hexdigest()[:22]
    return {
        "ts": _iso_utc(moment),
        "platform": "windows",
        "ms_played": ms,
        "conn_country": COUNTRIES[track_serial % len(COUNTRIES)],
        "ip_addr": IPS[track_serial % len(IPS)],
        "master_metadata_track_name": f"曲目 {track_serial:03d}",
        "master_metadata_album_artist_name": artist,
        "master_metadata_album_album_name": album,
        "spotify_track_uri": uri,
        "episode_name": None,
        "episode_show_name": None,
        "spotify_episode_uri": None,
        "reason_start": "clickrow",
        "reason_end": "trackdone",
        "shuffle": track_serial % 2 == 0,
        "skipped": False,
        "offline": False,
        "offline_timestamp": 0,
        "incognito_mode": False,
    }


def _podcast(day: date, index: int, serial: int) -> dict[str, object]:
    """播客: 元数据全为 null, 计入时长但不产生实体。"""
    show, episode = SHOWS[serial % len(SHOWS)]
    moment = datetime(day.year, day.month, day.day, 15, (index * 11) % 60, 0)
    return {
        "ts": _iso_utc(moment),
        "platform": "android",
        "ms_played": 1_500_000 + serial * 1000,
        "conn_country": COUNTRIES[serial % len(COUNTRIES)],
        "ip_addr": IPS[serial % len(IPS)],
        "master_metadata_track_name": None,
        "master_metadata_album_artist_name": None,
        "master_metadata_album_album_name": None,
        "spotify_track_uri": None,
        "episode_name": f"{episode} - 第 {serial} 段",
        "episode_show_name": show,
        "spotify_episode_uri": f"spotify:episode:{serial:022d}",
        "reason_start": "clickrow",
        "reason_end": "endplay",
        "shuffle": False,
        "skipped": False,
        "offline": False,
        "offline_timestamp": 0,
        "incognito_mode": False,
    }


def _edge_rows(day: date) -> list[dict[str, object]]:
    """边界行: 恰好 30 秒、30 秒+1 毫秒、不足 30 秒、incognito、未知字段。"""
    base = {
        "platform": "ios",
        "conn_country": "ZZ",
        "ip_addr": IPS[0],
        "master_metadata_track_name": "边界曲目",
        "master_metadata_album_artist_name": "Edge Case",
        "master_metadata_album_album_name": "Boundaries",
        "spotify_track_uri": "spotify:track:boundary",
        "episode_name": None,
        "episode_show_name": None,
        "spotify_episode_uri": None,
        "reason_start": "trackdone",
        "reason_end": "trackdone",
        "shuffle": False,
        "skipped": False,
        "offline": False,
        "offline_timestamp": 0,
        "incognito_mode": False,
    }
    rows: list[dict[str, object]] = []
    for offset, ms in enumerate((30_000, 30_001, 29_999, 8_000)):
        rows.append(
            {
                **base,
                "ts": _iso_utc(datetime(day.year, day.month, day.day, 13, offset, 0)),
                "ms_played": ms,
            }
        )
    rows.append(
        {
            **base,
            "ts": _iso_utc(datetime(day.year, day.month, day.day, 23, 0, 0)),
            "ms_played": 200_000,
            "incognito_mode": True,
        }
    )
    rows.append(
        {
            **base,
            "ts": _iso_utc(datetime(day.year, day.month, day.day, 12, 0, 0)),
            "ms_played": 190_000,
            "spotify_track_uri": "spotify:track:unknown-field",
            "brand_new_export_field": "ignored",
        }
    )
    return rows


def _old_rows() -> list[dict[str, object]]:
    """2023 年前的老格式: 无 ts、无 URI, 只有 endTime / trackName / artistName。"""
    rows: list[dict[str, object]] = []
    for index in range(6):
        rows.append(
            {
                "endTime": f"2022-0{index + 3}-1{index} 21:15:00",
                "artistName": "旧版艺人",
                "trackName": f"旧版曲目 {index}",
                "msPlayed": 180_000 + index * 1000,
            }
        )
    return rows


def build_spotify() -> dict[str, bytes]:
    """返回 {相对 tests/fixtures: 文件字节}。"""
    rng = random.Random(SEED)
    days = _active_days(rng)
    rows: list[dict[str, object]] = []
    serial = 0

    for day in days:
        for index in range(rng.choice([3, 4, 4, 5, 5, 6])):
            rows.append(_play(rng, day, index, track_serial=serial))
            serial += 1
        if serial % 5 == 0:
            rows.append(_podcast(day, serial, serial))
            serial += 1

    rows.extend(_edge_rows(days[0]))
    rows.sort(key=lambda row: str(row["ts"]))

    split = len(rows) // 2
    first, second = rows[:split], rows[split:]
    # 跨文件重复: 同一 ts、同一 uri、同一时长, 导入后只能留一条。
    second = second + [dict(row) for row in first[:5]]
    second.sort(key=lambda row: str(row["ts"]))

    old = _old_rows()
    broken = b'[{"ts": "2024-12-01T00:00:00Z", "ms_played": 180000,\n'

    def dump(items: list[dict[str, object]]) -> bytes:
        return (json.dumps(items, ensure_ascii=False, indent=2) + "\n").encode()

    return {
        "spotify/Streaming_History_Audio_2023-2024_0.json": dump(first),
        "spotify/Streaming_History_Audio_2024_1.json": dump(second),
        "spotify/Streaming_History_Audio_2015-2022_0.json": dump(old),
        "spotify/Streaming_History_Audio_2024_broken.json": broken,
    }


def build() -> dict[str, bytes]:
    """所有源的 fixture; 新源在这里追加一行。"""
    return build_spotify()


def _check(expected: dict[str, bytes]) -> int:
    """逐字节比对; 任何差异都算失败, 并列出文件名。"""
    drifted: list[str] = []
    for relative, payload in expected.items():
        path = FIXTURES / relative
        if not path.is_file() or path.read_bytes() != payload:
            drifted.append(relative)
    if drifted:
        for relative in drifted:
            print(f"与生成结果不一致: {relative}", file=sys.stderr)
        return 1
    print(f"fixture 与生成结果一致: {len(expected)} 个文件")
    return 0


def _write(expected: dict[str, bytes]) -> int:
    for relative, payload in expected.items():
        path = FIXTURES / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    print(f"已写入 {len(expected)} 个文件到 {FIXTURES}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成合成导出 fixture (固定 seed)")
    parser.add_argument("--check", action="store_true", help="只比对, 不写盘")
    args = parser.parse_args(argv)
    expected = build()
    return _check(expected) if args.check else _write(expected)


if __name__ == "__main__":
    raise SystemExit(main())
