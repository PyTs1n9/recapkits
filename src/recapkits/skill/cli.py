"""`recap skill install`: 只做参数校验与输出, 落盘逻辑在 install.py。

`print` 是唯一不写文件的 target, 因此它必须单独使用 —— 混在文件 target 里,
用户无法判断 stdout 的那一份到底装没装。
"""

import argparse
import sys
from pathlib import Path

from recapkits.errors import RecapError
from recapkits.skill import read_text
from recapkits.skill.install import UNCHANGED, install
from recapkits.workspace import load_workspace


def cmd_skill_install(args: argparse.Namespace) -> int:
    """装 skill 到当前项目; 本地模式下拒绝。"""
    targets = list(dict.fromkeys(args.target))
    if "print" in targets and len(targets) > 1:
        raise RecapError("--target print 不能与其他 target 同用: 它只打印, 不写文件")

    workspace = load_workspace()
    if workspace is not None and workspace.local_only:
        raise RecapError("本地模式不安装 agent skill: 先 recap init --no-local-only")

    if targets == ["print"]:
        sys.stdout.write(read_text())
        return 0

    for plan in install(targets, root=Path.cwd(), force=bool(args.force)):
        verb = "未改动" if plan.status == UNCHANGED else "已写入"
        print(f"{verb} {plan.path}")
    return 0
