"""硬规则 1、4 的唯一实现: 核心代码不联网, 本地时间只经 `tz.py`。

**这条规则原先的写法是假绿。** CI 里那段 shell 是:

```bash
set -e
! grep -rn -E "https?://" src          # 命中也照样往下走
```

bash 的 `-e` 对**状态被 `!` 取反的命令不生效**(POSIX 的 errexit 例外), 所以只要最后
一条 grep 是「没命中」, 整个脚本就以 0 退出。断言写了一个月, 一次也没拦过东西;
`assets/fonts/*.txt` 里的许可证 URL 只是让这个空洞显形, 不是它的起因。

**判据的对象是可执行代码, 不是文本。** 那三份 `.txt` 是 `renderer/dist/` 的同步副本,
也是 wheel 里 OFL 合规的必需项, 每份都带源地址 —— 把它们当违规, 规则就只剩解释成本。
所以范围钉死为 `.py` 与 `.mjs`: 包里全部可执行的字节。

判据也只有这一套: CI 的 `uv run pytest` 跑的就是这里, 没有第二份 shell 实现可以跟它
漂移, 也不会再因为 `!` 之类的写法静默失效 —— pytest 的断言只有通过和失败两种结局。

`socket` 不是出站请求: `recap preview` 要监听一个回环端口。例外只有它一个, 且必须绑
`127.0.0.1` —— 监听 `0.0.0.0` 会把半成品故事暴露到局域网, 与「不上传」直接冲突。
"""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent / "src"

#: 地址与出站客户端。`urllib.parse` 不算 —— 拼字符串不是请求, 真正的出口是 request。
OUTBOUND = re.compile(
    r"https?://"
    r"|(?:from|import)\s+(?:urllib\.request|urllib\.error|http\.client|httpx|aiohttp|requests)\b"
    r"|urlopen|urlretrieve"
)

#: 本地时间只经 `tz.py`; 这些写法会绕过工作区时区, 让深夜占比变成假话。
LOCAL_TIME = re.compile(r"datetime\.now|astimezone|strftime\(['\"]%H|CURRENT_TIMESTAMP")

#: 允许占用端口的模块; 只有一个文件可以 import 它们。
SERVER = re.compile(r"import\s+(?:socket|socketserver|http\.server)\b")
PORT_OWNER = "recapkits/render/preview.py"
LOOPBACK = '("127.0.0.1", port)'


def _code_files() -> list[Path]:
    """包里所有可执行文件; 许可证、NOTICE、字体二进制一律不在扫描范围。"""
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


def test_licence_text_is_out_of_scope() -> None:
    """范围必须恰好是 .py 与 .mjs。

    这一条同时防止两种失效: 扫到一个空集合就"通过"(所以断言后缀集合), 以及
    某天有人为了让它变绿而把 `.txt` 也放进来(那样规则就名存实亡)。
    """
    scanned = {path.suffix for path in _code_files()}

    assert scanned == {".py", ".mjs"}
