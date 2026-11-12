"""`--auto` 规划器: 卡片顺序、跳过理由、写盘前自检与幂等。

验收的四条硬指标都在这里: 黄金语料六卡、最小语料两卡加四条理由、同输入字节相同、
已存在文件时退出非零且不动原文件。
"""

import argparse
import copy
import json
from pathlib import Path

import pytest

from recapkits.cli import main
from recapkits.errors import RecapError
from recapkits.story import auto, templates
from recapkits.story.auto import NO_CONC, NO_DAILY, NO_HOUR, SENSITIVE, SUMMARY_SHORT
from recapkits.story.rules import PLACEHOLDER, YEAR, check_numbers
from recapkits.story.schema import InsightRef

ROOT = Path(__file__).parent.parent
GOLDEN = ROOT / "golden" / "snapshots" / "corpus_2024.insights.json"
SPOTIFY_GOLDEN = ROOT / "golden" / "snapshots" / "spotify_2024.insights.json"
FIXTURES = ROOT / "fixtures"
INSIGHTS = FIXTURES / "insights.json"


def golden() -> dict:
    """黄金语料的 insights.json: 220 事件 / 46 活跃日。"""
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def only_total(payload: dict) -> dict:
    """只留 vol.total 的最小语料; 对应 insufficient 级别下闸门的输出。"""
    total = next(item for item in payload["insights"] if item["kind"] == "vol.total")
    return {**payload, "insights": [copy.deepcopy(total)]}


