"""spotify 黄金语料: 合成导出 -> events -> insights.json 逐字节冻结。

语料由 `scripts/make-fixtures.py` 生成, 形状写死: 203 条入池播放、66 个活跃日、
The Midnight 占 44%、深夜时段占一半以上。快照只冻结构, 不冻截图。
"""

import json
import os
import sqlite3
from pathlib import Path

import pytest

from recapkits.adapters.spotify import SpotifyAdapter
from recapkits.db import connect, count_events, init_schema
from recapkits.emit import render
from recapkits.insights import engine
from recapkits.tz import rebuild_local

FIXTURES = Path(__file__).parent.parent / "fixtures" / "spotify"
SNAPSHOT = Path(__file__).parent / "snapshots" / "spotify_2024.insights.json"
TZ = "Asia/Shanghai"
YEAR = 2024
FULL_KINDS = {
    "vol.total",
    "vol.busiest_day",
    "vol.daily_series",
    "conc.top_entity",
    "time.hour_rhythm",
    "time.weekday_rhythm",
    "disc.longest_streak",
    "disc.longest_gap",
}


def build_db(path: Path, tz: str = TZ) -> sqlite3.Connection:
    """在 path 建库并导入 fixture, 再按 tz 重建本地日。"""
    conn = connect(path)
    init_schema(conn)
    SpotifyAdapter().ingest(FIXTURES, conn, tz=tz)
    rebuild_local(conn, tz)
    return conn


def payload_of(conn: sqlite3.Connection, tz: str = TZ) -> dict[str, object]:
    """跑一遍引擎并渲染成 insights.json 的结构。"""
    selected = engine.select(engine.run(conn, tz=tz, year=YEAR), top=10)
    return render(selected, sources=["spotify"], event_count=count_events(conn), tz=tz)


@pytest.fixture
def spotify_db(tmp_path: Path) -> sqlite3.Connection:
    """已导入黄金语料的库; 用完关闭。"""
    conn = build_db(tmp_path / "recap.db")
    yield conn
    conn.close()


def test_all_eight_kinds_appear(spotify_db: sqlite3.Connection) -> None:
    """样本量够, 8 个 kind 一个不少。"""
    found = engine.run(spotify_db, tz=TZ, year=YEAR)

    assert {insight.kind for insight in found} == FULL_KINDS


def test_top_entity_is_an_artist_not_a_podcast(spotify_db: sqlite3.Connection) -> None:
    """实体类别词是 artist; 播客只贡献时长, 不进集中度。"""
    conc = next(
        insight
        for insight in engine.run(spotify_db, tz=TZ, year=YEAR)
        if insight.kind == "conc.top_entity"
    )

    assert conc.id.startswith("conc.top_entity:artist:")
    assert conc.facts[0].label == "The Midnight"
    assert all("硬地骇客" not in fact.label for fact in conc.facts)


def test_every_evidence_sql_runs(spotify_db: sqlite3.Connection) -> None:
    """每条 evidence_sql 都能直接执行, 行数与 evidence_rows 一致。"""
    for insight in engine.run(spotify_db, tz=TZ, year=YEAR):
        rows = spotify_db.execute(insight.evidence_sql).fetchall()
        assert len(rows) == insight.evidence_rows, insight.id
        assert rows, insight.id


def test_pii_does_not_reach_insights_json(spotify_db: sqlite3.Connection) -> None:
    """国家与 IP 既不进库, 也不进 insights.json —— HTML 只从这份数据渲染。"""
    text = json.dumps(payload_of(spotify_db), ensure_ascii=False)

    for token in ("203.0.113.42", "198.51.100.77", "192.0.2.15", "conn_country", "ip_addr"):
        assert token not in text


def test_snapshot_matches(spotify_db: sqlite3.Connection) -> None:
    """整份 insights.json 与快照逐字节比对。"""
    actual = json.dumps(payload_of(spotify_db), ensure_ascii=False, indent=2) + "\n"

    if os.environ.get("RECAP_UPDATE_SNAPSHOT") == "1":
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(actual, encoding="utf-8")

    assert actual == SNAPSHOT.read_text(encoding="utf-8")


def test_workspace_timezone_moves_the_hour_rhythm(tmp_path: Path) -> None:
    """同一份导出, 上海与纽约的深夜占比必须不同。

    若两次相同, 说明 `tz_offset_min` 被写成了 0, 本地小时被锁死在 UTC。
    """
    shares: dict[str, float] = {}
    for name, tz in (("sh", TZ), ("ny", "America/New_York")):
        conn = build_db(tmp_path / name / "recap.db", tz)
        try:
            hour = next(
                insight
                for insight in engine.run(conn, tz=tz, year=YEAR)
                if insight.kind == "time.hour_rhythm"
            )
            shares[name] = float(hour.headline_fact.value)
        finally:
            conn.close()

    assert shares["sh"] > shares["ny"]
    assert shares["sh"] - shares["ny"] > 0.2
