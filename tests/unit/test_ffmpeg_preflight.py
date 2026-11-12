"""MP4 的快速失败: 缺 ffmpeg 时必须在读取任何输入之前退出。

与 `test_node_preflight.py` 同构: 不只断言退出码, 还断言 `.recapkits/` 没有被创建 ——
"跑到一半才失败"是这类检查最容易漏掉的失败模式。
"""

from pathlib import Path

from recapkits import doctor
from recapkits.cli import main
from recapkits.render import ffmpeg, node


def _node_ok(monkeypatch) -> None:
    monkeypatch.setattr(
        node, "node_info", lambda: node.NodeInfo(path="/usr/bin/node", version="v22.0.0", major=22)
    )


def test_mp4_fails_before_touching_workspace(tmp_path: Path, monkeypatch, capsys) -> None:
    """缺 ffmpeg: 立即退出, 不建工作区、不读 story.json。"""
    monkeypatch.chdir(tmp_path)
    _node_ok(monkeypatch)
    monkeypatch.setattr(ffmpeg, "ffmpeg_info", lambda: None)

    assert main(["render", "--format", "mp4"]) == 1

    err = capsys.readouterr().err
    assert "ffmpeg" in err
    assert "工作区" not in err and "story.json" not in err
    assert not (tmp_path / ".recapkits").exists()


def test_outdated_ffmpeg_names_the_version(tmp_path: Path, monkeypatch, capsys) -> None:
    """版本过低与缺失是两种失败; 报错要说清当前是哪个版本。"""
    monkeypatch.chdir(tmp_path)
    _node_ok(monkeypatch)
    monkeypatch.setattr(
        ffmpeg,
        "ffmpeg_info",
        lambda: ffmpeg.FfmpegInfo(path="/usr/bin/ffmpeg", version="4.4.2", major=4, minor=4),
    )

    assert main(["render", "--format", "mp4"]) == 1

    err = capsys.readouterr().err
    assert "4.4.2" in err
    assert "5.1" in err


def test_html_render_does_not_require_ffmpeg(tmp_path: Path, monkeypatch) -> None:
    """只出 HTML 的路径不该探测 ffmpeg。"""
    monkeypatch.chdir(tmp_path)
    _node_ok(monkeypatch)

    def explode() -> None:
        raise AssertionError("--format html 不应探测 ffmpeg")

    monkeypatch.setattr(ffmpeg, "ffmpeg_info", explode)

    # 没有工作区, 所以会在定位故事时报错 —— 但错误不该来自 ffmpeg。
    assert main(["render", "--format", "html"]) == 1


def test_doctor_prints_ffmpeg_path_and_version(tmp_path: Path, monkeypatch, capsys) -> None:
    """doctor 不能只报"可用": 路径与版本都要有。"""
    monkeypatch.chdir(tmp_path)
    info = ffmpeg.FfmpegInfo(path="/opt/ffmpeg/bin/ffmpeg", version="8.1.1", major=8, minor=1)
    monkeypatch.setattr(doctor, "ffmpeg_info", lambda: info)

    assert main(["doctor"]) == 0

    out = capsys.readouterr().out
    assert "8.1.1" in out
    assert "/opt/ffmpeg/bin/ffmpeg" in out
