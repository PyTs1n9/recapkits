"""`recap doctor`: 环境与工作区诊断。

只打印计数与路径, 不打印任何数据内容。node / ffmpeg 必须同时报出**绝对路径与
版本**: 只报"可用"无法帮用户判断到底是哪一个运行时在生效 (nvm、系统包管理器、
IDE 内置运行时经常不是同一个)。
"""

import argparse
import platform
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from recapkits import __version__
from recapkits.commands import ADAPTERS
from recapkits.db import connect, count_events, init_schema, list_sources
from recapkits.render.ffmpeg import MIN_FFMPEG, ffmpeg_info
from recapkits.render.node import MIN_NODE_MAJOR, node_info
from recapkits.workspace import WORKSPACE, load_workspace


def _git_line() -> str:
    """git 的版本与路径; 缺失时说明哪条命令会不可用。"""
    git = shutil.which("git")
    if git is None:
        return "git        未找到; import --source git 不可用"
    completed = subprocess.run(
        [git, "--version"], capture_output=True, text=True, encoding="utf-8", check=False
    )
    version = (completed.stdout or "").strip() or "unknown"
    return f"git        {version}  {git}"


def _node_line() -> str:
    """node 的版本与路径; 版本过低与缺失是两种不同的失败。"""
    info = node_info()
    if info is None:
        return (
            "node       未找到; render 不可用\n"
            "           装 Node 22+ (nodejs.org), 或用系统包管理器安装"
        )
    if info.major < MIN_NODE_MAJOR:
        return f"node       {info.version}  {info.path} (低于 {MIN_NODE_MAJOR}, render 不可用)"
    return f"node       {info.version}  {info.path}"


def _ffmpeg_line() -> str:
    """ffmpeg 的版本与路径; 版本过低与缺失是两种不同的失败。"""
    info = ffmpeg_info()
    if info is None:
        return "ffmpeg     未找到; render --format mp4 不可用"
    if (info.major, info.minor) < MIN_FFMPEG:
        return f"ffmpeg     {info.version}  {info.path} (低于 5.1, mp4 不可用)"
    return f"ffmpeg     {info.version}  {info.path}"


def cmd_doctor(args: argparse.Namespace) -> int:
    """诊断环境与工作区: 只打印计数, 不打印任何数据内容。"""
    print(f"recapkits  {__version__}")
    print(f"python     {platform.python_version()} ({sys.platform})")
    print(_git_line())
    print(_node_line())
    print(_ffmpeg_line())

    try:
        ZoneInfo("Asia/Shanghai")
        print("时区数据   可用")
    except ZoneInfoNotFoundError:
        print("时区数据   缺失; Windows 需要 tzdata")

    print(f"适配器     auto / {' / '.join(ADAPTERS)}")

    workspace = load_workspace()
    if workspace is None:
        print("workspace  未初始化; 先运行 recap init")
        return 0
    print(f"workspace  {WORKSPACE}/  tz={workspace.tz}  year={workspace.year}")
    if not workspace.db_path.is_file():
        print("events     数据库不存在")
        return 0

    conn = connect(workspace.db_path)
    try:
        init_schema(conn)
        total = count_events(conn)
        sources = list_sources(conn)
    finally:
        conn.close()

    print(f"events     {len(sources)} 个源, {total:,} 条事件")
    for name, count in sources:
        print(f"           {name}  {count:,}")
    counts = dict(sources)
    detail = "  ".join(f"{name} {counts.get(name, 0):,}" for name in ADAPTERS)
    print(f"按适配器   {detail}")
    return 0
