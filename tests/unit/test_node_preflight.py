"""Node 快速失败: 缺 node 时必须在读取任何输入之前退出。

这些用例不依赖真的删掉 node: 直接替换 `node_info` 的返回值, 断言错误顺序与
副作用。特别是 `test_run_path_...` 会检查 `.recapkits/` 没有被创建 —— 只断言
退出码会漏掉"已经跑了一半"的失败模式。
"""

from pathlib import Path

from recapkits import doctor
from recapkits.cli import main
from recapkits.render import node


def test_run_path_fails_before_touching_workspace(tmp_path: Path, monkeypatch, capsys) -> None:
    """`recap <路径>`: 缺 node 时立即退出, 不建工作区、不解析导出。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(node, "node_info", lambda: None)

    code = main([str(tmp_path / "exports")])

    assert code == 1
    err = capsys.readouterr().err
    assert "Node 22+" in err
    assert "找不到 node" in err
    assert not (tmp_path / ".recapkits").exists()


def test_render_reports_node_before_story(tmp_path: Path, monkeypatch, capsys) -> None:
    """`recap render`: node 错误优先于"未找到工作区", 用户才知道先装什么。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(node, "node_info", lambda: None)

    assert main(["render"]) == 1

    err = capsys.readouterr().err
    assert "Node 22+" in err
    assert "工作区" not in err


def test_outdated_node_names_the_version(tmp_path: Path, monkeypatch, capsys) -> None:
    """版本过低与缺失是两种失败; 报错要说清当前是哪个版本。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        node,
        "node_info",
        lambda: node.NodeInfo(path="/usr/bin/node", version="v18.19.0", major=18),
    )

    assert main([str(tmp_path / "exports")]) == 1

    err = capsys.readouterr().err
    assert "v18.19.0" in err
    assert "Node 22+" in err


def test_insights_works_without_node(tmp_path: Path, monkeypatch, git_repo: Path) -> None:
    """§0.2 的底线: 没有 node 也要能拿到 insights.json 与 insights.md。"""
    monkeypatch.chdir(tmp_path)

    def explode() -> None:
        raise AssertionError("insights 路径不应探测 node")

    monkeypatch.setattr(node, "node_info", explode)

    assert main(["init", "--year", "2024"]) == 0
    assert main(["import", str(git_repo), "--source", "git"]) == 0
    assert main(["insights"]) == 0
    assert (tmp_path / ".recapkits" / "out" / "insights.md").is_file()


def test_doctor_prints_node_path_and_version(tmp_path: Path, monkeypatch, capsys) -> None:
    """doctor 不能只报"可用": 路径与版本都要有。"""
    monkeypatch.chdir(tmp_path)
    info = node.NodeInfo(path="/opt/node/bin/node", version="v22.22.2", major=22)
    monkeypatch.setattr(doctor, "node_info", lambda: info)

    assert main(["doctor"]) == 0

    out = capsys.readouterr().out
    assert "v22.22.2" in out
    assert "/opt/node/bin/node" in out
