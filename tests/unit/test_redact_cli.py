"""`recap redact` 端到端: 写两份产物、审计只上 stderr、--report 不落盘。"""

import json
import shutil
from pathlib import Path

from recapkits.cli import main
from recapkits.redact import report
from recapkits.redact.apply import redact_pair
from recapkits.redact.pseudonym import Book
from recapkits.redact.text import Audit

FIXTURES = Path(__file__).parent.parent / "fixtures"
FIXED = "0123456789abcdef" * 2


def make_workspace(tmp_path: Path) -> Path:
    """一个最小的已初始化工作区: 配置 + insights + story。"""
    root = tmp_path / ".recapkits"
    (root / "out").mkdir(parents=True)
    (root / "config.json").write_text(
        json.dumps({"tz": "Asia/Shanghai", "year": 2024, "created_at": "2024-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    shutil.copyfile(FIXTURES / "insights.json", root / "out" / "insights.json")
    shutil.copyfile(FIXTURES / "story-render.json", root / "story.json")
    return root


def test_writes_a_consistent_pair(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    root = make_workspace(tmp_path)

    assert main(["redact"]) == 0

    captured = capsys.readouterr()
    assert "已写入" in captured.out
    assert "脱敏审计" in captured.err
    # 非 TTY: 只有计数, 没有样本原文
    assert "alpha" not in captured.err

    redacted = root / "redacted"
    insights = json.loads((redacted / "insights.json").read_text(encoding="utf-8"))
    story = json.loads((redacted / "story.json").read_text(encoding="utf-8"))
    assert "alpha" not in json.dumps(insights, ensure_ascii=False)
    assert "alpha" not in json.dumps(story, ensure_ascii=False)
    assert (root / "redactions.json").is_file()


def test_redacted_pair_passes_story_check(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    root = make_workspace(tmp_path)
    assert main(["redact"]) == 0
    capsys.readouterr()

    code = main(
        [
            "story",
            "--check",
            str(root / "redacted" / "story.json"),
            "--insights",
            str(root / "redacted" / "insights.json"),
        ]
    )

    assert code == 0
    assert "通过" in capsys.readouterr().out


def test_a_second_run_is_byte_identical(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    root = make_workspace(tmp_path)
    assert main(["redact"]) == 0
    capsys.readouterr()
    first = {path.name: path.read_bytes() for path in [*(root / "redacted").iterdir()]}
    first_book = (root / "redactions.json").read_bytes()

    assert main(["redact"]) == 0
    capsys.readouterr()
    second = {path.name: path.read_bytes() for path in [*(root / "redacted").iterdir()]}

    assert first == second
    assert (root / "redactions.json").read_bytes() == first_book


def test_report_writes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    root = make_workspace(tmp_path)

    assert main(["redact", "--report"]) == 0

    captured = capsys.readouterr()
    assert not (root / "redacted").exists()
    assert not (root / "redactions.json").exists()
    assert "未写入任何文件" in captured.err
    assert "临时盐" in captured.err
    assert "alpha" not in captured.err


def test_report_tty_prints_samples(tmp_path: Path) -> None:
    """样本只在 TTY 上出现; 用一个假的流证明这条路是通的。"""
    insights = json.loads((FIXTURES / "insights.json").read_text(encoding="utf-8"))
    story = json.loads((FIXTURES / "story-render.json").read_text(encoding="utf-8"))
    result = redact_pair(insights, story, book=Book(salt=FIXED), words=[])

    class Tty:
        def __init__(self) -> None:
            self.text = ""

        def write(self, value: str) -> None:
            self.text += value

        def isatty(self) -> bool:
            return True

    stream = Tty()
    report.render(result.audit, stream=stream)

    assert "alpha" in stream.text
    assert "实体替换" in stream.text


def test_over_redaction_is_called_out() -> None:
    """抑制表把所有实体都抹掉时, 必须提示"可能过度脱敏"。"""
    audit = Audit(entity_kinds={"repo": ["a", "b"]}, removed=["a", "b"], pseudonyms=0)

    class Sink:
        def __init__(self) -> None:
            self.text = ""

        def write(self, value: str) -> None:
            self.text += value

        def isatty(self) -> bool:
            return False

    stream = Sink()
    report.render(audit, stream=stream)

    assert "过度脱敏" in stream.text


def test_explicit_paths_work_without_a_workspace(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    insights = tmp_path / "insights.json"
    story = tmp_path / "story.json"
    shutil.copyfile(FIXTURES / "insights.json", insights)
    shutil.copyfile(FIXTURES / "story-render.json", story)

    code = main(
        [
            "redact",
            "--insights",
            str(insights),
            "--story",
            str(story),
            "--out",
            str(tmp_path / "share"),
        ]
    )

    assert code == 0
    assert (tmp_path / "share" / "story.json").is_file()
    assert (tmp_path / "redactions.json").is_file()
    assert "已写入" in capsys.readouterr().out
