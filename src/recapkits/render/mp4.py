"""MP4 输出: 起一次浏览器, 逐状态截图, 再交给 ffmpeg 编码。

三条与 PNG 共享的事实 (所以直接复用 `png._launch` / `png._wait_ready`, 不复制一份):

1. 截的就是用户能打开的那个 HTML, 版式只有一份实现;
2. 视口 = 舞台, 缩放强制为 1, 截图尺寸要断言;
3. 截图前等字体就绪、两帧 rAF、`data-render-ready`。

**帧是纯函数**: 截图前把 `document.getAnimations()` 全部 `pause()`, 再把
`currentTime` 设成 `N * 1000 / fps`。不用 `sleep`、不用 `animation-delay` 凑帧 ——
后两者都会让"第 N 帧"取决于机器快慢。

停留段只截一帧, 时长交给 concat 清单的 `duration`; 同一帧复制 90 份会把临时目录
撑到 1 GB, 而那些帧本来就是同一位图的重复。
"""

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from recapkits.errors import RecapError
from recapkits.render import mp4box, png, timeline
from recapkits.render.ffmpeg import FfmpegInfo, require_ffmpeg

#: 播放状态由它控制; `animations="disabled"` 会把动画快进到终态, 截出来全是最后一帧。
SET_ANIMATIONS = (
    "([ms]) => document.getAnimations().forEach((a) => { a.pause(); a.currentTime = ms; })"
)


@dataclass(frozen=True)
class Mp4Report:
    """一次 MP4 输出的结果; 结构自检已经在返回前跑过。"""

    path: Path
    bytes: int
    timeline: timeline.Timeline
    info: mp4box.Mp4Info
    channel: str | None
    ffmpeg: FfmpegInfo

    @property
    def seconds(self) -> float:
        return self.timeline.duration

    @property
    def bitrate_mbps(self) -> float:
        return self.bytes * 8 / self.seconds / 1_000_000 if self.seconds else 0.0


def _concat_list(plan: timeline.Timeline) -> str:
    """concat 清单: 动画帧各 1/fps, 停留帧一整段。

    路径带 `frames/` 前缀并以清单所在目录为基准: concat 解析相对路径时看的是清单
    文件的位置, 不是进程的 cwd。
    """
    lines: list[str] = []
    for frame in plan.frames:
        card = plan.cards[frame.card_index]
        seconds = card.hold_seconds if frame.hold else 1 / plan.fps
        lines.append(f"file 'frames/{frame.index:05d}.png'")
        lines.append(f"duration {seconds:.6f}")
    # concat 会忽略最后一帧的 duration; 再列一次最后一张, 把时间补齐。
    lines.append(f"file 'frames/{plan.frames[-1].index:05d}.png'")
    return "\n".join(lines) + "\n"


def _encode(ffmpeg: FfmpegInfo, work: Path, out_path: Path, fps: int, frames: int) -> None:
    """跑 ffmpeg; 参数与阶段任务书一致, 每一项都有理由, 不要随手加。

    `-frames:v` 是必须的: concat 会忽略最后一帧的 duration, 补一帧重复文件又会多出
    **一整帧** (实测 147 帧的片子出来 148 帧, 4.900s 变 4.934s)。按时间轴的总帧数
    截断, 成片时长才是 `帧数 / fps`。
    """
    command = [
        ffmpeg.path,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        "frames.txt",
        "-c:v",
        "libx264",
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
        "-preset",
        "medium",
        "-fps_mode",
        "cfr",
        "-r",
        str(fps),
        # moov 在 mdat 之前: 手机拖动进度条才不会先卡一下。
        "-movflags",
        "+faststart",
        # 与 PNG 的 strip_text_chunks 同一件事: 产物不带源路径与软件版本。
        "-map_metadata",
        "-1",
        "-fflags",
        "+bitexact",
        "-flags:v",
        "+bitexact",
        "-frames:v",
        str(frames),
        str(out_path.resolve()),
    ]
    completed = subprocess.run(
        command, cwd=work, capture_output=True, text=True, encoding="utf-8", check=False
    )
    if completed.returncode != 0:
        tail = "\n".join((completed.stderr or "").strip().splitlines()[-6:]) or "未知错误"
        raise RecapError(f"ffmpeg 编码失败 (退出码 {completed.returncode}):\n{tail}")


def _capture(page: Any, plan: timeline.Timeline, frames_dir: Path, size: tuple[int, int]) -> None:
    """逐状态截图; 每次先设 currentTime, 再按快门。"""
    for frame in plan.frames:
        page.evaluate(SET_ANIMATIONS, [frame.anim_ms])
        stage = page.locator(".stage").nth(frame.card_index)
        raw = frames_dir / f"{frame.index:05d}.png"
        stage.screenshot(path=str(raw), animations="allow")
        data = png.strip_text_chunks(raw.read_bytes())
        if png.image_size(data) != size:
            raise RecapError(
                f"第 {frame.index + 1} 帧的尺寸是 {png.image_size(data)}, 应为 {size}; "
                "舞台缩放没有固定为 1"
            )
        raw.write_bytes(data)


def render_mp4(html: str, *, aspect: str, out_path: Path, fps: int = 30) -> Mp4Report:
    """把一份已烘焙的 HTML 编码成 MP4, 并跑结构自检。"""
    width, height = png.VIEWPORTS[aspect]
    ffmpeg = require_ffmpeg()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plan: timeline.Timeline | None = None

    with tempfile.TemporaryDirectory(prefix="recapkits-mp4-") as tmp:
        work = Path(tmp)
        page_path = work / "recap.html"
        page_path.write_bytes(html.encode("utf-8"))
        frames_dir = work / "frames"
        frames_dir.mkdir()

        sync_playwright = png._sync_playwright()
        with sync_playwright() as playwright:
            browser, channel = png._launch(playwright)
            try:
                context = browser.new_context(
                    viewport={"width": width, "height": height}, device_scale_factor=1
                )
                page = context.new_page()
                page.goto(page_path.as_uri(), wait_until="load")
                page.evaluate("document.documentElement.style.setProperty('--stage-scale', '1')")
                # 动画只在 data-motion="on" 时定义: HTML 打开后是静态的, 不会自己动。
                page.evaluate("document.documentElement.dataset.motion = 'on'")
                png._wait_ready(page, timeout_ms=15_000)
                types = page.evaluate(
                    "[...document.querySelectorAll('.stage')].map((el) => el.dataset.cardType)"
                )
                if not isinstance(types, list) or not types:
                    raise RecapError("页面里没有 .stage: 故事没有卡片")
                plan = timeline.plan([str(item) for item in types], fps)
                _capture(page, plan, frames_dir, (width, height))
            finally:
                browser.close()

        (work / "frames.txt").write_text(_concat_list(plan), encoding="utf-8")
        _encode(ffmpeg, work, out_path, fps, plan.total_frames)

    if plan is None:  # pragma: no cover - 上面的分支已经保证有值
        raise RecapError("没能建立时间轴: 页面里没有卡片")
    data = out_path.read_bytes()
    info = mp4box.parse(data)
    mp4box.verify(
        info,
        seconds=plan.duration,
        width=width,
        height=height,
        frame_seconds=1 / fps,
    )
    return Mp4Report(
        path=out_path,
        bytes=len(data),
        timeline=plan,
        info=info,
        channel=channel,
        ffmpeg=ffmpeg,
    )
