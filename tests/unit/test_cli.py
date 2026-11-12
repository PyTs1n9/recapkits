"""CLI 行为: 工作区、退出码、幂等、产物落盘。"""

import json
from pathlib import Path

import pytest

from recapkits.cli import main
from recapkits.db import connect

SPOTIFY = Path(__file__).parent.parent / "fixtures" / "spotify"


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


def test_import_report_uses_review_window_coverage(
    tmp_path: Path, monkeypatch, git_repo: Path
) -> None:
    """导入报告的覆盖率与 period.coverage 同一口径: 活跃日 / 窗口天数。"""
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--year", "2024"]) == 0
    assert main(["import", str(git_repo), "--source", "git"]) == 0

    conn = connect(tmp_path / ".recapkits" / "recap.db")
    try:
        row = conn.execute("SELECT coverage FROM import_reports").fetchone()
    finally:
        conn.close()

    # 3 个活跃日 / 2024 年 366 天
    assert row["coverage"] == pytest.approx(3 / 366, abs=1e-4)


def test_import_report_prints_window(tmp_path: Path, monkeypatch, git_repo: Path, capsys) -> None:
    """打印的覆盖率必须带上分母, 否则读者会误读。"""
    monkeypatch.chdir(tmp_path)
    main(["init", "--year", "2024"])
    capsys.readouterr()

    assert main(["import", str(git_repo), "--source", "git"]) == 0
    assert "窗口 2024-01-01 至 2024-12-31" in capsys.readouterr().out


def test_import_auto_detects_spotify(tmp_path: Path, monkeypatch, capsys) -> None:
    """不给 --source 时, 按 detect 最高分选中 spotify。"""
    monkeypatch.chdir(tmp_path)
    main(["init", "--year", "2024"])
    capsys.readouterr()

    assert main(["import", str(SPOTIFY)]) == 0
    assert "源        spotify" in capsys.readouterr().out


def test_import_auto_refuses_ambiguous_directory(
    tmp_path: Path, monkeypatch, git_repo: Path, capsys
) -> None:
    """同时像 git 与 spotify 的目录: 报错要求显式指定, 不按字母序偷选。"""
    monkeypatch.chdir(tmp_path)
    main(["init", "--year", "2024"])
    (git_repo / "Streaming_History_Audio_2024_0.json").write_text("[]", encoding="utf-8")
    capsys.readouterr()

    assert main(["import", str(git_repo)]) == 1
    err = capsys.readouterr().err
    assert "同时像" in err
    assert "--source" in err


def test_import_prints_a_ledger_for_every_file(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """逐文件账必须能查: 文件名、解析数、跳过数与原因。"""
    monkeypatch.chdir(tmp_path)
    main(["init", "--year", "2024"])
    capsys.readouterr()

    assert main(["import", str(SPOTIFY), "--source", "spotify"]) == 0

    out = capsys.readouterr().out
    assert "逐文件" in out
    assert "Streaming_History_Audio_2023-2024_0.json" in out
    assert "incognito 1" in out
    assert "short_play 3" in out


def test_spotify_insights_are_byte_identical_after_reimport(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """导入两次 + 两次 insights, 产物逐字节相同, 事件数不变。"""
    monkeypatch.chdir(tmp_path)
    main(["init", "--year", "2024"])
    main(["import", str(SPOTIFY), "--source", "spotify"])
    main(["insights", "--top", "10"])
    first = (tmp_path / ".recapkits" / "out" / "insights.json").read_bytes()
    capsys.readouterr()

    assert main(["import", str(SPOTIFY), "--source", "spotify"]) == 0
    assert main(["insights", "--top", "10"]) == 0
    second = (tmp_path / ".recapkits" / "out" / "insights.json").read_bytes()

    assert first == second
    assert main(["doctor"]) == 0
    assert "209 条事件" in capsys.readouterr().out
