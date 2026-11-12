"""构建随包字体: 固定 URL + sha256 -> 子集化 -> WOFF2 -> base64。

为什么是构建期而不是运行期: `src/` 的硬约束是零第三方依赖 (Windows 的 tzdata 除外)。
在渲染时用 fonttools 按文案裁字形, 等于把 fonttools 变成运行期依赖, 而且 HTML 输出会
要求用户装一个 C 扩展。所以字体在提交前就裁好, 运行时只是读一份纯 ASCII 文本。

产物:
    renderer/src/assets/noto-sans-sc.woff2.b64
    renderer/src/assets/inter-tight.woff2.b64
    renderer/src/assets/fonts.manifest.json
    renderer/public/fonts/OFL-*.txt       (随 wheel 的许可证, 由 vite 拷进 dist)
    renderer/public/fonts/NOTICE.txt

用法:
    python scripts/build-fonts.py           # 下载 + 子集化 + 写产物
    python scripts/build-fonts.py --check   # 只校验 manifest 与文件哈希, 不下载
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "renderer" / "src" / "assets"
PUBLIC = ROOT / "renderer" / "public" / "fonts"
CACHE = ROOT / "build" / "fonts"
MANIFEST = ASSETS / "fonts.manifest.json"

#: 尺寸预算。超了先量、再改方案 (收字形集 / 拆静态字重), 不许悄悄放宽。
BUDGETS = {"noto-sans-sc": 1_600_000, "inter-tight": 60_000}

#: 源字体与许可证。URL 钉在提交号上而不是 main: 上游改一次文件, 这里的 sha256
#: 就会失配, 而失配必须是一次显式失败, 不能是"某天构建突然不一样了"。
NOTO_COMMIT = "2894aab31764f10f29c421bdfd2340d3b382d384"
INTER_COMMIT = "fac60545cc0de9d4eff6eb5b1ab88bcdfc9ecc69"
RAW = "https://raw.githubusercontent.com/google/fonts"


@dataclass(frozen=True)
class FontSpec:
    key: str
    family: str
    url: str
    sha256: str
    license_url: str
    license_sha256: str
    license_name: str
    output: str
    limit: int


SOURCES = (
    FontSpec(
        key="noto-sans-sc",
        family="Noto Sans SC",
        url=f"{RAW}/{NOTO_COMMIT}/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf",
        sha256="a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da",
        license_url=f"{RAW}/{NOTO_COMMIT}/ofl/notosanssc/OFL.txt",
        license_sha256="1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9",
        license_name="OFL-NotoSansSC.txt",
        output="noto-sans-sc.woff2.b64",
        limit=BUDGETS["noto-sans-sc"],
    ),
    FontSpec(
        key="inter-tight",
        family="Inter Tight",
        url=f"{RAW}/{INTER_COMMIT}/ofl/intertight/InterTight%5Bwght%5D.ttf",
        sha256="b81b73dcb64df3c230cabade7df6c5773bf863233f24c9ee51087519f1f88b6f",
        license_url=f"{RAW}/{INTER_COMMIT}/ofl/intertight/OFL.txt",
        license_sha256="50240ab035cf1b6b3307940235481d515c4b6de3ab1fa843dbe59e7892cb9d58",
        license_name="OFL-InterTight.txt",
        output="inter-tight.woff2.b64",
        limit=BUDGETS["inter-tight"],
    ),
)

#: 常用标点。全角标点必须在内: 中文文案里的逗号、句号若缺字形会回退系统字体,
#: 而"回退"正是跨平台差异的来源。
PUNCTUATION = "·—–…％‰「」『』《》〈〉、。，．！？：；（）【】“”‘’～￥　"  # noqa: RUF001


def gb2312_level1() -> list[str]:
    """GB/T 2312 一级字 (16-55 区, 3755 个), 按编码顺序。

    直接从标准库的 gb2312 编解码器枚举, 不额外带一份字表: 字表是数据, 会抄错;
    编码器是事实, 不会。
    """
    chars: list[str] = []
    for high in range(0xB0, 0xD8):
        for low in range(0xA1, 0xFF):
            try:
                chars.append(bytes([high, low]).decode("gb2312"))
            except UnicodeDecodeError:
                continue
    if len(chars) != 3755:  # pragma: no cover - 只可能因为 Python 编码器异常
        raise SystemExit(f"GB2312 一级字应为 3755 个, 实际 {len(chars)}")
    return chars


def codepoints() -> list[int]:
    """子集的码位集: 一级字 + ASCII + 常用标点。"""
    chars = set(gb2312_level1())
    chars.update(chr(code) for code in range(0x20, 0x7F))
    chars.update(PUNCTUATION)
    return sorted(ord(char) for char in chars)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str, expected: str) -> bytes:
    """按 sha256 取一个文件; 命中 build/fonts/ 缓存就不联网。"""
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / expected
    if cached.is_file():
        data = cached.read_bytes()
        if digest(data) == expected:
            return data
        cached.unlink()
    request = urllib.request.Request(url, headers={"User-Agent": "recapkits-build-fonts"})
    with urllib.request.urlopen(request, timeout=180) as response:
        data = response.read()
    actual = digest(data)
    if actual != expected:
        raise SystemExit(f"sha256 不符: {url}\n  期望 {expected}\n  实际 {actual}")
    cached.write_bytes(data)
    return data


def subset_font(ttf: bytes, spec: FontSpec) -> tuple[bytes, int]:
    """裁到码位集, 转 WOFF2, 保留 wght 轴; 返回 (字节, 字形数)。

    全程在内存里做: Windows 上临时文件会被字体对象持有句柄, 退出时删不掉
    (PermissionError: 另一个程序正在使用此文件), 而这里根本不需要落盘。
    """
    from io import BytesIO

    from fontTools import subset as ft_subset

    options = ft_subset.Options()
    options.flavor = "woff2"
    options.hinting = False
    options.name_IDs = ["*"]
    options.notdef_outline = True
    codes = codepoints()

    font = ft_subset.load_font(BytesIO(ttf), options)
    try:
        subsetter = ft_subset.Subsetter(options=options)
        subsetter.populate(unicodes=codes)
        subsetter.subset(font)
        buffer = BytesIO()
        ft_subset.save_font(font, buffer, options)
        data = buffer.getvalue()
    finally:
        font.close()

    if data[:4] != b"wOF2":
        raise SystemExit(f"{spec.key}: 产物不是 WOFF2")
    with _open_woff2(data) as subset_font:
        axes = [axis.axisTag for axis in subset_font["fvar"].axes] if "fvar" in subset_font else []
        if "wght" not in axes:
            raise SystemExit(f"{spec.key}: 子集丢了 wght 轴 ({axes})")
        glyphs = len(subset_font.getGlyphOrder())
    return data, glyphs


def _open_woff2(data: bytes) -> Any:
    """在内存里打开 WOFF2; 只用于读 fvar 与字形数。"""
    from io import BytesIO

    from fontTools.ttLib import TTFont

    return TTFont(BytesIO(data))


def render_notice(entries: list[dict[str, Any]]) -> str:
    """随字体一起分发的来源与许可说明; 用户拿到 wheel 就能回答"这些字从哪来"。"""
    lines = [
        "recapkits 随包字体",
        "==================",
        "",
        "以下字体的字形经子集化后内联进渲染器, 均为 SIL Open Font License 1.1。",
        "完整许可文本见本目录的 OFL-*.txt。",
        "",
    ]
    for entry in entries:
        lines += [
            f"{entry['family']} (variable, wght 轴保留)",
            f"  来源     {entry['source']}",
            f"  源 sha256 {entry['source_sha256']}",
            f"  子集     一级字 3755 + ASCII + 标点 ({entry['codepoints']} 个码位)",
            f"  产物     {entry['output']} ({entry['woff2_bytes']:,} 字节 WOFF2)",
            f"  许可     {entry['license']}",
            "",
        ]
    return "\n".join(lines)


def build() -> int:
    """下载、子集化、写产物与 manifest。"""
    ASSETS.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for spec in SOURCES:
        ttf = download(spec.url, spec.sha256)
        woff2, glyphs = subset_font(ttf, spec)
        if len(woff2) > spec.limit:
            raise SystemExit(
                f"{spec.key}: WOFF2 {len(woff2):,} 字节超过预算 {spec.limit:,}; "
                "先收字形集或拆静态字重, 不许改断言"
            )
        encoded = base64.b64encode(woff2)
        # 不写换行: ?raw 会把它原样带进 CSS 的 url(), 一个换行就是一处坏掉的字体。
        (ASSETS / spec.output).write_bytes(encoded)
        license_text = download(spec.license_url, spec.license_sha256)
        (PUBLIC / spec.license_name).write_bytes(license_text)
        entries.append(
            {
                "key": spec.key,
                "family": spec.family,
                "source": spec.url,
                "source_sha256": spec.sha256,
                "source_bytes": len(ttf),
                "output": spec.output,
                "output_sha256": digest(encoded),
                "woff2_sha256": digest(woff2),
                "woff2_bytes": len(woff2),
                "b64_bytes": len(encoded),
                "glyphs": glyphs,
                "codepoints": len(codepoints()),
                "license": spec.license_name,
            }
        )
        print(f"{spec.key:14} {len(woff2):>9,} B WOFF2  {len(encoded):>9,} B base64  {glyphs} 字形")

    from fontTools import version as fonttools_version

    manifest = {"fonttools": fonttools_version, "fonts": entries}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (PUBLIC / "NOTICE.txt").write_text(render_notice(entries), encoding="utf-8")
    print(f"manifest {MANIFEST.relative_to(ROOT)}")
    print(f"license  {PUBLIC.relative_to(ROOT)}/")
    return 0


def check() -> int:
    """只校验 manifest 与已提交产物的哈希, 不下载、不重算子集。"""
    if not MANIFEST.is_file():
        print(f"错误: 缺少 {MANIFEST.relative_to(ROOT)}; 先跑 python scripts/build-fonts.py")
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems: list[str] = []
    for entry in manifest.get("fonts", []):
        path = ASSETS / str(entry.get("output", ""))
        if not path.is_file():
            problems.append(f"缺少产物 {path.name}")
            continue
        encoded = path.read_bytes()
        if digest(encoded) != entry.get("output_sha256"):
            problems.append(f"{path.name}: base64 内容的 sha256 与 manifest 不符")
            continue
        try:
            raw = base64.b64decode(encoded, validate=True)
        except ValueError:
            problems.append(f"{path.name}: 不是合法 base64 (可能被编辑器加了换行)")
            continue
        if len(raw) != entry.get("woff2_bytes"):
            problems.append(
                f"{path.name}: 解码后 {len(raw)} 字节, manifest 记的是 {entry['woff2_bytes']}"
            )
        if raw[:4] != b"wOF2":
            problems.append(f"{path.name}: 解码后不是 WOFF2")
        if not (PUBLIC / str(entry.get("license", ""))).is_file():
            problems.append(f"缺少许可证 {entry.get('license')}")
    if not (PUBLIC / "NOTICE.txt").is_file():
        problems.append("缺少 NOTICE.txt")
    if problems:
        print("字体产物与 manifest 不一致:", file=sys.stderr)
        for line in problems:
            print(f"  {line}", file=sys.stderr)
        print("修复: python scripts/build-fonts.py", file=sys.stderr)
        return 1
    total = sum(int(entry["woff2_bytes"]) for entry in manifest.get("fonts", []))
    print(f"字体产物一致: {len(manifest.get('fonts', []))} 份, 共 {total:,} 字节 WOFF2")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="构建随包字体")
    parser.add_argument("--check", action="store_true", help="只校验 manifest 与文件哈希, 不下载")
    args = parser.parse_args(argv)
    return check() if args.check else build()


if __name__ == "__main__":
    raise SystemExit(main())
