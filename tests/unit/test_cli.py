"""CLI 行为: 工作区、退出码、幂等、产物落盘。"""

import json
from pathlib import Path

from recapkits.cli import main


def test_init_writes_config_and_gitignore(tmp_path: Path, monkeypatch) -> None:
    """init 建目录、写配置、把 .recapkits/ 加进 .gitignore。"""
    monkeypatch.chdir(tmp_path)

    assert main(["init", "--tz", "Asia/Shanghai", "--year", "2024"]) == 0

    config = json.loads((tmp_path / ".recapkits" / "config.json").read_text(encoding="utf-8"))
    assert config["tz"] == "Asia/Shanghai"
    assert config["year"] == 2024
    assert config["created_at"].endswith("Z")
    assert ".recapkits/" in (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_init_does_not_overwrite(tmp_path: Path, monkeypatch, capsys) -> None:
    """工作区已存在时只提示, 不改配置。"""
    monkeypatch.chdir(tmp_path)
    main(["init", "--year", "2024"])
    capsys.readouterr()

    assert main(["init", "--year", "2025"]) == 0

    config = json.loads((tmp_path / ".recapkits" / "config.json").read_text(encoding="utf-8"))
    assert config["year"] == 2024
    assert "已存在" in capsys.readouterr().out


def test_insights_without_workspace_fails(tmp_path: Path, monkeypatch, capsys) -> None:
    """没有工作区时给一句可操作的话, 退出码 1。"""
    monkeypatch.chdir(tmp_path)

    assert main(["insights"]) == 1
    assert "recap init" in capsys.readouterr().err


def test_import_then_insights_writes_artifact(tmp_path: Path, monkeypatch, git_repo: Path) -> None:
    """端到端: init -> import -> insights 产出 insights.json。"""
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--year", "2024"]) == 0
    assert main(["import", str(git_repo), "--source", "git"]) == 0
    assert main(["insights", "--top", "5"]) == 0

    payload = json.loads(
        (tmp_path / ".recapkits" / "out" / "insights.json").read_text(encoding="utf-8")
    )
    assert payload["generated_from"]["event_count"] == 3
    assert payload["insights"]


def test_reimport_keeps_event_count(tmp_path: Path, monkeypatch, git_repo: Path, capsys) -> None:
    """同一仓库导入两次, doctor 里的事件数不变。"""
    monkeypatch.chdir(tmp_path)
    main(["init", "--year", "2024"])
    main(["import", str(git_repo), "--source", "git"])
    capsys.readouterr()

    assert main(["import", str(git_repo), "--source", "git"]) == 0
    assert "新增" in capsys.readouterr().out

    assert main(["doctor"]) == 0
    assert "3 条事件" in capsys.readouterr().out


def test_bad_date_is_reported_before_adapter_lookup(tmp_path: Path, monkeypatch, capsys) -> None:
    """日期格式错误优先于"找不到仓库"报出来, 否则用户会改错地方。"""
    monkeypatch.chdir(tmp_path)
    main(["init", "--year", "2024"])
    capsys.readouterr()

    assert main(["import", str(tmp_path), "--source", "git", "--since", "2026/01/01"]) == 1
    assert "YYYY-MM-DD" in capsys.readouterr().err
