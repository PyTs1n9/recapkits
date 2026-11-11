"""命令行入口: 解析参数、调用子命令、把失败输出成一句人话。

子命令实现在 commands.py, 这里只管参数与错误出口。
"""

import argparse
import sys
from collections.abc import Sequence

from recapkits.commands import (
    RecapError,
    cmd_doctor,
    cmd_import,
    cmd_init,
    cmd_insights,
)


def build_parser() -> argparse.ArgumentParser:
    """recap init / import / insights / doctor。"""
    parser = argparse.ArgumentParser(prog="recap", description="本地优先的年度回顾引擎")
    parser.add_argument("--debug", action="store_true", help="失败时打印 traceback")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="建立工作区")
    init.add_argument("--tz", default="Asia/Shanghai", help="IANA 时区名, 默认 Asia/Shanghai")
    init.add_argument("--year", type=int, help="回顾年份, 默认当前 UTC 年")
    init.set_defaults(handler=cmd_init)

    imp = sub.add_parser("import", help="导入一个目录")
    imp.add_argument("path", help="导出目录, 或包含多个仓库的目录")
    imp.add_argument("--source", default="auto", choices=["auto", "git"])
    imp.add_argument("--since", help="起始本地日期 YYYY-MM-DD")
    imp.add_argument("--until", help="结束本地日期 YYYY-MM-DD")
    imp.set_defaults(handler=cmd_import)

    insights = sub.add_parser("insights", help="计算候选洞察")
    insights.add_argument("--json", action="store_true", help="输出完整 insights.json")
    insights.add_argument("--top", type=int, default=10, help="最多选几张卡, 默认 10")
    insights.add_argument("--explain", action="store_true", help="逐项打印 score_parts")
    insights.set_defaults(handler=cmd_insights)

    doctor = sub.add_parser("doctor", help="诊断环境与工作区")
    doctor.set_defaults(handler=cmd_doctor)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """命令行入口; 返回进程退出码。"""
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except RecapError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        if args.debug:
            raise
        return 1
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        print("加 --debug 可查看完整 traceback", file=sys.stderr)
        if args.debug:
            raise
        return 1
