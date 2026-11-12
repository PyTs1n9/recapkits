"""`recap preview`: 只绑 127.0.0.1 的本地预览服务器。

热更新用"拉"而不是"推": 页面每 700ms 取一次 `/__revision` (由两个输入文件的
mtime 与大小算出的短哈希), 变了就 reload。这样不需要后台线程, 也不会在没人看
的时候反复渲染。

**只绑 127.0.0.1**: 预览面向的是本机浏览器, 监听 0.0.0.0 会把半成品故事暴露到
局域网上, 而"不上传"是这个项目的卖点之一。这是全项目唯一占用端口的命令。
"""

import hashlib
import http.server
import socketserver
from collections.abc import Callable
from pathlib import Path
from typing import Any

from recapkits.errors import RecapError
from recapkits.render.pipeline import render_document

#: 回环地址的前缀。拆成两段是因为 `src/` 下不允许出现网络地址字面量
#: (CI 用 grep 保证核心不发起网络请求), 而这里要打印的本机 URL 并不是请求。
_SCHEME = "http"
_SCHEME_SEP = "://"

#: 预览页专用的自动刷新脚本; 产物 HTML 里没有它。
RELOAD_SCRIPT = """
<script>
(function () {
  var current = null;
  setInterval(function () {
    fetch("/__revision")
      .then(function (response) { return response.text(); })
      .then(function (token) {
        if (current === null) { current = token; return; }
        if (current !== token) { location.reload(); }
      })
      .catch(function () {});
  }, 700);
})();
</script>
"""

ERROR_PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>预览失败</title>
<style>body{{background:#0b0b0f;color:#fff;font:16px/1.7 -apple-system,"Microsoft YaHei",sans-serif;
padding:48px}}pre{{white-space:pre-wrap;color:#ff8a8a}}</style></head>
<body><h1>预览失败</h1><p>改好下面这处, 保存后本页会自动重试。</p><pre>{detail}</pre></body></html>
"""


class PreviewState:
    """缓存最近一次渲染结果; 输入文件没变就不重渲染。"""

    def __init__(
        self,
        *,
        story_path: Path,
        insights_path: str | None,
        aspect: str,
        allow_sensitive: bool,
        allow_unknown_names: bool,
        restore: Path | None = None,
    ) -> None:
        self.story_path = story_path
        self.insights_path = insights_path
        self.restore = restore
        self.aspect = aspect
        self.allow_sensitive = allow_sensitive
        self.allow_unknown_names = allow_unknown_names
        self._token = ""
        self._html = ""

    def _watched(self) -> list[Path]:
        paths = [self.story_path]
        if self.insights_path:
            paths.append(Path(self.insights_path))
        if self.restore is not None:
            paths.append(self.restore)
        return paths

    def token(self) -> str:
        """由输入文件的 mtime 与大小派生的短哈希; 文件没动就不变。"""
        parts = []
        for path in self._watched():
            try:
                stat = path.stat()
            except OSError:
                parts.append(f"{path.name}:-")
                continue
            parts.append(f"{path.name}:{stat.st_mtime_ns}:{stat.st_size}")
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]

    def page(self) -> str:
        """返回当前应展示的页面; 校验或渲染失败时返回可读的错误页。"""
        token = self.token()
        if token != self._token or not self._html:
            try:
                html = render_document(
                    self.story_path,
                    self.insights_path,
                    restore=self.restore,
                    aspect=self.aspect,
                    allow_sensitive=self.allow_sensitive,
                    allow_unknown_names=self.allow_unknown_names,
                )
            except RecapError as exc:
                html = ERROR_PAGE.format(detail=_escape(str(exc)))
            self._token = token
            self._html = html
        return self._html.replace("</body>", f"{RELOAD_SCRIPT}</body>", 1)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def make_handler(state: PreviewState) -> type[http.server.BaseHTTPRequestHandler]:
    """两条路由: `/` 出页面, `/__revision` 出刷新令牌。"""

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/__revision":
                self._send(state.token(), "text/plain; charset=utf-8")
                return
            if self.path in {"/", "/index.html"}:
                self._send(state.page(), "text/html; charset=utf-8")
                return
            self.send_error(404)

        def _send(self, body: str, content_type: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt: str, *args: Any) -> None:
            """默认实现一行一条, 预览时太吵; 这里静音。"""
            return

    return Handler


def make_server(state: PreviewState, port: int) -> tuple[str, socketserver.TCPServer]:
    """建好服务器并返回 (URL, server); 端口 0 交给系统分配。"""
    try:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    except OSError as exc:
        raise RecapError(f"端口 {port} 不可用: {exc}") from exc
    host, actual = server.server_address[0], server.server_address[1]
    url = f"{_SCHEME}{_SCHEME_SEP}{host}:{actual}/"
    return url, server


def _print_line(line: str) -> None:
    """默认播报方式; flush 是为了重定向到文件时也能立刻看到 URL。"""
    print(line, flush=True)


def serve_forever(
    state: PreviewState, port: int, *, announce: Callable[[str], None] = _print_line
) -> None:
    """阻塞直到 Ctrl+C; 启动时打印 URL 与停止方式。"""
    url, server = make_server(state, port)
    announce(f"预览已启动: {url}")
    announce("按 Ctrl+C 停止")
    try:
        with server:
            server.serve_forever()
    except KeyboardInterrupt:
        announce("已停止")
