"""时间轴: 纯计算, 不需要 node / ffmpeg / 浏览器。

数字是可以手算的: 30fps 下 900ms 动画段 = 27 帧; 停留段按秒折算成帧。
这些断言锁死三件事 —— 帧数、时长、以及"停留段只截一帧"(不复制 90 份)。
"""

import pytest

from recapkits.render import timeline

SIX = ("cover", "big-number", "ranking", "heatmap", "clock", "summary")


def test_six_cards_at_30fps() -> None:
    """六张卡的成片帧数与时长; 22s 不是写死的目标, 是这些数字加出来的。"""
    plan = timeline.plan(SIX, 30)

    assert [card.video_frames for card in plan.cards] == [147, 162, 105, 105, 105, 105]
    assert plan.total_frames == 729
    assert plan.duration == pytest.approx(24.3)


def test_only_cover_and_big_number_are_animated() -> None:
    """动画段只有两处; 其余四张单帧复制, 这是 20 h 做得完的前提。"""
    plan = timeline.plan(SIX, 30)

    animated = [card.card_type for card in plan.cards if card.animated]
    assert animated == ["cover", "big-number"]
    assert [card.animation_frames for card in plan.cards] == [27, 27, 0, 0, 0, 0]


def test_hold_segments_take_exactly_one_screenshot() -> None:
    """每张卡只有一帧 hold; 90 帧的停留由 concat 的 duration 表达。"""
    plan = timeline.plan(SIX, 30)

    holds = [frame for frame in plan.frames if frame.hold]
    assert len(holds) == len(SIX)
    assert len(plan.frames) == 28 + 28 + 4


def test_frames_are_global_and_in_order() -> None:
    """帧序号连续、按卡片顺序推进; 截图文件名的字典序就是播放顺序。"""
    plan = timeline.plan(SIX, 30)

    assert [frame.index for frame in plan.frames] == list(range(len(plan.frames)))
    card_indexes = [frame.card_index for frame in plan.frames]
    assert card_indexes == sorted(card_indexes)


def test_animation_frames_stay_inside_the_segment() -> None:
    """动画帧的 currentTime 必须落在 0..900 之间, 且最后一帧之后就是 hold。"""
    plan = timeline.plan(SIX, 30)

    animation = [frame for frame in plan.frames if not frame.hold and frame.card_index == 0]
    assert animation[0].anim_ms == 0
    assert animation[-1].anim_ms < timeline.ANIM_MS
    assert plan.frames[27].hold and plan.frames[27].anim_ms == timeline.ANIM_MS


def test_duration_does_not_depend_on_fps() -> None:
    """停留时长按秒给定, 换帧率只改帧数, 不改成片时长。"""
    assert timeline.plan(SIX, 30).duration == pytest.approx(24.3)
    assert timeline.plan(SIX, 60).duration == pytest.approx(24.3)
    assert timeline.plan(SIX, 60).total_frames == 1458


def test_static_card_is_one_frame_plus_hold() -> None:
    """一张静态卡: 一次截图 + 3.5s 停留, 没有动画段。"""
    plan = timeline.plan(("ranking",), 30)

    assert len(plan.frames) == 1
    assert plan.frames[0].hold
    assert plan.cards[0].video_frames == 105
    assert plan.duration == pytest.approx(3.5)


@pytest.mark.parametrize("fps", [0, -1, 121])
def test_bad_fps_is_rejected(fps: int) -> None:
    """帧率越界直接报错, 不要产出一个"看起来有画面"的坏时间轴。"""
    with pytest.raises(ValueError, match="fps"):
        timeline.plan(SIX, fps)


def test_empty_deck_is_rejected() -> None:
    with pytest.raises(ValueError, match="至少要有一张卡"):
        timeline.plan((), 30)
