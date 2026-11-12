"""核心代码不发起网络请求, 也不旁路 `tz.py` 取本地时间。

两条都是项目的硬约束, 而硬约束只写在文档里就会在某次重构里悄悄失效。CI 用 shell
grep 守同样的两条, 但那只在推送后才发现; 这里的测试让 `pytest` 在本机就报红。

只扫 `.py` 与 `.mjs`: `render/assets/fonts/*.txt` 是 OFL 许可证与来源说明, 里面的
URL 是署名要求的内容, 不是可执行的网络请求。断言的是**代码**, 不是文本。

`socket` 不算出站请求 —— `recap preview` 要监听一个回环端口。例外只有它一个,
且必须绑 `127.0.0.1`: 监听 `0.0.0.0` 会把半成品故事暴露到局域网, 与「不上传」
的卖点直接冲突。
"""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent / "src"

#: 地址与出站请求: 一旦出现, 说明核心在某处偷偷联网。
OUTBOUND = re.compile(r"https?://|import\s+urllib|import\s+requests")

#: 本地时间只经 `tz.py`; 这些写法会绕过工作区时区, 让深夜占比变成假话。
LOCAL_TIME = re.compile(
    r"datetime\.now|astimezone|strftime\(['\"]%H|urllib\.request|CURRENT_TIMESTAMP"
)

#: 允许占用端口的模块; 只有一个文件可以 import 它们。
SERVER = re.compile(r"import\s+(?:socket|socketserver|http\.server)\b")
PORT_OWNER = "recapkits/render/preview.py"
LOOPBACK = '("127.0.0.1", port)'


def _code_files() -> list[Path]:
    return sorted(
        path for path in SRC.rglob("*") if path.is_file() and path.suffix in {".py", ".mjs"}
    )


def _lines() -> list[tuple[str, int, str]]:
    """(相对路径, 行号, 内容) 三元组; 断言失败时能直接跳到那一行。"""
    return [
        (path.relative_to(SRC.parent).as_posix(), number, line)
        for path in _code_files()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
    ]


def test_core_has_no_outbound_addresses() -> None:
    offenders = [f"{path}:{number}" for path, number, line in _lines() if OUTBOUND.search(line)]

    assert offenders == []


def test_local_time_only_goes_through_tz() -> None:
    offenders = [f"{path}:{number}" for path, number, line in _lines() if LOCAL_TIME.search(line)]

    assert offenders == []


def test_only_the_preview_server_opens_a_port() -> None:
    """端口只有一处: 越界新增监听口, 会破坏「不上传」的可验证性。"""
    owners = {path for path, _, line in _lines() if SERVER.search(line)}

    assert owners == {f"src/{PORT_OWNER}"}


def test_the_preview_server_binds_loopback_only() -> None:
    """文档里可以提到 `0.0.0.0` 这个反面教材, 但绑定地址不能是它。"""
    source = (SRC / PORT_OWNER).read_text(encoding="utf-8")

    assert LOOPBACK in source
    assert '("0.0.0.0"' not in source


def test_license_files_are_not_scanned() -> None:
    """许可证文本里的 URL 必须在扫描范围之外, 否则这条断言会把 OFL 判成违规。"""
    scanned = {path.suffix for path in _code_files()}

    assert scanned == {".py", ".mjs"}
