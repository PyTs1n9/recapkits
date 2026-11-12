"""载荷最小化: 字段取舍、体积账、preview 输出、幂等、以及「agent 版能自校验」。

最小化的价值不是字节数, 而是让 agent 只看到决策所需的东西; `series` 是唯一为了
校验而保留的非决策字段 —— 去掉它, 这份载荷就校验不了它自己催生的故事。
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from recapkits.cli import main
from recapkits.db import Event, connect, init_schema, insert_events
from recapkits.payload import DROPPED, KEPT, TOP_LEVEL, measure, minimize
from recapkits.tz import rebuild_local, to_utc_iso

TZ = "Asia/Shanghai"
YEAR = 2024
BASE = datetime(2024, 1, 1, tzinfo=UTC)


def _event(day: int, slot: int) -> Event:
    """40 个活跃日, 每天 2 条: 足够越过 time.* / conc.* 的闸门。"""
    moment = BASE + timedelta(days=day, hours=(slot * 7) % 24, minutes=slot)
    return Event(
        source="git",
        kind="commit",
        ts_utc=to_utc_iso(moment),
        tz_offset_min=480,
        title=f"c{day}-{slot}",
        subtitle=f"repo-{slot % 3}",
        value=1.0,
        row_hash=f"{day:04d}{slot:04d}00000000",
    )


def make_workspace(tmp_path: Path, *, local_only: bool = False) -> Path:
    """一个已初始化、有 80 条事件的工作区; 不依赖 git。"""
    root = tmp_path / ".recapkits"
    root.mkdir()
    config: dict[str, object] = {"tz": TZ, "year": YEAR, "created_at": "2024-01-01T00:00:00Z"}
    if local_only:
        config["local_only"] = True
    (root / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    conn = connect(root / "recap.db")
    try:
        init_schema(conn)
        insert_events(conn, [_event(day, slot) for day in range(40) for slot in range(2)])
        rebuild_local(conn, TZ)
    finally:
        conn.close()
    return root


def _keys(payload: dict) -> set[str]:
    return {key for item in payload["insights"] for key in item}


def test_minimize_keeps_the_decision_fields() -> None:
    payload = {
        "version": 1,
        "build_id": "b3:x",
        "generated_from": {"sources": ["git"]},
        "unknown_top": 1,
        "insights": [
            {
                "id": "vol.total:git:2024",
                "kind": "vol.total",
                "source": "git",
                "period": {},
                "headline_fact": {},
                "facts": [],
                "score": 0.5,
                "novelty": "constant",
                "sensitivity": "low",
                "data_sufficiency": "ok",
                "gated": [],
                "caveats": [],
                "series": {"axis": "hour", "keys": [], "values": [], "unit": "share"},
                "evidence_sql": "SELECT 1",
                "score_parts": {"signal": 1.0},
                "evidence_rows": 1,
                "mystery": True,
            }
        ],
    }

    agent = minimize(payload)

    assert set(agent) == {*TOP_LEVEL, "insights"}
    assert set(agent["insights"][0]) == set(KEPT)
    assert "mystery" not in agent["insights"][0]
    assert agent["insights"][0]["series"]["axis"] == "hour"


def test_minimize_does_not_touch_the_input() -> None:
    payload = {"version": 1, "insights": [{"id": "a", "score_parts": {"x": 1}, "facts": []}]}
    snapshot = json.dumps(payload, sort_keys=True)

    agent = minimize(payload)
    agent["insights"][0]["facts"].append("mutated")

    assert json.dumps(payload, sort_keys=True) == snapshot


def test_the_dropped_breakdown_adds_up_to_the_difference(tmp_path: Path, monkeypatch) -> None:
    """三行明细之和必须等于总差值; 用户会拿计算器对。"""
    monkeypatch.chdir(tmp_path)
    make_workspace(tmp_path)
    assert main(["insights"]) == 0
    payload = json.loads((tmp_path / ".recapkits" / "out" / "insights.json").read_text("utf-8"))

    measurement = measure(payload)

    assert sum(size for _, size in measurement.dropped) == measurement.saved_bytes
    assert [name for name, _ in measurement.dropped] == [
        name for name, _ in sorted(measurement.dropped, key=lambda pair: -pair[1])
    ]


def test_insights_writes_a_smaller_agent_payload(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    root = make_workspace(tmp_path)

    assert main(["insights"]) == 0

    full = json.loads((root / "out" / "insights.json").read_text(encoding="utf-8"))
    agent = json.loads((root / "agent" / "insights.json").read_text(encoding="utf-8"))
    assert _keys(agent).isdisjoint(DROPPED)
    assert "series" in _keys(agent)
    assert "score_parts" in _keys(full)
    assert len((root / "agent" / "insights.json").read_bytes()) < len(
        (root / "out" / "insights.json").read_bytes()
    )
    assert "已写入" in capsys.readouterr().out


def test_a_second_run_is_byte_identical(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    root = make_workspace(tmp_path)
    assert main(["insights"]) == 0
    first = (
        (root / "out" / "insights.json").read_bytes(),
        (root / "agent" / "insights.json").read_bytes(),
    )
    capsys.readouterr()

    assert main(["insights"]) == 0

    second = (
        (root / "out" / "insights.json").read_bytes(),
        (root / "agent" / "insights.json").read_bytes(),
    )
    assert first == second


def test_payload_preview_prints_three_lines(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    make_workspace(tmp_path)

    assert main(["insights", "--payload-preview"]) == 0

    out = capsys.readouterr().out
    assert "payload" in out
    assert "agent" in out
    assert "删除" in out
    for name in DROPPED:
        assert name in out
    assert "score_parts" not in (tmp_path / ".recapkits" / "agent" / "insights.json").read_text(
        encoding="utf-8"
    )


def test_preview_with_json_prints_only_the_agent_payload(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    make_workspace(tmp_path)

    assert main(["insights", "--payload-preview", "--json"]) == 0

    out = capsys.readouterr().out
    assert not out.startswith("payload")
    payload = json.loads(out)
    assert set(payload) == {*TOP_LEVEL, "insights"}
    assert _keys(payload).isdisjoint(DROPPED)


def test_plain_json_still_prints_the_full_payload(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    make_workspace(tmp_path)

    assert main(["insights", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert "score_parts" in _keys(payload)


def test_the_agent_payload_can_validate_its_own_story(tmp_path: Path, monkeypatch, capsys) -> None:
    """验收项: 最小版不需要还原就能给 --check 用。"""
    monkeypatch.chdir(tmp_path)
    root = make_workspace(tmp_path)
    assert main(["insights"]) == 0
    assert main(["story", "--auto"]) == 0
    capsys.readouterr()

    code = main(
        [
            "story",
            "--check",
            str(root / "story.json"),
            "--insights",
            str(root / "agent" / "insights.json"),
        ]
    )

    assert code == 0
    assert "通过" in capsys.readouterr().out
