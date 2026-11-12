"""MP4 输出与入场动画: 结构自检、默认静态、currentTime 驱动。

这些用例需要 node / 一个浏览器 / ffmpeg。CI 的 node-gate 会装好三者并断言
"不得跳过" —— 无 ffmpeg 时全部跳过而仍然"全绿"是最糟的一种绿。
"""

import json
from pathlib import Path

import pytest

from recapkits.cli import main
from recapkits.render import ffmpeg, mp4, node, png, timeline
from recapkits.render.pipeline import render_document

FIXTURES = Path(__file__).parent.parent / "fixtures"
STORY = FIXTURES / "story-render.json"
INSIGHTS = FIXTURES / "insights.json"


def _browser_available() -> bool:
    try:
        sync_playwright = png._sync_playwright()
    except Exception:
        return False
    try:
        with sync_playwright() as playwright:
            browser, _ = png._launch(playwright)
            browser.close()
    except Exception:
        return False
    return True


_NODE = node.node_info()
_FFMPEG = ffmpeg.ffmpeg_info()
_READY = (
    _NODE is not None
    and _NODE.major >= node.MIN_NODE_MAJOR
    and node.BUNDLE.is_file()
    and _FFMPEG is not None
    and (_FFMPEG.major, _FFMPEG.minor) >= ffmpeg.MIN_FFMPEG
)
needs_av = pytest.mark.skipif(not _READY, reason="需要 Node 22+ / 已构建的 renderer / ffmpeg 5.1+")
needs_browser = pytest.mark.skipif(not _browser_available(), reason="需要 Playwright 与一个浏览器")


def _one_card_story(tmp_path: Path, card_type: str = "cover") -> Path:
    """抽一张卡成独立故事; 编码一条 5 秒的片子比三条快得多。"""
    story = json.loads(STORY.read_text(encoding="utf-8"))
    card = next(item for item in story["cards"] if item["type"] == card_type)
    path = tmp_path / f"{card_type}.json"
    path.write_text(json.dumps({**story, "cards": [card]}, ensure_ascii=False), encoding="utf-8")
    return path


@needs_av
def test_mp4_structure_is_verified(tmp_path: Path) -> None:
    """三张卡: moov 在 mdat 之前、分辨率正确、时长与时间轴一致、无元数据。"""
    html = render_document(STORY, str(INSIGHTS), aspect="9:16")

    report = mp4.render_mp4(html, aspect="9:16", out_path=tmp_path / "recap.mp4", fps=30)

    assert report.bytes > 0
    assert report.info.boxes.index("moov") < report.info.boxes.index("mdat")
    assert (report.info.width, report.info.height) == (1080, 1920)
    assert report.info.duration == pytest.approx(report.timeline.duration, abs=1 / 30)
    assert report.info.udta_items == 0
    assert not report.info.has_metadata
    # 三张卡: cover 4.9s + big-number 5.4s + ranking 3.5s。
    assert [card.video_frames for card in report.timeline.cards] == [147, 162, 105]
    assert report.timeline.total_frames == 414
    assert report.seconds == pytest.approx(13.8)


@needs_av
def test_four_by_five_keeps_the_stage_size(tmp_path: Path) -> None:
    """4:5 的分辨率是 1080x1350; yuv420p 的偶数约束不许改动舞台尺寸。"""
    html = render_document(_one_card_story(tmp_path), str(INSIGHTS), aspect="4:5")

    report = mp4.render_mp4(html, aspect="4:5", out_path=tmp_path / "wide.mp4", fps=30)

    assert (report.info.width, report.info.height) == (1080, 1350)


@needs_av
def test_cli_writes_aspect_specific_paths(tmp_path: Path, monkeypatch) -> None:
    """两个比例分开命名: 同名会互相覆盖, PNG 上已经踩过一次。"""
    monkeypatch.chdir(tmp_path)
    workspace = tmp_path / ".recapkits"
    workspace.mkdir()
    (workspace / "config.json").write_text(
        json.dumps({"tz": "Asia/Shanghai", "year": 2024}), encoding="utf-8"
    )
    (workspace / "story.json").write_text(
        _one_card_story(tmp_path).read_text(encoding="utf-8"), encoding="utf-8"
    )
    (workspace / "insights.json").write_text(INSIGHTS.read_text(encoding="utf-8"), encoding="utf-8")

    assert main(["render", "--format", "mp4", "--aspect", "9:16"]) == 0
    assert main(["render", "--format", "mp4", "--aspect", "4:5"]) == 0

    assert (workspace / "out" / "recap-2024.mp4").is_file()
    assert (workspace / "out" / "recap-2024-4x5.mp4").is_file()


@needs_browser
def test_page_is_static_until_motion_is_requested(tmp_path: Path) -> None:
    """HTML 的承诺是静态可读: 没有 data-motion 时页面上一条动画都没有。"""
    html = render_document(_one_card_story(tmp_path), str(INSIGHTS), aspect="9:16")
    page_path = tmp_path / "cover.html"
    page_path.write_bytes(html.encode("utf-8"))

    with png._sync_playwright()() as playwright:
        browser, _ = png._launch(playwright)
        try:
            page = browser.new_page(viewport={"width": 1080, "height": 1920})
            page.goto(page_path.as_uri(), wait_until="load")
            assert page.evaluate("document.getAnimations().length") == 0

            page.evaluate("document.documentElement.dataset.motion = 'on'")
            count = page.evaluate("document.getAnimations().length")
            assert count >= 5, f"封面应有五段入场动画, 实际 {count}"

            page.evaluate(mp4.SET_ANIMATIONS, [0])
            hidden = page.evaluate(
                "getComputedStyle(document.querySelector('.cover__year')).opacity"
            )
            page.evaluate(mp4.SET_ANIMATIONS, [timeline.ANIM_MS])
            shown = page.evaluate(
                "getComputedStyle(document.querySelector('.cover__year')).opacity"
            )
            assert float(hidden) < 1
            assert float(shown) == 1
        finally:
            browser.close()


@needs_browser
def test_big_number_animation_scales_from_92_percent(tmp_path: Path) -> None:
    """数字从 0.92 缩放到 1; 原点在 left bottom, 墨迹底边不动。"""
    html = render_document(_one_card_story(tmp_path, "big-number"), str(INSIGHTS), aspect="9:16")
    page_path = tmp_path / "total.html"
    page_path.write_bytes(html.encode("utf-8"))

    with png._sync_playwright()() as playwright:
        browser, _ = png._launch(playwright)
        try:
            page = browser.new_page(viewport={"width": 1080, "height": 1920})
            page.goto(page_path.as_uri(), wait_until="load")
            page.evaluate("document.documentElement.dataset.motion = 'on'")
            page.evaluate(mp4.SET_ANIMATIONS, [0])
            start = page.evaluate(
                "getComputedStyle(document.querySelector('.big-number__value')).transform"
            )
            page.evaluate(mp4.SET_ANIMATIONS, [timeline.ANIM_MS])
            end = page.evaluate(
                "getComputedStyle(document.querySelector('.big-number__value')).transform"
            )
            assert start.startswith("matrix(0.92")
            # fill: both 会保留 to 关键帧的恒等矩阵, 而不是把 transform 收回到 none。
            assert end in {"none", "matrix(1, 0, 0, 1, 0, 0)"}
        finally:
            browser.close()
