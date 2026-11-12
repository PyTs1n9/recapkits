"""insights.md: 没有 Node 的用户也要拿到一份能读的结论。

端到端用 git fixture 走 CLI; 纯函数用例只验证表格、分项与渲染专用序列的说明。
"""

import json
from pathlib import Path

from recapkits.cli import main
from recapkits.insights.markdown import render_markdown
from recapkits.insights.model import Fact, Insight, Period


def test_cli_writes_insights_markdown_by_default(
    tmp_path: Path, monkeypatch, git_repo: Path
) -> None:
    """默认开启: insights.json 与 insights.md 同时产出。"""
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--year", "2024"]) == 0
    assert main(["import", str(git_repo), "--source", "git"]) == 0
    assert main(["insights"]) == 0

    text = (tmp_path / ".recapkits" / "out" / "insights.md").read_text(encoding="utf-8")

    assert "# 2024 年度洞察" in text
    assert "| # | 类型 | 一句话事实 | 分数 | 数据充足度 |" in text
    assert "## 分项" in text
    assert "## 被闸门关闭的分量" in text
    assert "Node 22+" in text


def test_no_md_skips_the_file(tmp_path: Path, monkeypatch, git_repo: Path) -> None:
    """--no-md 是显式关闭; 不能因为默认开就写不出关闭的方式。"""
    monkeypatch.chdir(tmp_path)
    main(["init", "--year", "2024"])
    main(["import", str(git_repo), "--source", "git"])
    assert main(["insights", "--no-md"]) == 0

    assert not (tmp_path / ".recapkits" / "out" / "insights.md").exists()


def test_payload_preview_reports_series_bytes(
    tmp_path: Path, monkeypatch, git_repo: Path, capsys
) -> None:
    """只报字节数, 不打印洞察内容; 含/不含 series 两行都要有。"""
    monkeypatch.chdir(tmp_path)
    main(["init", "--year", "2024"])
    main(["import", str(git_repo), "--source", "git"])
    capsys.readouterr()

    assert main(["insights", "--payload-preview"]) == 0

    out = capsys.readouterr().out
    assert "payload" in out
    assert "不含 series" in out
    assert "series" in out
    payload = (tmp_path / ".recapkits" / "out" / "insights.json").read_text(encoding="utf-8")
    assert json.loads(payload)["version"] == 1


def test_markdown_mentions_render_only_series() -> None:
    """渲染专用序列不参与排名, 但必须在 md 里说明它已写入 JSON。"""
    ranked = [_insight("vol.total:git:2024", "vol.total", "事件总数", "220")]
    auxiliary = [_insight("vol.daily_series:git:2024", "vol.daily_series", "窗口内事件数", "21")]

    text = render_markdown(
        ranked,
        period=Period("2024-01-01", "2024-12-31", "Asia/Shanghai", 0.5),
        stats={"git": (220, 46)},
        sources=["git"],
        event_count=220,
        render_only=auxiliary,
    )

    assert "渲染专用序列" in text
    assert "不参与排名" in text
    assert "220" in text
    assert "| 1 | `vol.total` | 事件总数 220 |" in text


def test_markdown_escapes_table_pipes() -> None:
    """事实里的竖线不能把表格撕开。"""
    text = render_markdown(
        [_insight("x", "vol.total", "a|b", "1")],
        period=Period("2024-01-01", "2024-12-31", "Asia/Shanghai", 0.5),
        stats={"git": (1, 1)},
        sources=["git"],
        event_count=1,
    )

    assert "a\\|b" in text


def _insight(ident: str, kind: str, label: str, display: str) -> Insight:
    """最小洞察; 只测 Markdown 排版。"""
    return Insight(
        id=ident,
        kind=kind,
        source="git",
        period=Period("2024-01-01", "2024-12-31", "Asia/Shanghai", 0.5),
        headline_fact=Fact("events", label, 1, "count", display),
        facts=[],
        evidence_sql="SELECT 1",
        evidence_rows=1,
        signal=0.0,
        score=0.0,
        score_parts={"signal": 0.0, "deviation": 0.0, "discontinuity": 0.0, "sensitivity": 0.0},
        novelty="constant",
        sensitivity="low",
        data_sufficiency="ok",
        gated=["deviation", "discontinuity"],
        caveats=[],
    )
