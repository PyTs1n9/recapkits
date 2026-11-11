"""把 `renderer/dist/` 同步到 `src/recapkits/render/assets/`。

`assets/` 是入库的: wheel 里必须有渲染器, 否则装完就 `recap render` 就报"未构建"。
`dist/` 不入库 (构建产物), 所以两边一致需要人推一把 —— 而"忘了推"的后果是用户
拿到旧界面, 且不会有任何报错。因此 `--check` 比较文件清单与 sha256, CI 用它守这条。

用法:
    python scripts/sync-renderer.py           # 同步
    python scripts/sync-renderer.py --check   # 只比较, 不一致退出 1
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "renderer" / "dist"
TARGET = ROOT / "src" / "recapkits" / "render" / "assets"


def digest(path: Path) -> str:
    """文件内容的 sha256 前 16 位; 够用且好读。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def manifest(root: Path) -> dict[str, str]:
    """相对路径 -> 内容摘要; 排序后返回, 便于逐行比较。"""
    if not root.is_dir():
        return {}
    return {
        str(path.relative_to(root)).replace("\\", "/"): digest(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def describe(left: dict[str, str], right: dict[str, str]) -> list[str]:
    """列出两份清单的差异; 空列表表示一致。"""
    problems = [f"  只在 renderer/dist 里: {name}" for name in sorted(set(left) - set(right))]
    problems += [f"  只在 assets 里: {name}" for name in sorted(set(right) - set(left))]
    problems += [
        f"  内容不同: {name} ({left[name]} != {right[name]})"
        for name in sorted(set(left) & set(right))
        if left[name] != right[name]
    ]
    return problems


def main(argv: list[str] | None = None) -> int:
    """同步或校验两侧; 返回进程退出码。"""
    parser = argparse.ArgumentParser(description="同步 renderer/dist 到 recapkits assets")
    parser.add_argument("--check", action="store_true", help="只比较, 不写入")
    args = parser.parse_args(argv)

    dist = manifest(SOURCE)
    if not dist:
        print(f"错误: {SOURCE} 为空或不存在; 先 pnpm --dir renderer build", file=sys.stderr)
        return 1

    if args.check:
        problems = describe(dist, manifest(TARGET))
        if problems:
            print("渲染器产物与 assets 不一致:", file=sys.stderr)
            for line in problems:
                print(line, file=sys.stderr)
            print("修复: python scripts/sync-renderer.py", file=sys.stderr)
            return 1
        print(f"渲染器产物一致: {len(dist)} 个文件")
        return 0

    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET)
    print(f"已同步 {len(dist)} 个文件到 {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
