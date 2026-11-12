"""命令行入口: 解析参数、调用子命令、把失败输出成一句人话。

子命令实现在 commands.py / doctor.py / run.py, 这里只管参数与错误出口。

**两种入口:**
- `recap <子命令> ...`: 分步命令, 给 agent 与调试用。
- `recap <路径>`: 一条命令跑完导入 → 洞察 → 渲染; 第一个非选项参数不是已知
  子命令时走这条路径。node 检查在该路径的处理器第一行, 早于任何数据解析。
"""

import argparse
import sys
from collections.abc import Sequence

from recapkits.commands import cmd_import, cmd_init, cmd_insights
from recapkits.doctor import cmd_doctor
from recapkits.errors import RecapError
from recapkits.render.cli import cmd_preview, cmd_render
from recapkits.run import cmd_run
from recapkits.story.cli import cmd_story

SUBCOMMANDS = frozenset({"init", "import", "insights", "doctor", "story", "render", "preview"})


def build_parser() -> argparse.ArgumentParser:
    """recap init / import / insights / doctor / story / render / preview。"""
    parser = argparse.ArgumentParser(prog="recap", description="本地优先的年度回顾引擎")
    parser.add_argument("--debug", action="store_true", help="失败时打印 traceback")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="建立工作区")
    init.add_argument("--tz", default="Asia/Shanghai", help="IANA 时区名, 默认 Asia/Shanghai")
    init.add_argument("--year", type=int, help="回顾年份, 默认当前 UTC 年")
    init.set_defaults(handler=cmd_init)

    imp = sub.add_parser("import", help="导入一个目录")
    imp.add_argument("path", help="导出目录, 或包含多个仓库的目录")
    imp.add_argument(
        "--source",
        default="auto",
        choices=["auto", "git", "spotify", "netflix"],
        help="数据源; auto 按 detect 最高分选, 两个源分数相差 < 0.2 时报错要求显式指定",
    )
    imp.add_argument("--since", help="起始本地日期 YYYY-MM-DD")
    imp.add_argument("--until", help="结束本地日期 YYYY-MM-DD")
    imp.set_defaults(handler=cmd_import)

    insights = sub.add_parser("insights", help="计算候选洞察")
    insights.add_argument("--json", action="store_true", help="输出完整 insights.json")
    insights.add_argument("--top", type=int, default=10, help="最多选几张卡, 默认 10")
    insights.add_argument("--explain", action="store_true", help="逐项打印 score_parts")
    insights.add_argument(
        "--md",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="写 insights.md, 默认开; --no-md 关闭",
    )
    insights.add_argument(
        "--payload-preview",
        action="store_true",
        help="只报发出去的字节数 (含/不含 series), 不打印内容",
    )
    insights.set_defaults(handler=cmd_insights)

    doctor = sub.add_parser("doctor", help="诊断环境与工作区")
    doctor.set_defaults(handler=cmd_doctor)

    story = sub.add_parser("story", help="校验或自动生成 story.json")
    mode = story.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", metavar="PATH", help="要校验的 story.json")
    mode.add_argument("--auto", action="store_true", help="从 insights.json 规划一份故事")
    story.add_argument("--out", metavar="PATH", help="--auto 的输出, 默认 .recapkits/story.json")
    story.add_argument("--force", action="store_true", help="--auto 时覆盖已存在的 story.json")
    story.add_argument("--year", type=int, help="--auto 的回顾年份, 默认工作区年份")
    story.add_argument("--theme", default="neon", help="--auto 的主题, 默认 neon")
    story.add_argument("--tone", default="deadpan", help="--auto 的语气, 默认 deadpan")
    story.add_argument("--locale", default="zh-CN", help="--auto 的语言, 默认 zh-CN")
    story.add_argument("--insights", metavar="PATH", help="insights.json 路径")
    story.add_argument("--allow-sensitive", action="store_true", help="授权使用高敏洞察")
    story.add_argument("--allow-unknown-names", action="store_true", help="放行实体表外的专有名词")
    story.set_defaults(handler=cmd_story)

    render = sub.add_parser("render", help="渲染单文件 HTML、逐卡 PNG 或 MP4")
    render.add_argument(
        "--format",
        default="html",
        choices=["html", "png", "mp4"],
        help="输出格式: html 单文件, png 逐卡一组图, mp4 一条视频 (后两者需要可选依赖)",
    )
    render.add_argument("--aspect", default="9:16", choices=["9:16", "4:5"], help="画布比例")
    render.add_argument(
        "--story", metavar="PATH", help="story.json 路径, 默认 .recapkits/story.json"
    )
    render.add_argument("--insights", metavar="PATH", help="insights.json 路径")
    render.add_argument(
        "--out",
        metavar="PATH",
        help="html / mp4 为输出文件, png 为输出目录; 默认写到 .recapkits/out/",
    )
    render.add_argument("--fps", type=int, default=30, help="mp4 的帧率, 默认 30")
    render.add_argument("--allow-sensitive", action="store_true", help="授权使用高敏洞察")
    render.add_argument("--allow-unknown-names", action="store_true", help="放行实体表外的专有名词")
    render.set_defaults(handler=cmd_render)

    preview = sub.add_parser("preview", help="本地预览, 改 story.json 自动刷新")
    preview.add_argument("--aspect", default="9:16", choices=["9:16", "4:5"], help="画布比例")
    preview.add_argument(
        "--story", metavar="PATH", help="story.json 路径, 默认 .recapkits/story.json"
    )
    preview.add_argument("--insights", metavar="PATH", help="insights.json 路径")
    preview.add_argument("--port", type=int, default=0, help="端口, 默认由系统分配")
    preview.add_argument("--allow-sensitive", action="store_true", help="授权使用高敏洞察")
    preview.add_argument(
        "--allow-unknown-names", action="store_true", help="放行实体表外的专有名词"
    )
    preview.set_defaults(handler=cmd_preview)
    return parser


def build_run_parser() -> argparse.ArgumentParser:
    """`recap <路径>`: 无子命令的一条命令路径。"""
    parser = argparse.ArgumentParser(
        prog="recap",
        description="一条命令: 导入 → 洞察 → 渲染 (需要 Node 22+)",
    )
    parser.add_argument("--debug", action="store_true", help="失败时打印 traceback")
    parser.add_argument("path", help="导出目录, 或包含多个仓库的目录")
    parser.add_argument("--tz", default="Asia/Shanghai", help="IANA 时区名, 默认 Asia/Shanghai")
    parser.add_argument("--year", type=int, help="回顾年份, 默认当前 UTC 年")
    parser.add_argument("--top", type=int, default=10, help="最多选几张卡, 默认 10")
    parser.add_argument(
        "--no-auto",
        action="store_true",
        help="缺少 story.json 时只停到 insights, 不自动生成故事",
    )
    parser.set_defaults(handler=cmd_run)
    return parser


def _is_run_path(argv: Sequence[str]) -> bool:
    """第一个非选项参数不是已知子命令时, 按 `recap <路径>` 解释。"""
    for token in argv:
        if token == "--debug":
            continue
        if token.startswith("-"):
            return False
        return token not in SUBCOMMANDS
    return False


def main(argv: Sequence[str] | None = None) -> int:
    """命令行入口; 返回进程退出码。"""
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = build_run_parser() if _is_run_path(raw) else build_parser()
    args = parser.parse_args(raw)
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
