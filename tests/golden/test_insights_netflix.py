"""netflix 黄金语料: 两个档案的合成导出 -> events -> insights.json 冻结。

语料由 `scripts/make-fixtures.py` 生成, 形状写死: 180 条入池观看、71 个活跃日、
The Midnight Club 占 34%、深夜 59%。快照只冻结构, 不冻截图。
"""

import json
import os
import sqlite3
from pathlib import Path

import pytest

from recapkits.adapters.netflix import NetflixAdapter
from recapkits.db import connect, count_events, init_schema
from recapkits.emit import render
from recapkits.insights import engine
from recapkits.tz import rebuild_local

FIXTURES = Path(__file__).parent.parent / "fixtures" / "netflix"
SNAPSHOT = Path(__file__).parent / "snapshots" / "netflix_2024.insights.json"
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
    NetflixAdapter().ingest(FIXTURES, conn, tz=tz)
    rebuild_local(conn, tz)
    return conn


def payload_of(conn: sqlite3.Connection, tz: str = TZ) -> dict[str, object]:
    """跑一遍引擎并渲染成 insights.json 的结构。"""
    selected = engine.select(engine.run(conn, tz=tz, year=YEAR), top=10)
    return render(selected, sources=["netflix"], event_count=count_events(conn), tz=tz)


@pytest.fixture
def netflix_db(tmp_path: Path) -> sqlite3.Connection:
    conn = build_db(tmp_path / "recap.db")
    yield conn
    conn.close()


def test_all_eight_kinds_appear(netflix_db: sqlite3.Connection) -> None:
    """样本量够, 8 个 kind 一个不少。"""
    assert {insight.kind for insight in engine.run(netflix_db, tz=TZ, year=YEAR)} == FULL_KINDS


def test_top_entity_is_a_show(netflix_db: sqlite3.Connection) -> None:
    """实体类别词是 show; 榜单里是剧名, 不是季或集。"""
    conc = next(
        insight
        for insight in engine.run(netflix_db, tz=TZ, year=YEAR)
        if insight.kind == "conc.top_entity"
    )

    assert conc.id.startswith("conc.top_entity:show:")
    assert conc.facts[0].label == "The Midnight Club"
    assert all(not fact.label.startswith("Season") for fact in conc.facts)


def test_profile_names_do_not_reach_insights(netflix_db: sqlite3.Connection) -> None:
    """档案名既不在库里, 也不在 insights.json 里。"""
    text = json.dumps(payload_of(netflix_db), ensure_ascii=False)

    for name in ("Alice", "Bob"):
        assert name not in text


def test_every_evidence_sql_runs(netflix_db: sqlite3.Connection) -> None:
    for insight in engine.run(netflix_db, tz=TZ, year=YEAR):
        rows = netflix_db.execute(insight.evidence_sql).fetchall()
        assert len(rows) == insight.evidence_rows, insight.id
        assert rows, insight.id


def test_snapshot_matches(netflix_db: sqlite3.Connection) -> None:
    """整份 insights.json 与快照逐字节比对。"""
    actual = json.dumps(payload_of(netflix_db), ensure_ascii=False, indent=2) + "\n"

    if os.environ.get("RECAP_UPDATE_SNAPSHOT") == "1":
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(actual, encoding="utf-8")

    assert actual == SNAPSHOT.read_text(encoding="utf-8")


def test_workspace_timezone_moves_the_hour_rhythm(tmp_path: Path) -> None:
    """同一份导出, 上海与纽约的深夜占比必须不同 (tz_offset_min 不是 0)。"""
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
    assert shares["sh"] - shares["ny"] > 0.1
