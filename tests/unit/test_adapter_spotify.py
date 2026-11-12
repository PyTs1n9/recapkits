"""spotify 适配器: 字段映射、口径、行账、幂等与 PII 丢弃。

所有用例都用合成数据。真实导出永不进仓库, 也不该成为测试的前提。
"""

import json
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from recapkits.adapters.base import IngestReport
from recapkits.adapters.spotify import SpotifyAdapter
from recapkits.db import Event, connect, count_events, init_schema, insert_events
from recapkits.insights import engine
from recapkits.tz import rebuild_local

FIXTURES = Path(__file__).parent.parent / "fixtures" / "spotify"
TZ = "Asia/Shanghai"
YEAR = 2024

NEW_KEYS = {
    "ts": "2024-03-04T14:00:00Z",
    "platform": "windows",
    "ms_played": 180_000,
    "conn_country": "QQ",
    "ip_addr": "192.0.2.9",
    "master_metadata_track_name": "夜航",
    "master_metadata_album_artist_name": "The Midnight",
    "master_metadata_album_album_name": "Endless Summer",
    "spotify_track_uri": "spotify:track:abc",
    "episode_name": None,
    "episode_show_name": None,
    "spotify_episode_uri": None,
    "reason_start": "clickrow",
    "reason_end": "trackdone",
    "shuffle": True,
    "skipped": False,
    "offline": False,
    "incognito_mode": False,
}


def export_row(**overrides: object) -> dict[str, object]:
    """一条完整的新格式记录; 覆盖字段即可造边界。"""
    return {**NEW_KEYS, **overrides}


def podcast_row(**overrides: object) -> dict[str, object]:
    """播客: 元数据全为 null, 只有节目名与时长。"""
    row = export_row(
        master_metadata_track_name=None,
        master_metadata_album_artist_name=None,
        master_metadata_album_album_name=None,
        spotify_track_uri=None,
        episode_name="第 12 期 - 上",
        episode_show_name="硬地骇客",
        spotify_episode_uri="spotify:episode:0001",
    )
    row.update(overrides)
    return row


def write_export(root: Path, name: str, rows: list[object]) -> Path:
    """把一组记录写成 `Streaming_History_Audio_*.json`。"""
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return path


