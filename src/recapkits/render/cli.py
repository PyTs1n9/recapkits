"""`recap render` 与 `recap preview` 的实现。

render 只做四件事: 定位输入、跑完 pipeline、写文件、打印绝对路径。**不自动打开
浏览器** —— 一个生成文件的命令顺手弹窗口属于副作用。
"""

import argparse
from pathlib import Path

from recapkits.errors import RecapError
from recapkits.render import preview
from recapkits.render.ffmpeg import require_ffmpeg
from recapkits.render.mp4 import render_mp4
from recapkits.render.node import require_node
from recapkits.render.pipeline import build_html, load_input
from recapkits.render.png import render_pngs
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


def _default_cards_dir(story_path: Path, aspect: str) -> Path:
    """PNG 的默认目录: 9:16 用 `out/cards/`, 4:5 用 `out/cards-4x5/`。

    两个比例的图名一样 (recap-<年份>-NN.png), 同一个目录会互相覆盖; 而"两种比例都
    要出"是常见用法, 所以默认按比例分目录, 而不是让第二次运行悄悄抹掉第一次。
    """
    workspace: Workspace | None = load_workspace()
    root = workspace.root if workspace is not None else story_path.parent
    return root / "out" / ("cards" if aspect == "9:16" else "cards-4x5")


def _default_mp4_path(story_path: Path, year: int, aspect: str) -> Path:
    """MP4 的默认文件: 两个比例分开命名; 同名会互相覆盖, PNG 上已经踩过一次。"""
    workspace: Workspace | None = load_workspace()
    root = workspace.root if workspace is not None else story_path.parent
    name = f"recap-{year}.mp4" if aspect == "9:16" else f"recap-{year}-4x5.mp4"
    return root / "out" / name


def cmd_render(args: argparse.Namespace) -> int:
    """校验、烘焙、渲染; html 写单文件, png 逐卡写一组图, mp4 写一条视频。"""
    # 纯参数检查放最前: 一个写错的后缀不该先等 node / ffmpeg 探测。
    if args.format == "mp4" and args.out and Path(args.out).suffix.lower() != ".mp4":
        raise RecapError("--format mp4 的 --out 是输出文件, 需要以 .mp4 结尾")
    # 先确认 node, 再读 story/insights: 缺 node 时用户不该先看到校验错误。
    require_node()
    # mp4 的 ffmpeg 检查同样要早于读取输入: 缺工具时不该先解析三分钟数据。
    if args.format == "mp4":
        require_ffmpeg()
    story_path = _story_path(args.story)
    source = load_input(
        story_path,
        args.insights,
        allow_sensitive=bool(args.allow_sensitive),
        allow_unknown_names=bool(args.allow_unknown_names),
    )
    html = build_html(source, aspect=args.aspect)
    year = source.story.meta.year

    if args.format == "png":
        return _render_png(args, html, story_path=story_path, year=year)
    if args.format == "mp4":
        return _render_mp4(args, html, story_path=story_path, year=year)

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


def _render_png(args: argparse.Namespace, html: str, *, story_path: Path, year: int) -> int:
    """逐卡截图; `--out` 在这条路径上指的是目录, 不是文件。"""
    if args.out and Path(args.out).suffix.lower() == ".png":
        raise RecapError("--format png 的 --out 是输出目录, 不是文件名")
    out_dir = (
        Path(args.out).expanduser() if args.out else _default_cards_dir(story_path, args.aspect)
    )
    report = render_pngs(html, aspect=args.aspect, out_dir=out_dir, year=year)
    if report.channel is None:
        print("未找到本机 chrome / msedge, 已回落到 Playwright 自带的 chromium (约 150 MB)")
    print(f"已写入 {len(report.paths)} 张 PNG, 共 {report.total_bytes:,} 字节")
    print(f"  {out_dir.resolve()}  ({args.aspect})")
    return 0


def _render_mp4(args: argparse.Namespace, html: str, *, story_path: Path, year: int) -> int:
    """编码 MP4; `--out` 在这条路径上是文件, 与 png 的目录语义相反。"""
    out = (
        Path(args.out).expanduser()
        if args.out
        else _default_mp4_path(story_path, year, args.aspect)
    )
    report = render_mp4(html, aspect=args.aspect, out_path=out, fps=args.fps)
    if report.channel is None:
        print("未找到本机 chrome / msedge, 已回落到 Playwright 自带的 chromium (约 150 MB)")
    print(f"已写入 {out.resolve()}")
    print(
        f"  {report.seconds:.1f}s / {report.timeline.total_frames} 帧 @{args.fps}fps, "
        f"{report.bytes:,} 字节 ({report.bitrate_mbps:.2f} Mbps)"
    )
    per_card = " / ".join(f"{card.card_type} {card.video_frames}" for card in report.timeline.cards)
    print(f"  每张卡: {per_card}")
    print(f"  ffmpeg {report.ffmpeg.version}  {report.ffmpeg.path}")
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    """起一个只绑 127.0.0.1 的预览服务器; 改输入文件即自动刷新。"""
    require_node()
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
