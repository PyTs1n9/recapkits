"""`recap render` 与 `recap preview` 的实现。

render 只做四件事: 定位输入、跑完 pipeline、写文件、打印绝对路径。**不自动打开
浏览器** —— 一个生成文件的命令顺手弹窗口属于副作用。
"""

import argparse
from pathlib import Path

from recapkits.errors import RecapError
from recapkits.render import preview
from recapkits.render.pipeline import build_html, load_input
from recapkits.workspace import Workspace, load_workspace


def _story_path(explicit: str | None) -> Path:
    """定位 story.json: --story 优先, 否则用工作区的 .recapkits/story.json。"""
    if explicit:
        return Path(explicit).expanduser()
    workspace = load_workspace()
    if workspace is None:
        raise RecapError("未找到工作区: 先 recap init, 或用 --story 指定故事文件")
    path = workspace.story_path
    if not path.is_file():
        raise RecapError(f"故事文件不存在: {path}\n先写一份 story.json, 或用 --story 指定")
    return path


def _default_out(story_path: Path, year: int) -> Path:
    """默认输出到工作区的 out/; 没有工作区就放在故事旁边。"""
    workspace: Workspace | None = load_workspace()
    directory = workspace.root / "out" if workspace is not None else story_path.parent
    return directory / f"recap-{year}.html"


def cmd_render(args: argparse.Namespace) -> int:
    """校验、烘焙、渲染, 写一个自包含的 HTML 文件。"""
    story_path = _story_path(args.story)
    source = load_input(
        story_path,
        args.insights,
        allow_sensitive=bool(args.allow_sensitive),
        allow_unknown_names=bool(args.allow_unknown_names),
    )
    html = build_html(source, aspect=args.aspect)

    out = (
        Path(args.out).expanduser()
        if args.out
        else _default_out(story_path, source.story.meta.year)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    # 写字节而不是 write_text: 后者在 Windows 会把 \n 翻成 \r\n, 产物字节数随平台变化。
    # 这个项目要求跨平台一致, 行尾必须由我们决定而不是由平台决定。
    out.write_bytes(html.encode("utf-8"))

    size = len(html.encode("utf-8"))
    print(f"已写入 {out.resolve()}")
    print(f"  {len(source.story.cards)} 张卡, {args.aspect}, {size:,} 字节, 无外部请求")
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    """起一个只绑 127.0.0.1 的预览服务器; 改输入文件即自动刷新。"""
    story_path = _story_path(args.story)
    state = preview.PreviewState(
        story_path=story_path,
        insights_path=args.insights,
        aspect=args.aspect,
        allow_sensitive=bool(args.allow_sensitive),
        allow_unknown_names=bool(args.allow_unknown_names),
    )
    preview.serve_forever(state, args.port)
    return 0
