"""netflix 编码矩阵: 每种编码与每类边界的实际结果。

验收要求逐格写清「解析 / 跳过 / 报错」及原因。这里的每一格都是一条真实断言,
最终表格由 `pytest -q` 的结果汇总而来, 不是手写的期望表。
"""

import csv
import io
import sqlite3
from pathlib import Path

import pytest

from recapkits.adapters.netflix import NetflixAdapter
from recapkits.db import init_schema

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
DEFAULT_TITLE = 'The Midnight Club: Season 1: "The Hour of the Wolf"'


def csv_text(title: str = DEFAULT_TITLE) -> str:
    """一行有效数据; 行尾统一 LF, 需要别的编码由调用方转换。"""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n", quoting=csv.QUOTE_ALL)
    writer.writerow(HEADER)
    writer.writerow(
        [
            "Alice",
            "2024-03-04 14:00:00",
            "0:45:00",
            "",
            title,
            "",
            "Chrome",
            "0:00:00",
            "0:45:00",
            "US",
        ]
    )
    return buffer.getvalue()


def run(tmp_path: Path, payload: bytes):
    """把字节写成一个导出目录, 跑一次导入; 返回 (rows, skipped, reasons, problem, titles)。"""
    (tmp_path / "ViewingActivity.csv").write_bytes(payload)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    try:
        report = NetflixAdapter().ingest(tmp_path, conn, tz="Asia/Shanghai")
        rows = conn.execute("SELECT title FROM events").fetchall()
        ledger = report.files[0]
        return (
            report.rows,
            report.skipped,
            dict(ledger.reasons),
            ledger.problem,
            [row["title"] for row in rows],
        )
    finally:
        conn.close()


def test_plain_utf8(tmp_path: Path) -> None:
    rows, skipped, _reasons, problem, titles = run(tmp_path, csv_text().encode())
    assert (rows, skipped, problem) == (1, 0, None)
    assert titles == [DEFAULT_TITLE]


def test_utf8_with_bom(tmp_path: Path) -> None:
    """BOM 不能变成第一列列名的一部分。"""
    rows, skipped, _reasons, problem, _ = run(tmp_path, b"\xef\xbb\xbf" + csv_text().encode())
    assert (rows, skipped, problem) == (1, 0, None)


def test_cp1252_accents(tmp_path: Path) -> None:
    """西文导出用 cp1252: 重音片名不能变成乱码。"""
    rows, skipped, _reasons, problem, titles = run(tmp_path, csv_text("Amélie").encode("cp1252"))
    assert (rows, skipped, problem) == (1, 0, None)
    assert titles == ["Amélie"]


def test_crlf_line_endings(tmp_path: Path) -> None:
    rows, skipped, _reasons, problem, _ = run(tmp_path, csv_text().replace("\n", "\r\n").encode())
    assert (rows, skipped, problem) == (1, 0, None)


def test_embedded_comma_and_quote(tmp_path: Path) -> None:
    """集名里的逗号与引号由 csv 模块处理; 原串要一字不差。"""
    title = 'The Crown: Season 6: "Persona Non Grata, Part 1"'
    rows, skipped, _reasons, problem, titles = run(tmp_path, csv_text(title).encode())
    assert (rows, skipped, problem) == (1, 0, None)
    assert titles == [title]


def test_bad_byte_is_skipped_not_fatal(tmp_path: Path) -> None:
    """0x81 在 utf-8 与 cp1252 里都非法: 该行跳过, 原因写明是编码问题。"""
    payload = csv_text("BADMARK").encode().replace(b"BADMARK", b"Bad\x81Title")
    rows, skipped, reasons, problem, _ = run(tmp_path, payload)
    assert (rows, skipped, problem) == (0, 1, None)
    assert reasons == {"bad_encoding": 1}


def test_nul_line_is_one_bad_row(tmp_path: Path) -> None:
    """孤立的 NUL 行被当成行数不符: 跳过一行, 不崩掉整个导入。"""
    rows, skipped, reasons, problem, _ = run(tmp_path, csv_text().encode() + b"\x00\n")
    assert (rows, skipped, problem) == (1, 1, None)
    assert reasons == {"bad_row": 1}


def test_oversized_field_is_a_file_level_problem(tmp_path: Path) -> None:
    """超过 csv 的字段上限时整份文件记为结构错误, 不是崩掉整个导入。"""
    payload = csv_text("x" * 200_000).encode()
    rows, skipped, _reasons, problem, _ = run(tmp_path, payload)
    assert (rows, skipped) == (0, 0)
    assert problem == "CSV 结构错误"


def test_empty_file_is_reported(tmp_path: Path) -> None:
    rows, skipped, _reasons, problem, _ = run(tmp_path, b"")
    assert (rows, skipped) == (0, 0)
    assert problem == "空文件"


def test_blank_lines_are_counted(tmp_path: Path) -> None:
    """空行也进账: 解析 1 + 跳过 1 == 2 个数据行。"""
    rows, skipped, reasons, problem, _ = run(tmp_path, csv_text().encode() + b"\n")
    assert (rows, skipped, problem) == (1, 1, None)
    assert reasons == {"blank": 1}


def test_missing_column_is_an_error(tmp_path: Path) -> None:
    """表头不成立时失败并指名列, 不猜。"""
    columns = tuple(column for column in HEADER if column != "Start Time")
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n", quoting=csv.QUOTE_ALL)
    writer.writerow(columns)
    writer.writerow(
        ["Alice", "0:45:00", "", DEFAULT_TITLE, "", "Chrome", "0:00:00", "0:45:00", "US"]
    )
    (tmp_path / "ViewingActivity.csv").write_bytes(buffer.getvalue().encode())

    with pytest.raises(ValueError, match=r"ViewingActivity\.csv.*Start Time"):
        run(tmp_path, buffer.getvalue().encode())
