"""测试共享夹具。"""

import os
import sqlite3
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from recapkits.db import connect, init_schema
from recapkits.insights.model import day_keys

GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "Test Author",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test Author",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}

#: 固定日期 + 固定消息; 配合 `--allow-empty` 得到跨平台一致的提交哈希。
COMMITS = (
    ("2024-03-11T23:41:07+08:00", "feat: 第一个提交"),
    ("2024-03-12T09:05:00+08:00", "fix: 第二个提交"),
    ("2024-05-02T08:00:00+08:00", "docs: 第三个提交"),
)


def run_git(repo: Path, *args: str, extra_env: dict[str, str] | None = None) -> str:
    """在指定仓库里执行 git, 身份与时间由环境变量固定。"""
    env = dict(os.environ)
    env.update(GIT_IDENTITY)
    if extra_env:
        env.update(extra_env)
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        env=env,
    )
    return completed.stdout


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """空的、已按契约建表的数据库连接。"""
    connection = connect(tmp_path / "recap.db")
    init_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """三次提交、日期与消息都固定的仓库。"""
    path = tmp_path / "demo-repo"
    path.mkdir()
    run_git(path, "init", "-q")
    for when, message in COMMITS:
        run_git(
            path,
            "commit",
            "--allow-empty",
            "-q",
            "-m",
            message,
            extra_env={"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when},
        )
    return path


def _fact(key: str, label: str, value: float | str, unit: str | None, display: str) -> dict:
    return {"key": key, "label": label, "value": value, "unit": unit, "display": display}


def _insight(
    ident: str,
    kind: str,
    headline: dict,
    facts: list[dict],
    *,
    series: dict | None = None,
    sensitivity: str = "low",
) -> dict:
    """构造一条最小的 insights.json 记录; 只填校验与烘焙会读的字段。"""
    payload = {
        "id": ident,
        "kind": kind,
        "source": "git",
        "period": {
            "start": "2024-01-01",
            "end": "2024-12-31",
            "tz": "Asia/Shanghai",
            "coverage": 0.5,
        },
        "headline_fact": headline,
        "facts": facts,
        "evidence_sql": "SELECT 1",
        "evidence_rows": 1,
        "score": 0.5,
        "score_parts": {"signal": 0.5, "deviation": 0.0, "discontinuity": 0.0, "sensitivity": 0.0},
        "novelty": "constant",
        "sensitivity": sensitivity,
        "data_sufficiency": "ok",
        "gated": ["deviation", "discontinuity"],
        "caveats": [],
    }
    if series is not None:
        payload["series"] = series
    return payload


@pytest.fixture
def cards_payload() -> dict:
    """四种卡片所需的完整洞察集: ranking / heatmap / clock / summary-grid。

    刻意包含一个 12 字中文仓库名与一个全零日期, 供边界用例复用。
    """
    keys = day_keys("2024-01-01", "2024-12-31")
    daily = [0.0] * len(keys)
    for offset in (0, 30, 60, 100, 200, 300, 365):
        daily[offset] = 3.0

    hour_facts = [_fact(f"h{hour:02d}", f"{hour} 点", 9, "count", "9") for hour in range(24)]
    hour_values = [1 / 24] * 24

    return {
        "version": 1,
        "build_id": "b3:cards",
        "generated_from": {"sources": ["git"], "event_count": 220, "tz": "Asia/Shanghai"},
        "insights": [
            _insight(
                "vol.total:git:2024",
                "vol.total",
                _fact("events", "事件总数", 220, "count", "220"),
                [
                    _fact("active_days", "活跃天数", 46, "count", "46"),
                    _fact("daily_avg", "日均事件", 4.78, "count", "4.8"),
                ],
            ),
            _insight(
                "conc.top_entity:repo:alpha:2024",
                "conc.top_entity",
                _fact("share", "占全部事件的比重", 0.62, "pct", "62%"),
                [
                    _fact("rank_1", "一个特别特别长的仓库名字", 137, "count", "137"),
                    _fact("rank_2", "beta", 21, "count", "21"),
                    _fact("rank_3", "delta", 21, "count", "21"),
                    _fact("rank_4", "gamma", 21, "count", "21"),
                    _fact("rank_5", "epsilon", 21, "count", "21"),
                    _fact("share", "占全部事件的比重", 0.62, "pct", "62%"),
                ],
            ),
            _insight(
                "vol.daily_series:git:2024",
                "vol.daily_series",
                _fact("events", "窗口内事件数", 21, "count", "21"),
                [_fact("days", "窗口天数", 366, "count", "366")],
                series={"axis": "day", "keys": keys, "values": daily, "unit": "count"},
            ),
            _insight(
                "time.hour_rhythm:git:2024",
                "time.hour_rhythm",
                _fact("late_night_share", "深夜占比 22:00-03:00", 0.38, "pct", "38%"),
                [
                    *hour_facts,
                    _fact("peak_hour", "最活跃小时", "2 点", None, "2 点"),
                ],
                series={
                    "axis": "hour",
                    "keys": [str(hour) for hour in range(24)],
                    "values": hour_values,
                    "unit": "share",
                },
            ),
        ],
    }
