"""`recap skill install`: 四个 target、幂等、标记块、--force、本地模式。

落点只允许在当前项目内 —— 装到用户家目录的 skill 无法被 CI 测试, 也不该由
一个工作区命令决定。
"""

import hashlib
import json
from pathlib import Path

from recapkits.cli import main
from recapkits.skill import read_text
from recapkits.skill.install import BLOCK_END, BLOCK_START

CLAUDE = Path(".claude") / "skills" / "recapkits" / "SKILL.md"
CURSOR = Path(".cursor") / "rules" / "recapkits.mdc"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frontmatter_and_body(text: str) -> tuple[str, str]:
    end = text.find("\n---\n", 3)
    assert end != -1
    return text[4:end], text[end + len("\n---\n") :]


def _local_only(root: Path) -> None:
    """一个只带策略字段的工作区; 其余配置与 load_workspace 的必填项对齐。"""
    workspace = root / ".recapkits"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "config.json").write_text(
        json.dumps({"tz": "Asia/Shanghai", "year": 2024, "local_only": True}),
        encoding="utf-8",
    )


def test_claude_target_writes_the_skill_verbatim(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["skill", "install", "--target", "claude"]) == 0

    written = (tmp_path / CLAUDE).read_text(encoding="utf-8")
    assert written == read_text()
    assert "已写入" in capsys.readouterr().out


def test_cursor_target_swaps_the_frontmatter(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["skill", "install", "--target", "cursor"]) == 0

    text = (tmp_path / CURSOR).read_text(encoding="utf-8")
    front, body = _frontmatter_and_body(text)
    assert "description:" in front
    assert "alwaysApply: false" in front
    assert "name:" not in front
    assert body == _frontmatter_and_body(read_text())[1]
    capsys.readouterr()


def test_agents_target_appends_a_block_and_strips_frontmatter(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    original = "# 我的规则\n\n- 用 uv\n".encode()
    (tmp_path / "AGENTS.md").write_bytes(original)

    assert main(["skill", "install", "--target", "agents"]) == 0

    raw = (tmp_path / "AGENTS.md").read_bytes()
    assert raw.startswith(original)
    text = raw.decode("utf-8")
    assert BLOCK_START in text
    assert BLOCK_END in text
    assert "name: recapkits" not in text
    capsys.readouterr()


def test_agents_block_replaces_in_place_and_keeps_the_edges(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "AGENTS.md").write_text(
        f"用户内容\n\n{BLOCK_START}\n旧内容\n{BLOCK_END}\n尾巴\n", encoding="utf-8"
    )

    assert main(["skill", "install", "--target", "agents"]) == 0

    text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert text.startswith("用户内容\n\n")
    assert text.endswith("尾巴\n")
    assert "旧内容" not in text
    assert text.count(BLOCK_START) == 1
    capsys.readouterr()


def test_a_second_install_is_unchanged(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["skill", "install", "--target", "claude"]) == 0
    before = _sha(tmp_path / CLAUDE)
    capsys.readouterr()

    assert main(["skill", "install", "--target", "claude"]) == 0

    assert "未改动" in capsys.readouterr().out
    assert _sha(tmp_path / CLAUDE) == before


def test_a_different_file_needs_force(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / CLAUDE
    path.parent.mkdir(parents=True)
    path.write_text("old\n", encoding="utf-8")

    assert main(["skill", "install", "--target", "claude"]) == 1

    assert "加 --force 覆盖" in capsys.readouterr().err
    assert path.read_text(encoding="utf-8") == "old\n"

    assert main(["skill", "install", "--target", "claude", "--force"]) == 0
    assert path.read_text(encoding="utf-8") == read_text()


def test_one_conflict_writes_nothing_at_all(tmp_path: Path, monkeypatch, capsys) -> None:
    """多 target 一起装: 冲突必须在落盘之前发现, 否则用户拿到半成品。"""
    monkeypatch.chdir(tmp_path)
    path = tmp_path / CURSOR
    path.parent.mkdir(parents=True)
    path.write_text("old\n", encoding="utf-8")

    assert main(["skill", "install", "--target", "claude", "--target", "cursor"]) == 1

    assert "加 --force 覆盖" in capsys.readouterr().err
    assert not (tmp_path / CLAUDE).exists()
    assert path.read_text(encoding="utf-8") == "old\n"


def test_print_only_prints(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["skill", "install", "--target", "print"]) == 0

    assert capsys.readouterr().out == read_text()
    assert not (tmp_path / ".claude").exists()
    assert not (tmp_path / "AGENTS.md").exists()


def test_print_cannot_be_combined(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["skill", "install", "--target", "print", "--target", "claude"]) == 1

    assert "不能与其他" in capsys.readouterr().err
    assert not (tmp_path / CLAUDE).exists()


def test_local_only_refuses_every_target(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    _local_only(tmp_path)

    assert main(["skill", "install", "--target", "claude"]) == 1
    assert "本地模式" in capsys.readouterr().err
    assert not (tmp_path / ".claude").exists()

    assert main(["skill", "install", "--target", "print"]) == 1
    assert "本地模式" in capsys.readouterr().err


def test_agents_keeps_crlf_outside_the_block(tmp_path: Path, monkeypatch, capsys) -> None:
    """AGENTS.md 是用户的文件: 行尾不能因为一次写入而整体改变。"""
    monkeypatch.chdir(tmp_path)
    original = "# 我的规则\r\n\r\n- 用 uv\r\n".encode()
    (tmp_path / "AGENTS.md").write_bytes(original)

    assert main(["skill", "install", "--target", "agents"]) == 0

    raw = (tmp_path / "AGENTS.md").read_bytes()
    assert raw.startswith(original)
    assert b"\n" not in raw.replace(b"\r\n", b"")
    capsys.readouterr()


def test_all_three_file_targets_can_be_installed_at_once(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)

    assert (
        main(
            [
                "skill",
                "install",
                "--target",
                "claude",
                "--target",
                "cursor",
                "--target",
                "agents",
            ]
        )
        == 0
    )

    assert (tmp_path / CLAUDE).is_file()
    assert (tmp_path / CURSOR).is_file()
    assert BLOCK_START in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert capsys.readouterr().out.count("已写入") == 3