def ingest_dir(
    path: Path,
    *,
    tz: str = TZ,
    since: date | None = None,
    until: date | None = None,
) -> tuple[sqlite3.Connection, IngestReport]:
    """在内存库里跑一次导入, 返回 (conn, report); 调用方负责关闭。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    report = SpotifyAdapter().ingest(path, conn, tz=tz, since=since, until=until)
    return conn, report


def test_detect_scores(tmp_path: Path) -> None:
    """目录本身有导出为 1.0, 只在子目录里发现有 0.8, 其余 0.0。"""
    adapter = SpotifyAdapter()
    flat = tmp_path / "flat"
    flat.mkdir()
    write_export(flat, "Streaming_History_Audio_2024_0.json", [export_row()])
    nested = tmp_path / "nested"
    write_export(nested / "inner", "Streaming_History_Audio_2024_0.json", [export_row()])

    assert adapter.detect(flat) == 1.0
    assert adapter.detect(nested) == 0.8
    assert adapter.detect(tmp_path / "missing") == 0.0


def test_new_schema_field_mapping(tmp_path: Path) -> None:
    """ts 走 UTC, 时长换秒, 标题/副标题/分类与 uri 各就各位。"""
    write_export(tmp_path, "Streaming_History_Audio_2024_0.json", [export_row()])
    conn, _report = ingest_dir(tmp_path)
    try:
        row = conn.execute("SELECT * FROM events").fetchone()
        assert row["source"] == "spotify"
        assert row["kind"] == "play"
        assert row["ts_utc"] == "2024-03-04T14:00:00Z"
        assert row["tz_offset_min"] is None
        assert row["title"] == "夜航"
        assert row["subtitle"] == "The Midnight"
        assert row["category"] == "Endless Summer"
        assert row["duration_s"] == 180.0
        assert row["value"] == 1.0
        assert json.loads(row["meta_json"]) == {"uri": "spotify:track:abc"}
        flags = json.loads(row["flags"])
        assert flags["reason_end"] == "trackdone" and flags["shuffle"] is True
    finally:
        conn.close()


def test_old_schema_is_supported(tmp_path: Path) -> None:
    """老格式: endTime 无偏移按 UTC 归一, trackName/artistName 仍能落位。"""
    write_export(
        tmp_path,
        "Streaming_History_Audio_2015-2022_0.json",
        [
            {
                "endTime": "2022-03-05 21:15:00",
                "artistName": "旧版艺人",
                "trackName": "旧版曲目",
                "msPlayed": 187_000,
            }
        ],
    )
    conn, _report = ingest_dir(tmp_path)
    try:
        row = conn.execute("SELECT * FROM events").fetchone()
        assert row["ts_utc"] == "2022-03-05T21:15:00Z"
        assert row["tz_offset_min"] is None
        assert (row["title"], row["subtitle"]) == ("旧版曲目", "旧版艺人")
    finally:
        conn.close()


def test_new_schema_wins_when_both_present(tmp_path: Path) -> None:
    """两套字段同时出现时, 新版非空才用新版。"""
    write_export(
        tmp_path,
        "Streaming_History_Audio_2024_0.json",
        [export_row(trackName="旧标题", artistName="旧艺人")],
    )
    conn, _report = ingest_dir(tmp_path)
    try:
        row = conn.execute("SELECT title, subtitle FROM events").fetchone()
        assert (row["title"], row["subtitle"]) == ("夜航", "The Midnight")
    finally:
        conn.close()


def test_filters_record_a_reason_for_every_skip(tmp_path: Path) -> None:
    """不足 30 秒、恰好 30 秒、incognito 各走各的原因; 30 秒+1 毫秒保留。"""
    write_export(
        tmp_path,
        "Streaming_History_Audio_2024_0.json",
        [
            export_row(ms_played=30_000, spotify_track_uri="spotify:track:exact"),
            export_row(ms_played=30_001, spotify_track_uri="spotify:track:over"),
            export_row(ms_played=29_999, spotify_track_uri="spotify:track:under"),
            export_row(ms_played=200_000, incognito_mode=True),
            export_row(ms_played=None),
        ],
    )
    conn, report = ingest_dir(tmp_path)
    try:
        assert report.rows == 1
        assert report.skipped == 4
        assert report.files[0].reasons == Counter(
            {"short_play": 2, "incognito": 1, "missing_ms_played": 1}
        )
        assert count_events(conn) == 1
    finally:
        conn.close()


def test_podcast_is_counted_but_has_no_entity(tmp_path: Path) -> None:
    """播客计入时长, 但 title/subtitle 为空, 不进「出现最多的项目」。"""
    write_export(tmp_path, "Streaming_History_Audio_2024_0.json", [podcast_row()])
    conn, _report = ingest_dir(tmp_path)
    try:
        row = conn.execute("SELECT title, subtitle, category, duration_s FROM events").fetchone()
        assert row["title"] is None and row["subtitle"] is None
        assert row["category"] == "硬地骇客"
        assert row["duration_s"] == 180.0
    finally:
        conn.close()


def test_podcasts_never_enter_concentration(conn: sqlite3.Connection) -> None:
    """60 条播客 + 10 条艺人: 集中度只认艺人, 分母仍是全部事件。"""
    events = [
        Event(
            source="spotify",
            kind="play",
            ts_utc=f"2024-03-{day + 1:02d}T14:00:00Z",
            title=None,
            subtitle=None,
            category="硬地骇客",
            duration_s=1800.0,
            value=1.0,
            row_hash=f"pod{day}{index}",
        )
        for day in range(5)
        for index in range(12)
    ]
    events += [
        Event(
            source="spotify",
            kind="play",
            ts_utc=f"2024-03-{day + 1:02d}T15:00:00Z",
            title="夜航",
            subtitle="The Midnight",
            duration_s=200.0,
            value=1.0,
            row_hash=f"art{day}{index}",
        )
        for day in range(5)
        for index in range(2)
    ]
    insert_events(conn, events)
    rebuild_local(conn, TZ)

    conc = next(
        item for item in engine.run(conn, tz=TZ, year=YEAR) if item.kind == "conc.top_entity"
    )

    assert conc.id.startswith("conc.top_entity:artist:%54he%20%4didnight")
    assert conc.headline_fact.value == pytest.approx(10 / 70, abs=1e-4)
    assert all("硬地骇客" not in fact.label for fact in conc.facts)
    assert len(conn.execute(conc.evidence_sql).fetchall()) == 1


def test_pii_never_reaches_the_database(tmp_path: Path) -> None:
    """conn_country / ip_addr 入库即丢弃; raw_row 保持为空。"""
    write_export(tmp_path, "Streaming_History_Audio_2024_0.json", [export_row()])
    conn, _report = ingest_dir(tmp_path)
    try:
        dump = "\n".join(
            str(row)
            for table in ("events", "event_local", "import_reports", "raw_row")
            for row in conn.execute(f"SELECT * FROM {table}")
        )
        for token in ("QQ", "192.0.2.9", "conn_country", "ip_addr"):
            assert token not in dump
        assert conn.execute("SELECT COUNT(*) FROM raw_row").fetchone()[0] == 0
    finally:
        conn.close()


def test_ledger_identity_holds_per_file(tmp_path: Path) -> None:
    """逐文件: 解析 + 跳过 == 数组元素数, 且原因计数之和等于跳过数。"""
    conn, report = ingest_dir(FIXTURES)
    try:
        for ledger in report.files:
            if ledger.problem:
                assert ledger.rows == 0 and ledger.skipped == 0
                continue
            rows = json.loads((FIXTURES / ledger.name).read_text(encoding="utf-8"))
            assert ledger.rows + ledger.skipped == len(rows), ledger.name
            assert sum(ledger.reasons.values()) == ledger.skipped, ledger.name
    finally:
        conn.close()


def test_broken_file_only_warns(tmp_path: Path) -> None:
    """坏 JSON 整份跳过, 其余文件照常导入。"""
    write_export(tmp_path, "Streaming_History_Audio_2024_0.json", [export_row()])
    (tmp_path / "Streaming_History_Audio_2024_9.json").write_text("[{", encoding="utf-8")

    conn, report = ingest_dir(tmp_path)
    try:
        assert count_events(conn) == 1
        assert any("不是合法 JSON" in warning for warning in report.warnings)
        assert any(ledger.problem for ledger in report.files)
    finally:
        conn.close()


def test_top_level_object_is_a_problem(tmp_path: Path) -> None:
    """顶层必须是数组; 对象只记问题, 不猜结构。"""
    (tmp_path / "Streaming_History_Audio_2024_0.json").write_text("{}", encoding="utf-8")

    conn, report = ingest_dir(tmp_path)
    try:
        assert report.rows == 0
        assert report.files[0].problem == "顶层不是数组"
    finally:
        conn.close()


def test_missing_required_field_names_file_and_field(tmp_path: Path) -> None:
    """合法 JSON 但一行都解析不出来: 失败并指名文件与字段。"""
    write_export(
        tmp_path,
        "Streaming_History_Audio_2024_0.json",
        [{"artistName": "旧艺人", "msPlayed": 60_000}],
    )

    with pytest.raises(ValueError, match=r"Streaming_History_Audio_2024_0\.json.*ts"):
        ingest_dir(tmp_path)


def test_reimport_is_idempotent(tmp_path: Path) -> None:
    """同一目录导入两次, 事件数与行账都不变。"""
    conn, first = ingest_dir(FIXTURES)
    try:
        before = count_events(conn)
        second = SpotifyAdapter().ingest(FIXTURES, conn, tz=TZ)

        assert count_events(conn) == before
        assert (second.rows, second.skipped) == (first.rows, first.skipped)
    finally:
        conn.close()


def test_same_second_different_tracks_are_not_deduped(tmp_path: Path) -> None:
    """同一 ts 的两首不同曲目都是真实播放, 不许按时间戳去重。"""
    write_export(
        tmp_path,
        "Streaming_History_Audio_2024_0.json",
        [
            export_row(spotify_track_uri="spotify:track:a", ms_played=100_000),
            export_row(spotify_track_uri="spotify:track:b", ms_played=120_000),
        ],
    )
    conn, _report = ingest_dir(tmp_path)
    try:
        assert count_events(conn) == 2
    finally:
        conn.close()


def test_duplicate_rows_across_files_are_merged(tmp_path: Path) -> None:
    """同一行出现在两个文件里只留一条, 两个文件各自都记账。"""
    row = export_row()
    write_export(tmp_path, "Streaming_History_Audio_2024_0.json", [row])
    write_export(tmp_path, "Streaming_History_Audio_2024_1.json", [dict(row)])

    conn, report = ingest_dir(tmp_path)
    try:
        assert count_events(conn) == 1
        assert [ledger.rows for ledger in report.files] == [1, 1]
        assert report.rows == 2
    finally:
        conn.close()


def test_unknown_fields_are_warned_once_per_file(tmp_path: Path) -> None:
    """未知字段只警告, 不影响解析。"""
    write_export(
        tmp_path,
        "Streaming_History_Audio_2024_0.json",
        [export_row(brand_new_field="x")],
    )
    conn, report = ingest_dir(tmp_path)
    try:
        assert report.rows == 1
        assert any("brand_new_field" in warning for warning in report.warnings)
    finally:
        conn.close()


def test_since_until_use_the_workspace_timezone(tmp_path: Path) -> None:
    """2023-12-31T16:30Z 在上海是 2024-01-01: 按 UTC 过滤会误删它。"""
    write_export(
        tmp_path,
        "Streaming_History_Audio_2024_0.json",
        [
            export_row(ts="2023-12-31T16:30:00Z", spotify_track_uri="spotify:track:sh"),
            export_row(ts="2024-01-01T00:30:00Z", spotify_track_uri="spotify:track:utc"),
        ],
    )

    shanghai, _ = ingest_dir(tmp_path, tz=TZ, since=date(2024, 1, 1))
    utc, _ = ingest_dir(tmp_path, tz="UTC", since=date(2024, 1, 1))
    try:
        assert count_events(shanghai) == 2
        assert count_events(utc) == 1
    finally:
        shanghai.close()
        utc.close()


def test_missing_export_is_an_actionable_error(tmp_path: Path) -> None:
    """目录里没有导出文件时, 报错要点名期望的文件名。"""
    empty = tmp_path / "empty"
    empty.mkdir()

    conn = connect(tmp_path / "recap.db")
    init_schema(conn)
    try:
        with pytest.raises(FileNotFoundError, match="Streaming_History_Audio_"):
            SpotifyAdapter().ingest(empty, conn)
    finally:
        conn.close()
