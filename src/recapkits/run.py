"""`recap <路径>`: 一条命令完成导入、洞察与 HTML 渲染。

**node 检查必须是第一条语句。** 这条路径会解析并写入大量数据, 缺 node 时应当
在读取任何导出文件之前就拒绝, 而不是跑完三分钟才在渲染步骤失败。检查放在
`cmd_run` 而不是 `main`, 是为了让"无子命令路径"的语义在处理器里一目了然。
"""

import argparse
from pathlib import Path

from recapkits.commands import cmd_import, cmd_init, cmd_insights
from recapkits.errors import RecapError
from recapkits.render.cli import cmd_render
from recapkits.render.node import require_node
from recapkits.story.cli import auto_story
from recapkits.workspace import load_workspace


def _ns(**values: object) -> argparse.Namespace:
    """构造一个只带字段的 Namespace, 避免在调用处堆一长串关键字。"""
    return argparse.Namespace(**values)


def cmd_run(args: argparse.Namespace) -> int:
    """导入 → 洞察 → (有故事时) 渲染 HTML。"""
    require_node()

    path = Path(args.path).expanduser()
    if not path.exists():
        raise RecapError(f"路径不存在: {args.path}")

    workspace = load_workspace()
    if workspace is None:
        code = cmd_init(_ns(tz=args.tz, year=args.year))
        if code != 0:
            return code
        workspace = load_workspace()
    if workspace is None:
        raise RecapError("工作区创建失败: .recapkits/config.json 没有写出来")

    code = cmd_import(_ns(path=str(path), source="auto", since=None, until=None))
    if code != 0:
        return code

    print()
    code = cmd_insights(
        _ns(
            json=False,
            top=args.top,
            explain=False,
            md=True,
            payload_preview=False,
            entities="name",
        )
    )
    if code != 0:
        return code

    print()
    if not workspace.story_path.is_file():
        if args.no_auto:
            print(f"还没有故事: 写一份 {workspace.story_path}, 再跑 recap render")
            if not workspace.local_only:
                print("需要 agent 帮写时, 把 agent/insights.json 交给它, 按 skill 写 story.json")
            return 0
        # 少了这一步, 「引擎不会自动写故事」就是上手的第一卡点: 22 条事件 →
        # 1 条洞察 → 用户停在 0 张卡。自动规划只是把这一步补上, 不改变任何校验规则。
        code = auto_story(
            insights=None,
            out=None,
            year=None,
            theme="neon",
            tone="deadpan",
            locale="zh-CN",
            force=False,
        )
        if code != 0:
            return code
        print()

    return cmd_render(
        _ns(
            story=None,
            insights=None,
            restore=None,
            out=None,
            format="html",
            aspect="9:16",
            fps=30,
            allow_sensitive=False,
            allow_unknown_names=False,
        )
    )
