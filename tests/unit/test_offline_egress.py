"""出网证明: 只有 loopback 的网络命名空间里跑完整链路, 产物字节不变。

`unshare -rn` 把当前用户映射成新命名空间里的 root, 再建一个只有 loopback 的
网络命名空间 —— 不需要宿主机 root, 也不需要改任何系统配置。

断言 HTML 的 sha256 与联网时相同, 而不只是"命令成功": 后者放得过"渲染时悄悄
取了远程字体、失败后回退"这种情形, 前者要求内容一个字节都不依赖网络。

Windows 与 macOS 没有 unshare, 本地跳过是预期; CI 的 egress-gate 用 `-rs` 守住
"不得跳过" —— 这条证据不能靠"跳过"变绿。
"""

import hashlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "spotify"
LINUX = sys.platform.startswith("linux")

pytestmark = pytest.mark.skipif(not LINUX, reason="unshare 只在 Linux 上存在")


def _quote(value: Path | str) -> str:
    return shlex.quote(str(value))


def _chain() -> str:
    """一次跑完整条链路: 每次新建 netns 会丢掉工作区状态, 测不到跨命令的东西。"""
    python = _quote(sys.executable)
    fixture = _quote(FIXTURES)
    return "\n".join(
        [
            "set -euo pipefail",
            f"{python} -m recapkits.cli init --tz Asia/Shanghai --year 2024",
            f"{python} -m recapkits.cli import {fixture} --source spotify",
            f"{python} -m recapkits.cli insights --top 10",
            f"{python} -m recapkits.cli story --auto",
            f"{python} -m recapkits.cli render --format html",
        ]
    )


def _run(cwd: Path, *, netns: bool) -> subprocess.CompletedProcess[str]:
    argv = ["bash", "-c", _chain()]
    if netns:
        argv = ["unshare", "-rn", "--", *argv]
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_unshare() -> None:
    """没有 unshare / user namespace 时失败而不是跳过: 证据缺了就是缺了。"""
    if shutil.which("unshare") is None:
        pytest.fail("找不到 unshare: 这台 Linux 机器无法提供出网证据")
    probe = subprocess.run(["unshare", "-rn", "true"], capture_output=True)
    if probe.returncode != 0:
        detail = probe.stderr.decode("utf-8", errors="replace").strip()
        pytest.fail(
            f"unshare -rn 不可用: {detail or '未知原因'}\n"
            "Ubuntu 23.10+ 需要先执行 "
            "sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0"
        )


def test_full_chain_is_byte_identical_without_network(tmp_path: Path) -> None:
    _require_unshare()
    if shutil.which("node") is None:
        # 本地缺 node 时跳过; CI 的 egress-gate 装了 node, 并由 -rs 拦住跳过。
        pytest.skip("没有 node: 无法渲染 HTML")

    plain = tmp_path / "plain"
    sandboxed = tmp_path / "sandboxed"
    plain.mkdir()
    sandboxed.mkdir()

    first = _run(plain, netns=False)
    assert first.returncode == 0, f"联网时链路就失败了:\n{first.stderr}"
    second = _run(sandboxed, netns=True)
    assert second.returncode == 0, f"无网环境里链路失败:\n{second.stderr}"

    online = plain / ".recapkits" / "out" / "recap-2024.html"
    offline = sandboxed / ".recapkits" / "out" / "recap-2024.html"
    assert online.is_file() and offline.is_file()
    assert _digest(online) == _digest(offline)
