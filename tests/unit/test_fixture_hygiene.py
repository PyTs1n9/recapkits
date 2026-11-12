"""fixture 卫生: 真实导出不进仓库, 合成数据里没有 PII 与高熵令牌。

这是 `scripts/guard-exports.py` 的测试。脚本本身在 CI 里以独立步骤运行, 这里守的是
「它的判据真的会失败」—— 一条永远返回 0 的检查等于没有检查。所以除了跑真实仓库,
还对每个判据各造一个反例。
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent.parent


def _load() -> ModuleType:
    """按路径加载脚本; `scripts/` 不是包, 不能直接 import。"""
    path = ROOT / "scripts" / "guard-exports.py"
    spec = importlib.util.spec_from_file_location("guard_exports", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load()


def test_repository_is_clean() -> None:
    """当前仓库必须通过: fixture 是合成的, 入库路径里没有导出特征文件。"""
    assert guard.check(ROOT) == []


def test_export_feature_is_rejected_outside_fixtures() -> None:
    """真导出放进 `tmp/` 也算违规; fixtures 之下才豁免文件名拦截。"""
    assert guard.is_export_feature("tmp/ViewingActivity.csv", 200) is not None
    assert guard.is_export_feature("data/Streaming_History_Audio_2024_0.json", 200) is not None
    assert guard.is_export_feature("tests/fixtures/netflix/ViewingActivity.csv", 200) is None


def test_big_export_xml_is_rejected_by_size() -> None:
    """Apple Health 的 export.xml 只看体积: 小文件是夹具, 大文件是真导出。"""
    assert guard.is_export_feature("docs/export.xml", 2_000_000) is not None
    assert guard.is_export_feature("docs/export.xml", 1_000) is None
    assert guard.is_export_feature("docs/export.xml", guard.BIG_EXPORT_BYTES) is None


def test_public_ip_is_rejected() -> None:
    """文档网段之外的地址一律可疑: 合成数据没有理由出现真实公网 IP。"""
    assert guard.scan_text('"ip_addr": "8.8.8.8"') == ["非文档网段地址 8.8.8.8"]
    assert guard.scan_text('"ip_addr": "192.0.2.15"') == []


def test_email_is_rejected() -> None:
    assert guard.scan_text("profile: someone@example.org") == ["邮箱 someone@example.org"]


def test_random_token_is_rejected() -> None:
    """64 位十六进制会话令牌是典型的「剪了一段真导出」。"""
    token = "9f2a7c41e08b635d1a4c9e77b2f0d384a6c51be927d04f8a3e6b1c5d72f9a048"
    found = guard.scan_text(f'"access_token": "{token}"')

    assert found == [f"高熵令牌 {token[:12]}…"]


def test_field_names_are_not_tokens() -> None:
    """长字段名熵也接近 3.4, 但它没有数字、没有大小写混排, 不能误判。"""
    assert guard.scan_text("master_metadata_album_album_name") == []
    assert guard.scan_text("spotify:track:4uLU6hMCjMI75M1A2tKUQC") == []


def test_runs_under_a_narrow_console_encoding() -> None:
    """Windows runner 是 en-US 代码页: 打印中文不能让检查本身崩掉。

    这条是真实事故的回归: 脚本在 cp1252 控制台上打印中文成功行时抛
    `UnicodeEncodeError`, CI 三个 Windows job 全部变红 —— 一个"发现问题"的
    步骤, 因为一句提示把自己变成了问题。
    """
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "guard-exports.py")],
        capture_output=True,
        env=env,
        cwd=ROOT,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr.decode("cp1252", errors="replace")
    assert b"Traceback" not in completed.stderr
