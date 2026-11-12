"""netflix 适配器: 字段映射、续播去重、档案合并、行账与 PII 丢弃。

编码矩阵在 `test_adapter_netflix_encoding.py`; 这里只测口径与结构。
"""

import csv
import io
import json
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from recapkits.adapters.base import IngestReport
from recapkits.adapters.netflix import NetflixAdapter, find_files
from recapkits.adapters.netflix_parse import parse_title
from recapkits.db import connect, count_events, init_schema
from recapkits.tz import rebuild_local

FIXTURES = Path(__file__).parent.parent / "fixtures" / "netflix"
TZ = "Asia/Shanghai"
YEAR = 2024

HEADER = (
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


def record(**overrides: str) -> dict[str, str]:
    """一条完整的观看记录; 覆盖字段即可造边界。"""
    row = {
        "Profile Name": "Alice",
        "Start Time": "2024-03-04 14:00:00",
        "Duration": "0:45:00",
        "Attributes": "",
        "Title": 'The Midnight Club: Season 1: "The Hour of the Wolf"',
        "Supplemental Video Type": "",
        "Device Type": "Chrome",
        "Bookmark": "0:00:00",
        "Latest Bookmark": "0:45:00",
        "Country": "US",
    }
    row.update(overrides)
    return row


def csv_bytes(rows: list[dict[str, str]], columns: tuple[str, ...] = HEADER) -> bytes:
    """按给定列序写 CSV; 全部字段加引号, 与真实导出一致。"""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n", quoting=csv.QUOTE_ALL)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row[column] for column in columns])
    return buffer.getvalue().encode()


def write_export(
    root: Path, rows: list[dict[str, str]], relative: str = "ViewingActivity.csv"
) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(csv_bytes(rows))
    return path


def ingest_dir(
    path: Path, *, tz: str = TZ, since: date | None = None
) -> tuple[sqlite3.Connection, IngestReport]:
    """在内存库里跑一次导入, 返回 (conn, report)。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    report = NetflixAdapter().ingest(path, conn, tz=tz, since=since)
    return conn, report


def test_detect_scores(tmp_path: Path) -> None:
    """根目录有 CSV 为 1.0, 只在子目录里找到为 0.8, 其余 0.0。"""
    adapter = NetflixAdapter()
    write_export(tmp_path, [record()])
    write_export(tmp_path, [record()], relative="Profiles/Bob/ViewingActivity.csv")

    assert adapter.detect(tmp_path) == 1.0
    assert adapter.detect(tmp_path / "Profiles") == 0.8
    assert adapter.detect(tmp_path / "missing") == 0.0
    assert len(find_files(tmp_path)) == 2


def test_field_mapping(tmp_path: Path) -> None:
    """剧名进 subtitle, 季进 category, 集名进 meta; 时长换秒。"""
    write_export(tmp_path, [record()])
    conn, report = ingest_dir(tmp_path)
    try:
        row = conn.execute("SELECT * FROM events").fetchone()
        assert row["source"] == "netflix"
        assert row["kind"] == "view"
        assert row["ts_utc"] == "2024-03-04T14:00:00Z"
        assert row["tz_offset_min"] is None
        assert row["title"] == 'The Midnight Club: Season 1: "The Hour of the Wolf"'
        assert row["subtitle"] == "The Midnight Club"
        assert row["category"] == "Season 1"
        assert json.loads(row["meta_json"]) == {"episode": "The Hour of the Wolf"}
        assert row["duration_s"] == 2700.0
        assert row["value"] == 1.0
        assert report.rows == 1 and report.skipped == 0
    finally:
        conn.close()


def test_title_with_colon_and_movie(tmp_path: Path) -> None:
    """剧名自带冒号时仍能取出剧名; 电影没有季与集。"""
    write_export(
        tmp_path,
        [
            record(Title='Star Trek: Discovery: Season 1: "The Vulcan Hello"'),
            record(Title="Amélie", **{"Start Time": "2024-03-05 14:00:00"}),
        ],
    )
    conn, _report = ingest_dir(tmp_path)
    try:
        rows = conn.execute(
            "SELECT subtitle, category, meta_json FROM events ORDER BY ts_utc"
        ).fetchall()
        assert rows[0]["subtitle"] == "Star Trek: Discovery"
        assert rows[0]["category"] == "Season 1"
        assert rows[1]["subtitle"] == "Amélie"
        assert rows[1]["category"] is None
        assert rows[1]["meta_json"] is None
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('Show: Season 2: "Ep"', ("Show", "Season 2", "Ep")),
        ('Star Trek: Discovery: Season 1: "Ep"', ("Star Trek: Discovery", "Season 1", "Ep")),
        ('Show: Limited Series: "Ep"', ("Show", "Limited Series", "Ep")),
        ('Show: Special: "Ep"', ("Show: Special", None, "Ep")),
        ('Show: "Ep"', ("Show", None, "Ep")),
        ("Movie", ("Movie", None, None)),
        ("", ("", None, None)),
    ],
)
def test_parse_title(raw: str, expected: tuple[str, str | None, str | None]) -> None:
    """认不出季就不猜; 剧名里的冒号不会被误切。"""
    assert parse_title(raw) == expected


def test_resume_duplicate_keeps_the_longest(tmp_path: Path) -> None:
    """短行排在前面也保留长行: 不是先到先得。"""
    write_export(
        tmp_path,
        [record(Duration="0:03:00"), record(Duration="0:45:00")],
    )
    conn, report = ingest_dir(tmp_path)
    try:
        row = conn.execute("SELECT duration_s FROM events").fetchone()
        assert row["duration_s"] == 2700.0
        assert report.rows == 1
        assert report.files[0].reasons == Counter({"resume_duplicate": 1})
    finally:
        conn.close()


def test_same_title_time_across_profiles_is_kept(tmp_path: Path) -> None:
    """档案在去重键里: 两个人在同一秒看同一集是两条记录。"""
    write_export(
        tmp_path,
        [record(**{"Profile Name": "Alice"}), record(**{"Profile Name": "Bob"})],
    )
    conn, report = ingest_dir(tmp_path)
    try:
        assert count_events(conn) == 2
        assert report.notes == ["已合并 2 个档案，未写入档案名"]  # noqa: RUF001
    finally:
        conn.close()


def test_preview_and_supplemental_are_skipped_with_reasons(tmp_path: Path) -> None:
    """1 秒 / 2 秒预览、HOOK/RECAP/TRAILER 各有各的原因。"""
    write_export(
        tmp_path,
        [
            record(Duration="0:00:01", **{"Start Time": "2024-03-04 14:00:01"}),
            record(Duration="0:00:02", **{"Start Time": "2024-03-04 14:00:02"}),
            record(Duration="0:00:03", **{"Start Time": "2024-03-04 14:00:03"}),
            record(**{"Supplemental Video Type": "hook", "Start Time": "2024-03-04 14:00:04"}),
            record(**{"Supplemental Video Type": "RECAP", "Start Time": "2024-03-04 14:00:05"}),
            record(**{"Supplemental Video Type": "TRAILER", "Start Time": "2024-03-04 14:00:06"}),
            record(**{"Supplemental Video Type": "BONUS", "Start Time": "2024-03-04 14:00:07"}),
        ],
    )
    conn, report = ingest_dir(tmp_path)
    try:
        assert count_events(conn) == 2
        assert report.files[0].reasons == Counter({"preview": 2, "supplemental": 3})
    finally:
        conn.close()


def test_bad_duration_and_empty_title_are_skipped(tmp_path: Path) -> None:
    """坏时长与空标题是跳过, 不是整份失败。"""
    write_export(
        tmp_path,
        [record(Duration="1:2:3"), record(Title=""), record(Duration="0:30:00")],
    )
    conn, report = ingest_dir(tmp_path)
    try:
        assert count_events(conn) == 1
        assert report.files[0].reasons == Counter({"bad_duration": 1, "empty_title": 1})
    finally:
        conn.close()


def test_profile_name_never_reaches_the_database(tmp_path: Path) -> None:
    """档案名只参与哈希; 表里搜不到明文, raw_row 仍为空。"""
    write_export(tmp_path, [record(**{"Profile Name": "DistinctiveProfileName"})])
    conn, _report = ingest_dir(tmp_path)
    try:
        dump = "\n".join(str(tuple(row)) for row in conn.execute("SELECT * FROM events"))
        assert "DistinctiveProfileName" not in dump
        assert conn.execute("SELECT COUNT(*) FROM raw_row").fetchone()[0] == 0
    finally:
        conn.close()


def test_ledger_identity_holds_per_file(tmp_path: Path) -> None:
    """逐文件: 解析 + 跳过 == 该文件的数据行数。"""
    write_export(tmp_path, [record()])
    write_export(
        tmp_path,
        [record(**{"Profile Name": "Bob"}), record(**{"Profile Name": "Bob"}, Duration="0:00:01")],
        relative="Profiles/Bob/ViewingActivity.csv",
    )
    _conn, report = ingest_dir(tmp_path)
    try:
        for ledger in report.files:
            path = tmp_path / ledger.name
            with path.open(encoding="utf-8", newline="") as handle:
                rows = sum(1 for _ in csv.reader(handle)) - 1
            assert ledger.rows + ledger.skipped == rows, ledger.name
            assert sum(ledger.reasons.values()) == ledger.skipped, ledger.name
    finally:
        _conn.close()


def test_headers_are_matched_by_name_not_position(tmp_path: Path) -> None:
    """列序不同也能读; 这是多档案导出的常态。"""
    shuffled = (
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
    path = tmp_path / "ViewingActivity.csv"
    path.write_bytes(csv_bytes([record()], shuffled))

    conn, _report = ingest_dir(tmp_path)
    try:
        row = conn.execute("SELECT subtitle, duration_s FROM events").fetchone()
        assert (row["subtitle"], row["duration_s"]) == ("The Midnight Club", 2700.0)
    finally:
        conn.close()


def test_unknown_columns_only_warn(tmp_path: Path) -> None:
    """多一列不该让整次导入失败。"""
    columns = (*HEADER, "Future Column")
    path = tmp_path / "ViewingActivity.csv"
    path.write_bytes(csv_bytes([record(**{"Future Column": "x"})], columns))

    conn, report = ingest_dir(tmp_path)
    try:
        assert report.rows == 1
        assert any("Future Column" in warning for warning in report.warnings)
    finally:
        conn.close()


def test_missing_required_column_names_file_and_column(tmp_path: Path) -> None:
    """缺必需列直接失败, 报错里要有文件名与列名。"""
    columns = tuple(column for column in HEADER if column != "Duration")
    (tmp_path / "ViewingActivity.csv").write_bytes(csv_bytes([record()], columns))

    with pytest.raises(ValueError, match=r"ViewingActivity\.csv.*Duration"):
        ingest_dir(tmp_path)


def test_missing_export_is_actionable(tmp_path: Path) -> None:
    """没有 CSV 时点名期望的文件名, 不是一句 FileNotFoundError。"""
    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(FileNotFoundError, match=r"ViewingActivity\.csv"):
        ingest_dir(empty)


def test_empty_file_is_a_problem_not_a_crash(tmp_path: Path) -> None:
    """空文件整份跳过; 另一份文件照常导入。"""
    write_export(tmp_path, [record()])
    (tmp_path / "Profiles" / "Empty").mkdir(parents=True)
    (tmp_path / "Profiles" / "Empty" / "ViewingActivity.csv").write_bytes(b"")

    conn, report = ingest_dir(tmp_path)
    try:
        assert count_events(conn) == 1
        problems = {ledger.name: ledger.problem for ledger in report.files}
        assert problems == {
            "ViewingActivity.csv": None,
            "Profiles/Empty/ViewingActivity.csv": "空文件",
        }
    finally:
        conn.close()


def test_since_uses_the_workspace_timezone(tmp_path: Path) -> None:
    """2023-12-31 16:30Z 在上海是 2024-01-01: 按 UTC 过滤会误删它。"""
    write_export(
        tmp_path,
        [
            record(**{"Start Time": "2023-12-31 16:30:00"}),
            record(**{"Start Time": "2024-01-01 00:30:00"}),
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


def test_reimport_is_idempotent(tmp_path: Path) -> None:
    """同一目录导入两次, 事件数不变。"""
    conn, first = ingest_dir(FIXTURES)
    try:
        before = count_events(conn)
        second = NetflixAdapter().ingest(FIXTURES, conn, tz=TZ)
        assert count_events(conn) == before
        assert (second.rows, second.skipped) == (first.rows, first.skipped)
    finally:
        conn.close()


def test_fixture_merges_two_profiles(tmp_path: Path) -> None:
    """合成导出有两个档案、两份不同列序的 CSV。"""
    conn = connect(tmp_path / "recap.db")
    init_schema(conn)
    try:
        report = NetflixAdapter().ingest(FIXTURES, conn, tz=TZ)
        rebuild_local(conn, TZ)
        assert report.units == 2
        assert report.notes == ["已合并 2 个档案，未写入档案名"]  # noqa: RUF001
        assert {ledger.name for ledger in report.files} == {
            "ViewingActivity.csv",
            "Profiles/Bob/ViewingActivity.csv",
        }
        assert count_events(conn) == report.rows
        assert report.rows > 150
    finally:
        conn.close()
