"""本地模式: 工作区策略、入口拒绝、以及「已有载荷不替你删」。

`--local-only` 不是每条命令的 flag, 而是 config 里的一个字段: 会忘的开关不是
隐私承诺。已有工作区也必须能切换, 否则早先建的工作区永远回不到本地模式。
"""

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from recapkits.cli import main
from recapkits.db import Event, connect, init_schema, insert_events
from recapkits.tz import rebuild_local, to_utc_iso

TZ = "Asia/Shanghai"
YEAR = 2024
BASE = datetime(2024, 1, 1, tzinfo=UTC)


def write_config(root: Path, *, local_only: bool | None = None, tz: str = TZ) -> Path:
    """只写 config; 拒绝类断言发生在读库之前, 所以不 seed 也能测。"""
    workspace = root / ".recapkits"
    workspace.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {"tz": tz, "year": YEAR, "created_at": "2024-01-01T00:00:00Z"}
    if local_only is not None:
        data["local_only"] = local_only
    path = workspace / "config.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def seed_events(root: Path) -> None:
    """40 个活跃日, 每天 2 条事件, 足够让 insights 产出多类洞察。"""
    events = [
        Event(
            source="git",
            kind="commit",
            ts_utc=to_utc_iso(BASE + timedelta(days=day, hours=(slot * 7) % 24)),
            tz_offset_min=480,
            title=f"c{day}-{slot}",
            subtitle=f"repo-{slot % 3}",
            value=1.0,
            row_hash=f"{day:04d}{slot:04d}00000000",
        )
        for day in range(40)
        for slot in range(2)
    ]
    conn = connect(root / ".recapkits" / "recap.db")
    try:
        init_schema(conn)
        insert_events(conn, events)
        rebuild_local(conn, TZ)
    finally:
        conn.close()


def read_config(root: Path) -> dict:
    return json.loads((root / ".recapkits" / "config.json").read_text(encoding="utf-8"))


def test_init_can_create_a_local_only_workspace(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["init", "--local-only", "--year", "2024"]) == 0

    assert read_config(tmp_path)["local_only"] is True
    assert "本地模式" in capsys.readouterr().out


def test_init_flips_the_policy_without_touching_tz_or_year(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path, tz="Europe/Berlin")

    assert main(["init", "--local-only"]) == 0

    data = read_config(tmp_path)
    assert data["local_only"] is True
    assert data["tz"] == "Europe/Berlin"
    assert data["year"] == YEAR
    assert data["created_at"] == "2024-01-01T00:00:00Z"
    assert "本地模式: 开" in capsys.readouterr().out


def test_init_can_turn_the_policy_off(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path, local_only=True)

    assert main(["init", "--no-local-only"]) == 0

    assert read_config(tmp_path)["local_only"] is False
    assert "本地模式: 关" in capsys.readouterr().out


def test_plain_init_still_does_not_overwrite(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path, local_only=True)

    assert main(["init", "--tz", "UTC"]) == 0

    assert "未覆盖" in capsys.readouterr().out
    assert read_config(tmp_path)["tz"] == TZ
    assert read_config(tmp_path)["local_only"] is True


def test_local_mode_writes_no_agent_payload(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path, local_only=True)
    seed_events(tmp_path)

    assert main(["insights"]) == 0

    workspace = tmp_path / ".recapkits"
    assert (workspace / "out" / "insights.json").is_file()
    assert not (workspace / "agent").exists()
    assert "本地模式" not in capsys.readouterr().out


def test_an_existing_agent_dir_is_kept_not_deleted(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path, local_only=True)
    seed_events(tmp_path)
    agent = tmp_path / ".recapkits" / "agent"
    agent.mkdir()
    stale = agent / "insights.json"
    stale.write_text("{}", encoding="utf-8")

    assert main(["insights"]) == 0

    assert stale.read_text(encoding="utf-8") == "{}"
    assert "未改写" in capsys.readouterr().out


def test_preview_is_refused_in_local_mode(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path, local_only=True)

    assert main(["insights", "--payload-preview"]) == 1

    assert "本地模式不生成外发载荷" in capsys.readouterr().err


def test_placeholder_is_refused_in_local_mode(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path, local_only=True)

    assert main(["insights", "--entities=placeholder"]) == 1

    assert "本地模式不生成外发载荷" in capsys.readouterr().err


def test_skill_install_is_refused_in_local_mode(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path, local_only=True)

    assert main(["skill", "install", "--target", "claude"]) == 1

    assert "本地模式" in capsys.readouterr().err
    assert not (tmp_path / ".claude").exists()


def test_doctor_reports_local_mode(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path, local_only=True)

    assert main(["doctor"]) == 0

    out = capsys.readouterr().out
    assert "策略" in out
    assert "本地模式" in out


def test_doctor_reports_the_default_policy(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    write_config(tmp_path, local_only=False)

    assert main(["doctor"]) == 0

    out = capsys.readouterr().out
    assert "策略" in out
    assert "默认" in out


def test_run_path_hides_the_agent_hint_in_local_mode(
    tmp_path: Path, monkeypatch, capsys, git_repo: Path
) -> None:
    from recapkits import run

    monkeypatch.chdir(tmp_path)
    write_config(tmp_path, local_only=True)
    monkeypatch.setattr(run, "require_node", lambda: None)

    code = run.cmd_run(
        argparse.Namespace(path=str(git_repo), tz=TZ, year=YEAR, top=10, no_auto=True)
    )

    out = capsys.readouterr().out
    assert code == 0
    assert "还没有故事" in out
    assert "交给它" not in out
