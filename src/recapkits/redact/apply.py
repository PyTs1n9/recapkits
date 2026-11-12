"""redact 的数据层: 一次变换, 两份产物。

渲染层拿到的已经是烘焙后的字符串 (`copy` / `rows` / `number`), 哪一段是实体已经
丢了; PNG 与 MP4 又复用同一条截图链路, 替换点漏一层就是泄漏。所以脱敏只在这里
做一次, 产物是两份可以直接交给 `render` 的 JSON。

**两份必须同时写。** `story.json` 的占位符在烘焙时从 insights 取数; 只改文案,
数字与实体名会被旧 insights 原样带回。写完还要再验一次"每个占位符都能在新
insights 里解析", 否则用户拿到的是一份看似脱敏、渲染时才崩的组合。

顺序即保证: 结构化 PII -> 抑制表 -> 一致化假名。假名放在抑制表之后, 因为用户
点名要消失的词不该再换个名字出现。
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from recapkits.errors import RecapError
from recapkits.redact.entities import collect_entities, rewrite_insights
from recapkits.redact.pseudonym import Book
from recapkits.redact.text import REMOVED, Audit, Suppressor, replace_entities, scrub
from recapkits.story.rules import PLACEHOLDER
from recapkits.story.schema import Story, StorySchemaError
from recapkits.story.validate import build_refs


@dataclass
class Redaction:
    """两份脱敏产物与它们的账。"""

    insights: dict[str, Any]
    story: dict[str, Any]
    audit: Audit
    id_map: dict[str, str]


def _rewrite_copy(
    text: str,
    *,
    id_map: dict[str, str],
    replacements: dict[str, str],
    suppressor: Suppressor,
    audit: Audit,
) -> str:
    """先换占位符里的 id, 再只处理占位符之外的文字。

    顺序不能反: 占位符里的转义实体仍是 ASCII (`health`), 直接做文本替换会把 id
    改成一个非法片段。占位符本身也不参与 PII 与抑制表 —— 那是数据坐标, 不是文案。
    """

    def swap(match: re.Match[str]) -> str:
        insight_id, dot, fact_key = match.group(1).rpartition(".")
        new_id = id_map.get(insight_id) if dot else None
        return match.group(0) if new_id is None else "{{" + new_id + "." + fact_key + "}}"

    rewritten = PLACEHOLDER.sub(swap, text)
    pieces: list[str] = []
    cursor = 0
    for match in PLACEHOLDER.finditer(rewritten):
        prose = rewritten[cursor : match.start()]
        pieces.append(replace_entities(scrub(prose, suppressor, audit), replacements))
        pieces.append(match.group(0))
        cursor = match.end()
    tail = rewritten[cursor:]
    pieces.append(replace_entities(scrub(tail, suppressor, audit), replacements))
    return "".join(pieces)


def rewrite_story(
    payload: dict[str, Any],
    *,
    id_map: dict[str, str],
    replacements: dict[str, str],
    suppressor: Suppressor,
    audit: Audit,
) -> None:
    """故事只有三处引用洞察: `insight`、`evidence` 与 copy 里的占位符。"""
    cards = payload.get("cards")
    for card in cards if isinstance(cards, list) else []:
        if not isinstance(card, dict):
            continue
        insight = card.get("insight")
        if isinstance(insight, str):
            card["insight"] = id_map.get(insight, insight)
        evidence = card.get("evidence")
        if isinstance(evidence, list):
            card["evidence"] = [
                id_map.get(item, item) if isinstance(item, str) else item for item in evidence
            ]
        copy = card.get("copy")
        if not isinstance(copy, dict):
            continue
        for slot, text in copy.items():
            if isinstance(text, str):
                copy[slot] = _rewrite_copy(
                    text,
                    id_map=id_map,
                    replacements=replacements,
                    suppressor=suppressor,
                    audit=audit,
                )


def check_resolvable(insights: dict[str, Any], story: dict[str, Any]) -> None:
    """写盘前的一致性闸门: 故事的每个占位符都能在脱敏后的 insights 里解析。"""
    try:
        refs = build_refs(insights)
        parsed = Story.from_dict(story)
    except StorySchemaError as exc:
        raise RecapError(f"脱敏产物没有通过结构校验: {exc}") from exc

    for index, card in enumerate(parsed.cards, start=1):
        allowed = [card.insight] if card.insight else []
        allowed += card.evidence
        for ident in allowed:
            if ident not in refs:
                raise RecapError(f"脱敏后卡#{index}引用了不存在的洞察 {ident}")
        for slot, text in card.copy.items():
            for match in PLACEHOLDER.finditer(text):
                insight_id, dot, fact_key = match.group(1).rpartition(".")
                if not dot or insight_id not in refs:
                    raise RecapError(f"脱敏后卡#{index}的 {slot} 占位符无法解析: {match.group(0)}")
                if insight_id not in allowed:
                    raise RecapError(f"脱敏后卡#{index}的 {slot} 引用了未列出的洞察 {insight_id}")
                if fact_key not in refs[insight_id].facts:
                    raise RecapError(f"脱敏后 {insight_id} 没有事实 {fact_key}")


def redact_pair(
    insights: dict[str, Any], story: dict[str, Any], *, book: Book, words: list[str]
) -> Redaction:
    """原地脱敏两份结构; 返回结果与审计。"""
    audit = Audit()
    suppressor = Suppressor(words)
    kinds = collect_entities(insights)
    removed: list[str] = []
    for name in kinds:
        words_hit = suppressor.matches(name)
        if words_hit:
            removed.append(name)
            # 实体整体移除时不会经过 `apply`, 命中要在这里记账, 否则报告永远是 0。
            suppressor.record(words_hit)
    removed.sort()
    dropped = set(removed)
    book.assign({name: kind for name, kind in kinds.items() if name not in dropped})
    replacements = {name: (REMOVED if name in dropped else book.map[name]) for name in kinds}
    grouped: dict[str, list[str]] = {}
    for name, kind in kinds.items():
        grouped.setdefault(kind, []).append(name)
    audit.entity_kinds = {kind: sorted(names) for kind, names in grouped.items()}
    audit.removed = removed
    audit.pseudonyms = len(kinds) - len(removed)

    id_map = rewrite_insights(
        insights, suppressor=suppressor, audit=audit, replacements=replacements
    )
    rewrite_story(
        story,
        id_map=id_map,
        replacements=replacements,
        suppressor=suppressor,
        audit=audit,
    )
    audit.suppressed = dict(suppressor.hits)
    check_resolvable(insights, story)
    return Redaction(insights=insights, story=story, audit=audit, id_map=id_map)


def write_pair(out_dir: Path, insights: dict[str, Any], story: dict[str, Any]) -> tuple[Path, Path]:
    """原子写入两份。先写两个临时文件, 再替换 —— 中途失败时原文件仍是完整的一份。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    targets = (out_dir / "insights.json", out_dir / "story.json")
    temps = tuple(target.with_name(target.name + ".tmp") for target in targets)
    try:
        for temp, payload in zip(temps, (insights, story), strict=True):
            text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
            temp.write_bytes(text.encode("utf-8"))
    except OSError:
        for temp in temps:
            temp.unlink(missing_ok=True)
        raise
    for temp, target in zip(temps, targets, strict=True):
        os.replace(temp, target)
    return targets
