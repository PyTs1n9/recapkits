"""随包字体: 两段 @font-face、零外部请求、体积在预算内。

字体在构建期子集化并 base64 内联 (见 scripts/build-fonts.py)。这条断言守的是
"用户拿到 wheel 后断网也能出图": 一旦有人把 @font-face 改回 CDN, 或者把系统字族
加回 --font-sans, 这里就会红。
"""

import base64
import json
import re
from pathlib import Path

import pytest

from recapkits.render import node
from recapkits.render.pipeline import render_document

FIXTURES = Path(__file__).parent.parent / "fixtures"
STORY = FIXTURES / "story-render.json"
INSIGHTS = FIXTURES / "insights.json"
MANIFEST = (
    Path(__file__).parent.parent.parent / "renderer" / "src" / "assets" / "fonts.manifest.json"
)

#: 单文件 HTML 的上限; 与阶段任务书的尺寸预算一致。
HTML_LIMIT = 2_600_000

#: 系统字族一个都不许回退: 回退正是跨平台差异的来源。
SYSTEM_FAMILIES = ("PingFang", "Microsoft YaHei", "Segoe UI", "-apple-system")

_NODE = node.node_info()
needs_node = pytest.mark.skipif(
    _NODE is None or _NODE.major < node.MIN_NODE_MAJOR or not node.BUNDLE.is_file(),
    reason="需要 Node 22+ 与已构建的 renderer assets",
)


def _html() -> str:
    return render_document(STORY, str(INSIGHTS), aspect="9:16")


def test_manifest_lists_two_bundled_fonts() -> None:
    """manifest 是字体与构建脚本之间的契约: 两份、都有 sha256 与许可文件。"""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    keys = [entry["key"] for entry in manifest["fonts"]]
    assert keys == ["noto-sans-sc", "inter-tight"]
    for entry in manifest["fonts"]:
        assert len(entry["source_sha256"]) == 64
        assert len(entry["output_sha256"]) == 64
        assert entry["woff2_bytes"] > 0
        assert entry["license"].startswith("OFL-")


@needs_node
def test_html_embeds_fonts_and_never_calls_network() -> None:
    """两段 @font-face、两次 base64、零外链, 且体积在预算内。"""
    html = _html()
    data = html.encode("utf-8")

    assert html.count("@font-face") == 2
    assert html.count("data:font/woff2;base64,") == 2
    assert "http://" not in html and "https://" not in html
    assert len(data) <= HTML_LIMIT, f"HTML {len(data):,} 字节超过预算 {HTML_LIMIT:,}"


@needs_node
def test_font_stack_has_no_system_fallback() -> None:
    """--font-sans 只列随包字族 + sans-serif: 系统字族是跨平台差异的来源。"""
    html = _html()

    assert '--font-sans: "Inter Tight", "Noto Sans SC", sans-serif;' in html
    for family in SYSTEM_FAMILIES:
        assert family not in html, f"字族里仍有系统字体 {family}"


@needs_node
def test_embedded_payloads_match_the_manifest() -> None:
    """内联的 base64 就是 manifest 记录的那两份字体, 防止"改了字体忘了重建"。"""
    payloads = re.findall(r"url\(data:font/woff2;base64,([A-Za-z0-9+/=]+)\)", _html())
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert len(payloads) == 2
    embedded = sorted(len(base64.b64decode(payload)) for payload in payloads)
    expected = sorted(entry["woff2_bytes"] for entry in manifest["fonts"])
    assert embedded == expected
