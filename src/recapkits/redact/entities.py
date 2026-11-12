"""实体侧的重写: 收集 Top-5 名单, 重写 `rank_*` 标题与 `conc.*` 的 id。

`conc.top_entity:<类别>:<转义实体>:<年份>` 的实体段就是用户数据
(`%54he%20%4didnight` 就是 `The Midnight`)。分享 `story.json` 等于分享 id, 所以
标题与 id 必须一起换 —— 只改标题不改 id, 等于把实体名写进了要分享的文件里。
"""

import re
from collections.abc import Iterator
from typing import Any
from urllib.parse import unquote

from recapkits.insights.detectors.generic import _escape_entity
from recapkits.redact.text import REMOVED, Audit, Suppressor, scrub

#: `conc.top_entity:<类别>:<转义实体>:<年份>`; 类别与转义段都不含冒号。
CONC_ID = re.compile(r"^conc\.top_entity:([^:]+):([^:]+):(\d{4})$")
RANK = re.compile(r"^rank_\d+$")


def facts(item: dict[str, Any]) -> list[dict[str, Any]]:
    """headline_fact 与 facts 的顺序展开; 非对象项跳过, 不让外部 JSON 崩掉。"""
    values: list[dict[str, Any]] = []
    headline = item.get("headline_fact")
    if isinstance(headline, dict):
        values.append(headline)
    body = item.get("facts")
    if isinstance(body, list):
        values.extend(fact for fact in body if isinstance(fact, dict))
    return values


def conc(item: dict[str, Any]) -> tuple[str, str, str] | None:
    """(实体类别, 转义实体, 年份); 不是集中度洞察就返回 None。"""
    if item.get("kind") != "conc.top_entity":
        return None
    match = CONC_ID.match(str(item.get("id", "")))
    if match is None:
        return None
    return match.group(1), match.group(2), match.group(3)


def rank_labels(item: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
    """`rank_*` 事实的 (容器, 原标题); 标题就是实体名, 顺序即名次。"""
    found: list[tuple[dict[str, Any], str]] = []
    for fact in facts(item):
        label = fact.get("label")
        if isinstance(label, str) and RANK.match(str(fact.get("key", ""))):
            found.append((fact, label))
    return found


def prose_fields(item: dict[str, Any]) -> Iterator[tuple[Any, Any]]:
    """要清洗的文本字段; `rank_*` 的标题交给假名阶段, 这里跳过。

    跳过是为了不让抑制表在实体标题上留一次"命中" —— 那个标题最终要么整体换成
    假名、要么整体移除, 中间的子串命中只会让审计数字虚高。
    """
    for fact in facts(item):
        if RANK.match(str(fact.get("key", ""))):
            continue
        for key in ("label", "display"):
            if isinstance(fact.get(key), str):
                yield fact, key
    caveats = item.get("caveats")
    if isinstance(caveats, list):
        for index, value in enumerate(caveats):
            if isinstance(value, str):
                yield caveats, index


def collect_entities(insights: dict[str, Any]) -> dict[str, str]:
    """原名 -> 实体类别; 来源是 `rank_*` 标题, 缺失时退回 id 里的转义段。"""
    kinds: dict[str, str] = {}
    items = insights.get("insights")
    if not isinstance(items, list):
        return kinds
    for item in items:
        if not isinstance(item, dict):
            continue
        parts = conc(item)
        if parts is None:
            continue
        labels = rank_labels(item)
        if labels:
            for _, label in labels:
                # 空白标题不是实体: 收进来会让 replace_entities 把每个空格都换掉。
                if not label.strip():
                    continue
                # 同名跨类别 (repo 与 artist 都叫 foo) 只保留先遇到的类别: 假名按
                # 名字分配, 一个名字只能有一个前缀, 否则同一实体会有两个名字。
                kinds.setdefault(label, parts[0])
        else:
            name = unquote(parts[1])
            if name:
                kinds.setdefault(name, parts[0])
    return kinds


def rewrite_insights(
    payload: dict[str, Any],
    *,
    suppressor: Suppressor,
    audit: Audit,
    replacements: dict[str, str],
) -> tuple[dict[str, str], set[str]]:
    """清洗文本、重写实体标题与 id。

    返回 (旧 id -> 新 id, 被抑制表整体移除的旧 id)。第二个返回值不是审计信息:
    那些 id 不能进还原表, 否则 render 会顺着 id 把用户点名要消失的实体带回来。
    """
    id_map: dict[str, str] = {}
    suppressed: set[str] = set()
    plans: list[tuple[dict[str, Any], tuple[str, str, str] | None, list[tuple[Any, str]]]] = []
    items = payload.get("insights")
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            plans.append((item, conc(item), rank_labels(item)))

    for item, parts, labels in plans:
        for container, key in prose_fields(item):
            container[key] = scrub(str(container[key]), suppressor, audit)
        if parts is None:
            continue
        for fact, original in labels:
            fact["label"] = replacements.get(original, fact["label"])
        top = labels[0][1] if labels else unquote(parts[1])
        old_id = str(item.get("id", ""))
        new_top = replacements.get(top)
        if new_top == REMOVED:
            # 抑制表在 `redact_insights` 里已经记录过命中, 这里只标记 id 不可还原。
            suppressed.add(old_id)
        elif new_top is None and suppressor.hits_on(top):
            new_top = REMOVED
            suppressor.record(suppressor.matches(top))
            suppressed.add(old_id)
        if new_top is None:
            new_top = top
        new_id = f"conc.top_entity:{parts[0]}:{_escape_entity(new_top)}:{parts[2]}"
        if new_id != old_id:
            id_map[old_id] = new_id
            item["id"] = new_id
    return id_map, suppressed
