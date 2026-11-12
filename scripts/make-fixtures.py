#!/usr/bin/env python3
"""生成合成导出 fixture: 固定 seed, 逐字节可复现。

真实导出**永不进 git**: 一行 IP、一个档案名就足够反查到具体的人。本脚本只产出
合成数据, `--check` 只比对不写盘, CI 与验收命令用它证明 fixture 没有被手改。

每个源一个构建模块 (`fixtures_spotify.py` / `fixtures_netflix.py`), 它们各自
负责「数据刻意做脏」的细节; 这里只管收件、比对与落盘。
"""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

import fixtures_netflix
import fixtures_spotify

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

#: 每个构建器返回 {相对 tests/fixtures 的路径: 文件字节}。新源在这里追加一行。
BUILDERS: tuple[Callable[[], dict[str, bytes]], ...] = (
    fixtures_spotify.build,
    fixtures_netflix.build,
)


def build() -> dict[str, bytes]:
    """所有源的 fixture; 同一路径被两个构建器写出时直接失败。"""
    expected: dict[str, bytes] = {}
    for builder in BUILDERS:
        for relative, payload in builder().items():
            if relative in expected:
                raise SystemExit(f"fixture 路径重复: {relative}")
            expected[relative] = payload
    return expected


def _check(expected: dict[str, bytes]) -> int:
    """逐字节比对; 任何差异都算失败, 并列出文件名。"""
    drifted = [
        relative
        for relative, payload in expected.items()
        if not (FIXTURES / relative).is_file() or (FIXTURES / relative).read_bytes() != payload
    ]
    if drifted:
        for relative in drifted:
            print(f"与生成结果不一致: {relative}", file=sys.stderr)
        return 1
    print(f"fixture 与生成结果一致: {len(expected)} 个文件")
    return 0


def _write(expected: dict[str, bytes]) -> int:
    for relative, payload in expected.items():
        path = FIXTURES / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    print(f"已写入 {len(expected)} 个文件到 {FIXTURES}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成合成导出 fixture (固定 seed)")
    parser.add_argument("--check", action="store_true", help="只比对, 不写盘")
    args = parser.parse_args(argv)
    expected = build()
    return _check(expected) if args.check else _write(expected)


if __name__ == "__main__":
    raise SystemExit(main())
