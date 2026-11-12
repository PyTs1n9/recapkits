"""视频时间轴: 纯函数, 不碰浏览器也不碰 ffmpeg。

每张卡的时长由「动画段 + 停留段」组成:

- 动画段按 fps 逐帧采样 (`anim_ms` 就是截图时要设的 `animation.currentTime`);
- 停留段只截**一帧**, 由 concat 清单里的 `duration` 表达。

不把同一帧复制 90 份, 是因为 6 张卡 x 1080x1920 的 PNG 会把临时目录撑到 1 GB,
而视频里那 90 帧本来就是同一位图的重复。

这一层不依赖 node / ffmpeg / 浏览器, 所以它的测试可以在任何环境里跑 ——
时间轴算错是最容易发生也最容易被"看起来有画面"掩盖的错误。
"""

from collections.abc import Sequence
from dataclasses import dataclass

#: 入场动画的时长; 两处动画共用这一个值, 录制与 CSS 必须一致。
ANIM_MS = 900

#: 只有这两张卡有入场动画; 其余四张单帧复制。这是计划 §3.8 的混合采集策略。
ANIMATED = frozenset({"cover", "big-number"})

#: 停留时长 (秒)。cover 与 big-number 有动画, 多留半秒让观众读完。
HOLD_SECONDS = {"cover": 4.0, "big-number": 4.5}
DEFAULT_HOLD_SECONDS = 3.5

MIN_FPS = 1
MAX_FPS = 120


@dataclass(frozen=True)
class Frame:
    """一次截图的状态; `hold=True` 的那一帧同时承担整段停留。"""

    index: int
    card_index: int
    anim_ms: int
    hold: bool


@dataclass(frozen=True)
class CardTiming:
    """一张卡在成片里的时长构成; 一律按帧数折算, 不四舍五入到秒。"""

    card_index: int
    card_type: str
    animated: bool
    animation_frames: int
    hold_frames: int
    fps: int

    @property
    def video_frames(self) -> int:
        """这张卡在成片里占多少帧: 动画帧 + 停留帧。"""
        return self.animation_frames + self.hold_frames

    @property
    def anim_seconds(self) -> float:
        return self.animation_frames / self.fps

    @property
    def hold_seconds(self) -> float:
        return self.hold_frames / self.fps

    @property
    def total_seconds(self) -> float:
        return self.video_frames / self.fps


@dataclass(frozen=True)
class Timeline:
    """一份成片的完整时间轴; `frames` 是要截图的那些状态 (含停留帧)。"""

    fps: int
    cards: tuple[CardTiming, ...]
    frames: tuple[Frame, ...]

    @property
    def duration(self) -> float:
        return sum(card.total_seconds for card in self.cards)

    @property
    def total_frames(self) -> int:
        return sum(card.video_frames for card in self.cards)


def _hold_seconds(card_type: str) -> float:
    return HOLD_SECONDS.get(card_type, DEFAULT_HOLD_SECONDS)


def plan(card_types: Sequence[str], fps: int = 30) -> Timeline:
    """按卡片顺序排出时间轴; 卡片类型决定动画段与停留时长。"""
    if not MIN_FPS <= fps <= MAX_FPS:
        raise ValueError(f"fps 必须在 {MIN_FPS}..{MAX_FPS} 之间, 收到 {fps}")
    if not card_types:
        raise ValueError("时间轴至少要有一张卡")

    cards: list[CardTiming] = []
    frames: list[Frame] = []
    index = 0
    for card_index, card_type in enumerate(card_types):
        animated = card_type in ANIMATED
        animation_frames = round(ANIM_MS * fps / 1000) if animated else 0
        hold_frames = round(_hold_seconds(card_type) * fps)
        if animated and animation_frames < 1:
            raise ValueError(f"fps={fps} 下动画段采不到帧")
        if hold_frames < 1:
            raise ValueError(f"fps={fps} 下停留段采不到帧")
        for step in range(animation_frames):
            frames.append(
                Frame(
                    index=index,
                    card_index=card_index,
                    # 取整到毫秒: currentTime 以毫秒为单位, 半毫秒没有意义。
                    anim_ms=round(step * 1000 / fps),
                    hold=False,
                )
            )
            index += 1
        frames.append(
            Frame(
                index=index,
                card_index=card_index,
                anim_ms=ANIM_MS if animated else 0,
                hold=True,
            )
        )
        index += 1
        cards.append(
            CardTiming(
                card_index=card_index,
                card_type=card_type,
                animated=animated,
                animation_frames=animation_frames,
                hold_frames=hold_frames,
                fps=fps,
            )
        )
    return Timeline(fps=fps, cards=tuple(cards), frames=tuple(frames))
