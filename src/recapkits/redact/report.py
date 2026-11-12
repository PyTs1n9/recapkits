# ruff: noqa: RUF001
# 报告是给人看的中文, 全角标点在这里是内容而不是代码, 故整体豁免 RUF001。
"""审计输出: 计数总是打, 样本只上 TTY。

样本是**被替换掉的原文**。打印它正是为了让用户发现"你把我自己的艺人名也抹了":
过度脱敏是真实的失败模式, 而只有用户能判断哪个名字不该消失。但它绝不能进文件
或 CI 日志 —— 重定向到文件或管道时只打计数, 因为那份文件迟早会被贴进 issue。

报告也不回显 `redactions.json` 的内容: 那是"原名 -> 假名"的完整映射, 等于原文。
"""

import sys
from typing import TextIO

from recapkits.redact.pseudonym import DEFAULT_PREFIX, KIND_PREFIX
from recapkits.redact.text import Audit

#: 固定顺序, 让两次运行的报告可以逐行对比。
PII_ORDER = ("URL", "邮箱", "IBAN", "卡号", "路径", "IP", "坐标", "电话", "@handle")
SAMPLES = 5

KIND_LABEL = {**KIND_PREFIX, "entity": DEFAULT_PREFIX}


def _is_tty(stream: TextIO) -> bool:
    probe = getattr(stream, "isatty", None)
    return bool(probe()) if callable(probe) else False


def _pii_line(audit: Audit) -> str:
    found = [f"{name} {audit.pii_counts[name]}" for name in PII_ORDER if audit.pii_counts.get(name)]
    total = sum(audit.pii_counts.values())
    detail = " · ".join(found) if found else "无"
    return f"  结构化 PII  {total} 处（{detail}）"


def _pseudonym_line(audit: Audit) -> str:
    parts = []
    removed = set(audit.removed)
    for kind, names in sorted(audit.entity_kinds.items()):
        kept = len([name for name in names if name not in removed])
        if kept:
            parts.append(f"{KIND_LABEL.get(kind, kind)} {kept}")
    detail = f"（{' · '.join(parts)}）" if parts else ""
    return f"  假名        {audit.pseudonyms} 个实体{detail}"


def render(audit: Audit, *, stream: TextIO | None = None, salt_note: str | None = None) -> None:
    """把审计写到 stderr; 样本只在 TTY 上出现。"""
    target = sys.stderr if stream is None else stream
    lines = ["脱敏审计", _pii_line(audit)]
    lines.append(
        f"  抑制词      {len(audit.suppressed)} 个词命中 {sum(audit.suppressed.values())} 处"
    )
    lines.append(_pseudonym_line(audit))

    total = audit.entity_total
    removed = len(audit.removed)
    percent = (100 * removed / total) if total else 0.0
    lines.append(f"  实体替换    {removed}/{total}（{percent:.0f}%）")
    if total and percent > 80:
        lines.append("  提示        可能过度脱敏，检查 redact.txt 是否写得太宽")

    if _is_tty(target):
        for category in PII_ORDER:
            samples = audit.pii_samples.get(category)
            if samples:
                lines.append(f"      {category}  " + " · ".join(samples[:SAMPLES]))
        if audit.suppressed:
            words = sorted(audit.suppressed)
            lines.append("      抑制  " + " · ".join(words[:SAMPLES]))
        for kind, names in sorted(audit.entity_kinds.items()):
            label = KIND_LABEL.get(kind, kind)
            lines.append(f"      {label}  " + " · ".join(names[:SAMPLES]))

    if salt_note:
        lines.append(f"  说明        {salt_note}")
    print("\n".join(lines), file=target)
