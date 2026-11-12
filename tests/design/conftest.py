"""设计断言的夹具: 一套浏览器, 六张卡 x 两个比例, 一次量完。

为什么是 session 级: 每次起浏览器、每次渲染页面都要几百毫秒, 而三条断言 (溢出 /
安全区 / 对比度) 用的是同一批截图。分开做会让 `pytest -m design` 慢三倍。
"""

import json

import design_deck
import design_harness as harness
import pytest


def _skip_reason() -> str | None:
    """缺 Node / Playwright / 浏览器时给一句能照着做的话。"""
    from recapkits.render import node

    info = node.node_info()
    if info is None:
        return "需要 Node 22+ 才能渲染页面"
    if info.major < node.MIN_NODE_MAJOR:
        return f"需要 Node 22+, 当前 {info.version}"
    try:
        import playwright  # noqa: F401
    except ImportError:
        return "需要 Playwright: uv sync --extra png"
    return None


@pytest.fixture(scope="session")
def deck(tmp_path_factory) -> list[dict]:
    """六张卡 x 两个比例: 每张卡的截图、版面度量与像素分析。"""
    reason = _skip_reason()
    if reason is not None:
        pytest.skip(reason)

    from playwright.sync_api import sync_playwright

    from recapkits.render.pipeline import render_document
    from recapkits.render.png import _launch

    root = tmp_path_factory.mktemp("design")
    payload = design_deck.insights_payload()
    story = design_deck.story()
    insights = root / "insights.json"
    insights.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    results: list[dict] = []
    with sync_playwright() as playwright:
        browser, _channel = _launch(playwright)
        try:
            analyzer = browser.new_page(viewport={"width": 240, "height": 240})
            for aspect, (width, height) in harness.VIEWPORTS.items():
                for card in story["cards"]:
                    tag = f"{aspect.replace(':', '')}-{card['id']}"
                    one = {**story, "cards": [card]}
                    story_path = root / f"{tag}.json"
                    story_path.write_text(json.dumps(one, ensure_ascii=False), encoding="utf-8")
                    html = render_document(story_path, str(insights), aspect=aspect)
                    page_path = root / f"{tag}.html"
                    page_path.write_bytes(html.encode("utf-8"))

                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.goto(page_path.as_uri(), wait_until="load")
                    shot = harness.capture(page, aspect=aspect)
                    page.close()
                    results.append(
                        {
                            "shot": shot,
                            "analysis": harness.analyze(analyzer, shot),
                            "html": page_path,
                        }
                    )
            analyzer.close()
        finally:
            browser.close()
    return results
