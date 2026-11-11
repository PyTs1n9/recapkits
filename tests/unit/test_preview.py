"""预览服务器: 只绑 127.0.0.1, 输入文件一变就换 revision。

热更新是"拉"模式, 所以测试也按拉来验: 同一个 URL 取两次, 中间改一次文件,
revision 必须变; 页面内容必须跟着变。
"""

import http.client
import shutil
import threading
from pathlib import Path

import pytest

from recapkits.render import node, preview

FIXTURES = Path(__file__).parent.parent / "fixtures"

needs_node = pytest.mark.skipif(
    shutil.which("node") is None or not node.BUNDLE.is_file(),
    reason="需要 node 与已构建的 renderer assets",
)


class Server:
    """在后台线程里跑一个预览服务器, 退出时确保关掉。"""

    def __init__(self, story: Path, insights: Path) -> None:
        self.state = preview.PreviewState(
            story_path=story,
            insights_path=str(insights),
            aspect="9:16",
            allow_sensitive=False,
            allow_unknown_names=False,
        )
        self.url, self.server = preview.make_server(self.state, 0)
        self.host, self.port = self.server.server_address[0], self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> "Server":
        self.thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def get(self, path: str) -> tuple[int, str]:
        connection = http.client.HTTPConnection(str(self.host), int(self.port), timeout=10)
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            return response.status, response.read().decode("utf-8")
        finally:
            connection.close()


def test_url_is_loopback_and_has_random_port() -> None:
    """只绑 127.0.0.1: 预览不该暴露到局域网。"""
    state = preview.PreviewState(
        story_path=FIXTURES / "story-render.json",
        insights_path=str(FIXTURES / "insights.json"),
        aspect="9:16",
        allow_sensitive=False,
        allow_unknown_names=False,
    )
    url, server = preview.make_server(state, 0)
    try:
        assert "127.0.0.1" in url
        assert url.endswith("/")
        assert server.server_address[1] > 0
    finally:
        server.server_close()


@needs_node
def test_page_is_served_and_reloads_are_injected() -> None:
    """GET / 返回整页 HTML, 并带一段预览专用的刷新脚本。"""
    with Server(FIXTURES / "story-render.json", FIXTURES / "insights.json") as server:
        status, body = server.get("/")

    assert status == 200
    assert "提交总数" in body
    assert "/__revision" in body
    assert body.count("</html>") == 1


@needs_node
def test_revision_changes_when_story_changes(tmp_path: Path) -> None:
    """改一次 story.json, revision 必须变, 页面内容也要跟着变。"""
    story = tmp_path / "story.json"
    shutil.copy(FIXTURES / "story-render.json", story)

    with Server(story, FIXTURES / "insights.json") as server:
        _, before = server.get("/__revision")
        _, page_before = server.get("/")

        text = story.read_text(encoding="utf-8").replace("提交总数", "提交总量")
        story.write_text(text, encoding="utf-8")

        _, after = server.get("/__revision")
        _, page_after = server.get("/")

    assert before != after
    assert "提交总数" in page_before
    assert "提交总量" in page_after


@needs_node
def test_invalid_story_shows_error_page(tmp_path: Path) -> None:
    """校验不过时给一个可读的错误页, 而不是空白或 500。"""
    story = tmp_path / "story.json"
    story.write_text(
        '{"version": 1, "meta": {"year": 2024, "locale": "zh-CN", "theme": "neon",'
        ' "tone": "d", "tz": "Asia/Shanghai", "build_id": ""},'
        ' "cards": [{"id": "c1", "type": "big-number", "copy": {"headline": "共 12 次"}}]}',
        encoding="utf-8",
    )

    with Server(story, FIXTURES / "insights.json") as server:
        status, body = server.get("/")

    assert status == 200
    assert "预览失败" in body
    assert "NUMBER_NOT_IN_PLACEHOLDER" in body


@needs_node
def test_unknown_path_is_404() -> None:
    """除了 / 与 /__revision, 其他路径一律 404。"""
    with Server(FIXTURES / "story-render.json", FIXTURES / "insights.json") as server:
        status, _ = server.get("/nope")

    assert status == 404
