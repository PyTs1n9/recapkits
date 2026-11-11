"""git 适配器端到端: 临时仓库 -> events -> 洞察。

仓库用 `--allow-empty` 建, 提交哈希只取决于作者/提交时间与消息, 三平台一致。
黄金语料与快照在 test_corpus.py, 这里只验证适配器与薄数据闸门的衔接。
"""

import subprocess
from pathlib import Path

from recapkits.adapters.git_local import GitAdapter, find_repos
from recapkits.db import connect, count_events, init_schema
from recapkits.insights import engine
from recapkits.tz import rebuild_local

TZ = "Asia/Shanghai"
YEAR = 2024


def test_detect_scores(tmp_path: Path, git_repo: Path) -> None:
    """仓库本身 1.0, 只含仓库的目录 0.8, 空目录 0.0。"""
    adapter = GitAdapter()
    empty = tmp_path / "empty"
    empty.mkdir()

    assert adapter.detect(git_repo) == 1.0
    assert adapter.detect(tmp_path) == 0.8
    assert adapter.detect(empty) == 0.0


def test_find_repos_skips_noise(tmp_path: Path) -> None:
    """node_modules 里的仓库不应被计入。"""
    noise = tmp_path / "node_modules" / "nested"
    noise.mkdir(parents=True)
    subprocess.run(
        ["git", "-C", str(noise), "init", "-q"], check=True, capture_output=True, text=True
    )

    assert find_repos(tmp_path) == []


def test_ingest_parses_commits(tmp_path: Path, git_repo: Path) -> None:
    """一个 commit 一条事件, 作者时间转 UTC, 偏移原样保留。"""
    conn = connect(tmp_path / "recap.db")
    init_schema(conn)
    try:
        report = GitAdapter().ingest(git_repo, conn)

        assert (report.units, report.rows, report.skipped) == (1, 3, 0)
        assert report.first_ts == "2024-03-11T15:41:07Z"
        assert report.last_ts == "2024-05-02T00:00:00Z"
        assert report.warnings == []

        rows = conn.execute(
            "SELECT ts_utc, tz_offset_min, title, subtitle, value FROM events ORDER BY ts_utc"
        ).fetchall()
        assert [tuple(row) for row in rows] == [
            ("2024-03-11T15:41:07Z", 480, "feat: 第一个提交", "demo-repo", 1.0),
            ("2024-03-12T01:05:00Z", 480, "fix: 第二个提交", "demo-repo", 1.0),
            ("2024-05-02T00:00:00Z", 480, "docs: 第三个提交", "demo-repo", 1.0),
        ]
    finally:
        conn.close()


def test_ingest_twice_keeps_count(tmp_path: Path, git_repo: Path) -> None:
    """同一仓库导入两次, 计数不变。"""
    conn = connect(tmp_path / "recap.db")
    init_schema(conn)
    try:
        adapter = GitAdapter()
        adapter.ingest(git_repo, conn)
        adapter.ingest(git_repo, conn)

        assert count_events(conn) == 3
    finally:
        conn.close()


def test_empty_repo_is_tolerated(tmp_path: Path) -> None:
    """刚 init 的仓库没有提交, 应当得到 0 行而不是异常。"""
    empty = tmp_path / "fresh"
    empty.mkdir()
    subprocess.run(
        ["git", "-C", str(empty), "init", "-q"], check=True, capture_output=True, text=True
    )

    conn = connect(tmp_path / "recap.db")
    init_schema(conn)
    try:
        report = GitAdapter().ingest(empty, conn)

        assert (report.rows, report.skipped) == (0, 0)
    finally:
        conn.close()


def test_git_pipeline_is_marked_insufficient(tmp_path: Path, git_repo: Path) -> None:
    """三次提交、三个活跃日: 端到端跑通, 并如实标成数据不足。"""
    conn = connect(tmp_path / "recap.db")
    init_schema(conn)
    try:
        GitAdapter().ingest(git_repo, conn)
        rebuild_local(conn, TZ)
        found = engine.run(conn, tz=TZ, year=YEAR)

        assert [insight.kind for insight in found] == ["vol.total"]
        assert found[0].data_sufficiency == "insufficient"
        for insight in found:
            rows = conn.execute(insight.evidence_sql).fetchall()
            assert len(rows) == insight.evidence_rows
    finally:
        conn.close()
