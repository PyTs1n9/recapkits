#!/usr/bin/env python3
"""守住两件事: 真实导出不进仓库, 合成 fixture 里没有 PII 与高熵令牌。

**第一件**是文件名拦截。真实导出带 IP、档案名、观看历史, 一行就足够反查到具体的人。
诚实的人不会提交它, 但 `git add .` 不会问问题。匹配 `*Streaming_History_Audio*`、
`ViewingActivity.csv` 与超过 1 MB 的 `export.xml` 的**入库路径**(`tests/fixtures/`
之外)一律失败。

**第二件**是内容扫描。fixture 目录豁免文件名拦截(它本来就是合成导出), 但豁免不等于
放任: 这里逐文件扫邮箱、非文档网段的 IPv4、以及长且高熵的令牌。合成数据必须一眼
看出是合成 —— 文档网段(`192.0.2.0/24`、`198.51.100.0/24`、`203.0.113.0/24`)是
RFC 5737 留给示例的, 出现别的地址就说明有人把真导出剪了一段进来。

无参数运行; 有违规时退出码 1, 逐条打印路径与原因。
"""

import math
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 真实导出的特征文件名; `fnmatch` 之外还要匹配任意位置的同名文件。
EXPORT_PATTERNS = ("*Streaming_History_Audio*", "ViewingActivity.csv")

#: 大文件导出: 名字固定, 体积是判据。Apple Health 的 export.xml 动辄几十 MB。
BIG_EXPORT_NAME = "export.xml"
BIG_EXPORT_BYTES = 1_000_000

#: 文件名拦截的豁免前缀: fixture 本身就是合成导出。
FIXTURE_PREFIX = "tests/fixtures/"

#: RFC 5737 的文档网段; 只有这三个可以出现在 fixture 里。
DOC_NETWORKS = ("192.0.2.", "198.51.100.", "203.0.113.")

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

#: 够长 + 够乱才可能是令牌。32 以下基本是正常的标识符与 URL 片段。
TOKEN = re.compile(r"[A-Za-z0-9+/_-]{32,}")
TOKEN_ENTROPY = 3.6


def _shannon(text: str) -> float:
    """Shannon 熵(bit/字符); 用来区分「长单词」与「随机串」。"""
    counts = Counter(text)
    total = len(text)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def _looks_random(token: str) -> bool:
    """高熵且字符类混杂才算令牌。

    纯小写长标识符(`master_metadata_album_album_name`)熵也接近 3.4, 但它没有数字、
    也没有大小写混排, 不该被当成密钥。这个组合条件把误报压到零。
    """
    if len(set(token)) < 8 or _shannon(token) < TOKEN_ENTROPY:
        return False
    has_digit = any(char.isdigit() for char in token)
    mixed_case = any(char.islower() for char in token) and any(char.isupper() for char in token)
    return has_digit or mixed_case


def tracked_files(root: Path) -> list[str]:
    """仓库里所有被 git 跟踪的相对路径(正斜杠)。"""
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        check=True,
    )
    return [item for item in completed.stdout.decode("utf-8").split("\0") if item]


def is_export_feature(relative: str, size: int) -> str | None:
    """入库路径是否是真实导出的特征文件; 是则返回原因。"""
    if relative.startswith(FIXTURE_PREFIX):
        return None
    name = relative.rsplit("/", 1)[-1]
    if any(_matches(name, pattern) for pattern in EXPORT_PATTERNS):
        return f"疑似真实导出: {name}"
    if name == BIG_EXPORT_NAME and size > BIG_EXPORT_BYTES:
        return f"疑似真实导出: {name} ({size:,} 字节)"
    return None


def _matches(name: str, pattern: str) -> bool:
    """`*x*` 与精确名两种模式; 只用到这两种, 不值得引 fnmatch。"""
    if pattern.startswith("*") and pattern.endswith("*"):
        return pattern.strip("*") in name
    return name == pattern


def scan_text(text: str) -> list[str]:
    """扫一段文本里的 PII 与高熵令牌, 返回人类可读的违规描述。"""
    found: list[str] = []
    for match in EMAIL.finditer(text):
        found.append(f"邮箱 {match.group(0)}")
    for match in IPV4.finditer(text):
        address = match.group(0)
        if not address.startswith(DOC_NETWORKS):
            found.append(f"非文档网段地址 {address}")
    for match in TOKEN.finditer(text):
        if _looks_random(match.group(0)):
            found.append(f"高熵令牌 {match.group(0)[:12]}…")
    return found


def _fixtures(root: Path) -> list[Path]:
    directory = root / FIXTURE_PREFIX
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.rglob("*") if path.is_file())


def check(root: Path = ROOT) -> list[str]:
    """跑全部检查, 返回违规行; 空列表代表干净。"""
    problems: list[str] = []
    for relative in tracked_files(root):
        path = root / relative
        size = path.stat().st_size if path.is_file() else 0
        reason = is_export_feature(relative, size)
        if reason is not None:
            problems.append(f"{relative}: {reason}")
    for path in _fixtures(root):
        text = path.read_bytes().decode("utf-8", errors="replace")
        for issue in scan_text(text):
            problems.append(f"{path.relative_to(root).as_posix()}: {issue}")
    return problems


def main() -> int:
    problems = check()
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print(f"共 {len(problems)} 处: 真实导出不进仓库, fixture 只用合成数据", file=sys.stderr)
        return 1
    print(f"导出拦截与 fixture 扫描通过: {len(_fixtures(ROOT))} 个 fixture 文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