def init_workspace(tmp_path: Path, payload: dict) -> Path:
    """建一个带 insights.json 与 config.json 的工作区。"""
    workspace = tmp_path / ".recapkits"
    (workspace / "out").mkdir(parents=True)
    (workspace / "config.json").write_text(
        json.dumps({"tz": "Asia/Shanghai", "year": 2024}), encoding="utf-8"
    )
    (workspace / "out" / "insights.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    return workspace


def test_golden_payload_plans_six_cards() -> None:
    """黄金语料六类洞察都在: 卡片顺序固定, 没有跳过。"""
    result = auto.plan(golden(), year=2024)

    assert result.cards == templates.CARD_ORDER
    assert result.skips == ()


def test_spotify_payload_plans_six_cards() -> None:
    """spotify 语料同样出满六卡: 新源不需要另一套规划规则。"""
    payload = json.loads(SPOTIFY_GOLDEN.read_text(encoding="utf-8"))

    result = auto.plan(payload, year=2024)

    assert result.cards == templates.CARD_ORDER
    assert result.skips == ()


def test_minimal_payload_plans_two_cards_with_four_reasons() -> None:
    """最小语料: 只有 vol.total, 因此只有封面与大数字, 四条理由逐条成立。"""
    result = auto.plan(only_total(golden()), year=2024)

    assert result.cards == ("cover", "big-number")
    assert [skip.card for skip in result.skips] == ["ranking", "heatmap", "clock", "summary"]
    assert [skip.reason for skip in result.skips] == [NO_CONC, NO_DAILY, NO_HOUR, SUMMARY_SHORT]


def ref(kind: str) -> InsightRef:
    """模板测试用的最小引用; id 只要唯一, 不参与任何事实解析。"""
    return InsightRef(f"{kind}:git:2024", kind, "low", {}, [])


def test_templates_have_no_handwritten_numbers_or_latin() -> None:
    """模板去掉占位符与年份后只能是 CJK: 一条测试同时守住 V2 与 V6。"""
    refs = {kind: ref(kind) for kind in (*templates.CARD_SOURCE.values(), "vol.daily_series")}
    for kind in templates.CARD_ORDER:
        template = templates.copy(kind, refs, 2024)
        for slot in ("kicker", "headline", "sub"):
            text = getattr(template, slot)
            if text is None:
                continue
            plain = YEAR.sub("", PLACEHOLDER.sub("", text))
            assert not any(char.isascii() and char.isalnum() for char in plain), (kind, slot, text)
            assert check_numbers(0, slot, text) == [], (kind, slot, text)


def test_high_sensitivity_is_skipped_not_auto_authorized() -> None:
    """高敏洞察不进自动规划: 跳过理由必须是「需要 --allow-sensitive」。"""
    payload = golden()
    next(item for item in payload["insights"] if item["kind"] == "conc.top_entity")[
        "sensitivity"
    ] = "high"

    result = auto.plan(payload, year=2024)

    assert "ranking" not in result.cards
    assert ("ranking", SENSITIVE) in [(skip.card, skip.reason) for skip in result.skips]
    # summary 少了一条可引洞察, 于是也退出。
    assert ("summary", SUMMARY_SHORT) in [(skip.card, skip.reason) for skip in result.skips]


def test_daily_series_picks_the_largest_headline_not_the_first() -> None:
    """多条日序列取 headline 值最大者, 同值才按 id; 不依赖字典顺序。"""
    payload = golden()
    daily = next(item for item in payload["insights"] if item["kind"] == "vol.daily_series")
    smaller = copy.deepcopy(daily)
    smaller["id"] = "vol.daily_series:aaa:2024"
    smaller["headline_fact"] = {**smaller["headline_fact"], "value": 1, "display": "1"}
    payload["insights"].append(smaller)

    result = auto.plan(payload, year=2024)

    heatmap = next(card for card in result.story["cards"] if card["id"] == "heatmap")
    assert heatmap["insight"] == daily["id"]


def test_missing_total_is_an_error_not_a_skip() -> None:
    """一个只有空故事的工作区不该产出文件: 没有 vol.total 直接报错。"""
    payload = {"insights": [{"id": "x", "kind": "conc.top_entity", "facts": []}]}

    with pytest.raises(RecapError, match="没有可用的洞察"):
        auto.plan(payload, year=2024)


def test_all_high_sensitivity_refuses_to_plan() -> None:
    """唯一可用的洞察是高敏时, 规划器不替用户授权, 也不写空故事。"""
    payload = only_total(golden())
    payload["insights"][0]["sensitivity"] = "high"

    with pytest.raises(RecapError, match="高敏"):
        auto.plan(payload, year=2024)


def test_plan_is_byte_identical_twice() -> None:
    """同输入跑两次, story.json 字节相同。"""
    first = auto.plan(golden(), year=2024).as_json()
    second = auto.plan(golden(), year=2024).as_json()

    assert first == second


def test_cli_auto_writes_and_check_passes(tmp_path: Path, monkeypatch, capsys) -> None:
    """`story --auto` 写盘后必须能过 `story --check`。"""
    monkeypatch.chdir(tmp_path)
    init_workspace(tmp_path, golden())

    assert main(["story", "--auto"]) == 0
    story_path = tmp_path / ".recapkits" / "story.json"
    assert story_path.is_file()
    assert "6 张卡" in capsys.readouterr().out

    assert main(["story", "--check", str(story_path)]) == 0


def test_cli_auto_refuses_to_overwrite(tmp_path: Path, monkeypatch, capsys) -> None:
    """已存在手写故事时退出非零, 且文件内容与修改时间都不变。"""
    monkeypatch.chdir(tmp_path)
    init_workspace(tmp_path, golden())
    assert main(["story", "--auto"]) == 0
    story_path = tmp_path / ".recapkits" / "story.json"
    before = story_path.stat()
    original = story_path.read_bytes()
    capsys.readouterr()

    assert main(["story", "--auto"]) == 1

    err = capsys.readouterr().err
    assert "已存在手写故事" in err
    assert "--force" in err
    assert story_path.read_bytes() == original
    assert story_path.stat().st_mtime_ns == before.st_mtime_ns


def test_cli_auto_force_regenerates(tmp_path: Path, monkeypatch) -> None:
    """--force 才覆盖; 覆盖后的内容与首次生成一致。"""
    monkeypatch.chdir(tmp_path)
    init_workspace(tmp_path, golden())
    assert main(["story", "--auto"]) == 0
    story_path = tmp_path / ".recapkits" / "story.json"
    original = story_path.read_bytes()
    story_path.write_bytes(b"{}")

    assert main(["story", "--auto", "--force"]) == 0
    assert story_path.read_bytes() == original


def test_cli_auto_without_workspace_demands_out(tmp_path: Path, monkeypatch, capsys) -> None:
    """没有工作区又没给 --out 时报错, 不猜路径。"""
    monkeypatch.chdir(tmp_path)

    assert main(["story", "--auto"]) == 1

    assert "没有工作区" in capsys.readouterr().err


def test_cli_requires_exactly_one_mode(tmp_path: Path, monkeypatch) -> None:
    """`--check` 与 `--auto` 互斥且必选其一。"""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as raised:
        main(["story"])

    assert raised.value.code == 2


def test_validation_failure_does_not_write(tmp_path: Path, monkeypatch, capsys) -> None:
    """模板写坏时: 不写盘、退出 1、报错里有卡片序号。"""
    monkeypatch.chdir(tmp_path)
    init_workspace(tmp_path, golden())
    real = templates.copy

    def overflowing(kind: str, refs: dict, year: int) -> templates.Template:
        template = real(kind, refs, year)
        return templates.Template(
            template.card_id,
            template.card_type,
            template.kicker,
            "记录" * 40,
            template.sub,
        )

    monkeypatch.setattr(templates, "copy", overflowing)

    assert main(["story", "--auto"]) == 1

    err = capsys.readouterr().err
    assert "已放弃写盘" in err
    assert "卡#1" in err
    assert "SLOT_TOO_LONG" in err
    assert not (tmp_path / ".recapkits" / "story.json").exists()


def test_run_path_plans_story_before_render(tmp_path: Path, monkeypatch, git_repo: Path) -> None:
    """`recap <路径>` 缺故事时先自动规划, 再把参数交给 render。"""
    from recapkits import run

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run, "require_node", lambda: None)
    calls: list[argparse.Namespace] = []
    monkeypatch.setattr(run, "cmd_render", lambda args: calls.append(args) or 0)

    code = run.cmd_run(
        argparse.Namespace(path=str(git_repo), tz="Asia/Shanghai", year=2024, top=10, no_auto=False)
    )

    assert code == 0
    story_path = tmp_path / ".recapkits" / "story.json"
    assert story_path.is_file()
    assert json.loads(story_path.read_text(encoding="utf-8"))["cards"]
    assert calls, "自动规划之后必须继续渲染"


def test_run_path_no_auto_keeps_old_behaviour(
    tmp_path: Path, monkeypatch, git_repo: Path, capsys
) -> None:
    """--no-auto 只停到 insights, 不写故事。"""
    from recapkits import run

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run, "require_node", lambda: None)

    code = run.cmd_run(
        argparse.Namespace(path=str(git_repo), tz="Asia/Shanghai", year=2024, top=10, no_auto=True)
    )

    assert code == 0
    assert not (tmp_path / ".recapkits" / "story.json").exists()
    assert "还没有故事" in capsys.readouterr().out


def test_fixture_insights_plans_three_cards() -> None:
    """夹具里没有日序列与小时节律: 三张卡 + 三条理由, 与夹具自身的形状一致。"""
    payload = json.loads(INSIGHTS.read_text(encoding="utf-8"))

    result = auto.plan(payload, year=2024)

    assert result.cards == ("cover", "big-number", "ranking")
    assert [skip.card for skip in result.skips] == ["heatmap", "clock", "summary"]
