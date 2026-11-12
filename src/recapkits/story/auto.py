"""`recap story --auto`: 从已选洞察规划一份能过校验器的故事。

四条不可让步的规则:

1. **只读 insights.json 的已选列表。** `select()` 已经截断并附回 `vol.daily_series`;
   在这里重排或重算分数, 两套排序必然漂移。
2. **生成后立刻自检** (`Story.from_dict` → `validate_story`), 零错误才写盘。写出坏
   `story.json` 只会把失败推迟到 render, 用户会看到两条互相矛盾的错误。
3. **高敏洞察不进自动规划。** 授权是用户的决定, 不是规划器的。
4. **跳过必须带理由。** 「跳过」两个字没有信息量; 理由要说清是闸门关闭、数据不足,
   还是 `--top` 截断。
5. **多源只讲一个源。** 主源按已选洞察的多数票定; 其余源的卡进跳过表并写明原因 ——
   把 git 的日序列和 spotify 的总时长拼进同一份故事, 读者无从解释。
"""

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

from recapkits.errors import RecapError
from recapkits.insights.engine import RENDER_ONLY_KINDS
from recapkits.story import templates
from recapkits.story.refs import build_refs
from recapkits.story.schema import InsightRef

#: 跳过理由的固定文案; 原文照抄进跳过表, 不要在各处另写一版。
NO_TOTAL = "没有 vol.total：先跑 recap import"  # noqa: RUF001
NO_CONC = "没有 conc.top_entity：事件不足 50 条时不出集中度"  # noqa: RUF001
NO_DAILY = "没有 vol.daily_series：工作区没有事件，或数据不足时它与其余洞察一起被闸门关闭"  # noqa: RUF001
NO_HOUR = "没有 time.hour_rhythm：活跃日不足 30 天时被闸门关闭"  # noqa: RUF001
SENSITIVE = "需要 --allow-sensitive"
SUMMARY_SHORT = "可引洞察不足 3 条：--top 太小，或数据源太少"  # noqa: RUF001
MIXED = "本回顾以 {primary} 为主源，{others} 的洞察未入卡"  # noqa: RUF001


@dataclass(frozen=True)
class Skip:
    """一张没被规划出来的卡, 以及为什么。"""

    card: str
    reason: str


@dataclass(frozen=True)
class Plan:
    """一次自动规划的结果; `story` 是可直接写盘的 story.json 结构。"""

    story: dict[str, Any]
    skips: tuple[Skip, ...]

    @property
    def cards(self) -> tuple[str, ...]:
        return tuple(str(card["id"]) for card in self.story["cards"])

    def as_json(self) -> str:
        """固定缩进 + 末尾换行; 同输入两次必须字节相同。"""
        return json.dumps(self.story, ensure_ascii=False, indent=2) + "\n"


def _group(refs: dict[str, InsightRef]) -> dict[str, list[InsightRef]]:
    """按 kind 建索引; 按 id 排序, 让"输入顺序"不参与结果。"""
    grouped: dict[str, list[InsightRef]] = {}
    for ident in sorted(refs):
        ref = refs[ident]
        grouped.setdefault(ref.kind, []).append(ref)
    return grouped


def _first(grouped: dict[str, list[InsightRef]], kind: str) -> InsightRef | None:
    """同一 kind 取 id 最小的一条; select() 已按 kind 去重, 这里只兜底手写输入。"""
    items = grouped.get(kind, [])
    return items[0] if items else None


def _primary_source(refs: dict[str, InsightRef]) -> str | None:
    """已选洞察里出现次数最多的源; 平局比该源的最小 id, 再比源名。

    渲染专用序列 (`vol.daily_series`) 不参与计票: 每个源都有一条, 计进去等于
    给每个源加一票。空 `source` 也不投票 —— 手写 payload 可能没有这个键,
    这时不做任何过滤, 保持旧行为。
    """
    votes = Counter(
        ref.source for ref in refs.values() if ref.source and ref.kind not in RENDER_ONLY_KINDS
    )
    if not votes:
        return None
    smallest = {
        source: min(ref.id for ref in refs.values() if ref.source == source) for source in votes
    }
    return min(votes, key=lambda source: (-votes[source], smallest[source], source))


def _split_sources(
    refs: dict[str, InsightRef], primary: str | None
) -> tuple[dict[str, InsightRef], dict[str, InsightRef]]:
    """按主源拆成「可入卡」与「被排除」; 无 source 的条目始终保留。"""
    if primary is None:
        return refs, {}
    kept = {ident: ref for ident, ref in refs.items() if ref.source in ("", primary)}
    dropped = {ident: ref for ident, ref in refs.items() if ref.source and ref.source != primary}
    return kept, dropped


def _mixed_reason(primary: str, dropped: dict[str, InsightRef], card: str) -> str | None:
    """这张卡需要的洞察只存在于别的源时, 说清主源与未入卡的源。"""
    wanted = templates.CARD_SOURCE[card]
    others = sorted({ref.source for ref in dropped.values() if ref.kind == wanted})
    if not others:
        return None
    return MIXED.format(primary=primary, others="/".join(others))


def _pick_daily(items: list[InsightRef]) -> InsightRef | None:
    """多条日序列取 headline 值最大者, 同值按 id 升序。

    不能让「哪个源」取决于字典顺序: 两个数据源都产出日序列时, 选中的那张热图
    会随文件里键的排列顺序变化, 而用户无从解释为什么。
    """
    if not items:
        return None
    return sorted(items, key=lambda ref: (-ref.headline_value, ref.id))[0]


def _meta(payload: dict[str, Any], *, year: int, theme: str, tone: str, locale: str) -> dict:
    """故事元信息; tz 与 build_id 跟着 insights.json 走, 不另起一套口径。"""
    generated = payload.get("generated_from")
    tz = "Asia/Shanghai"
    if isinstance(generated, dict):
        raw_tz = generated.get("tz")
        if isinstance(raw_tz, str) and raw_tz:
            tz = raw_tz
    raw_build = payload.get("build_id")
    return {
        "year": year,
        "locale": locale,
        "theme": theme,
        "tone": tone,
        "tz": tz,
        "build_id": raw_build if isinstance(raw_build, str) else "",
    }


def _card(kind: str, ref: InsightRef, year: int, source: str | None) -> dict[str, Any]:
    """把模板落成一张卡的 JSON; cover 用 evidence 承载数字来源, 其余用 insight。"""
    template = templates.copy(kind, {ref.kind: ref}, year, source=source)
    copy: dict[str, str] = {
        "kicker": template.kicker,
        "headline": template.headline,
    }
    if template.sub is not None:
        copy["sub"] = template.sub
    card: dict[str, Any] = {
        "id": template.card_id,
        "type": template.card_type,
        "copy": copy,
    }
    if kind == "cover":
        card["evidence"] = [ref.id]
    else:
        card["insight"] = ref.id
    return card


def _summary_evidence(cards: dict[str, dict[str, Any]]) -> list[str]:
    """summary-grid 将引用的洞察: 前四类卡用过、且能复算的那些, 去重保序。

    `vol.daily_series` 不进总览: 它的 facts 是「窗口天数」, 放进网格是噪声。
    """
    evidence: list[str] = []
    for kind in ("cover", "big-number", "ranking", "clock"):
        card = cards.get(kind)
        if card is None:
            continue
        ident = card.get("insight")
        if ident is None:
            ids = card.get("evidence", [])
            ident = ids[0] if ids else None
        if isinstance(ident, str) and ident not in evidence:
            evidence.append(ident)
    return evidence


def _summary(evidence: list[str], year: int) -> dict[str, Any]:
    """summary-grid 本身不引单一洞察, 只带 evidence 链。"""
    template = templates.copy("summary", {}, year)
    return {
        "id": template.card_id,
        "type": template.card_type,
        "copy": {"kicker": template.kicker, "headline": template.headline},
        "evidence": evidence,
    }


def plan(
    payload: dict[str, Any],
    *,
    year: int,
    theme: str = "neon",
    tone: str = "deadpan",
    locale: str = "zh-CN",
) -> Plan:
    """按固定顺序规划卡片; 不可得的卡进跳过表, 不静默消失。

    多源时先定主源, 只引用主源的洞察: 不同量纲混进一份故事而不说明, 是产品级
    错误。主源判不出来 (没有 source 键) 时退回旧行为。
    """
    refs = build_refs(payload)
    primary = _primary_source(refs)
    kept, dropped = _split_sources(refs, primary)
    grouped = _group(kept)
    total = _first(grouped, "vol.total")
    if total is None:
        raise RecapError("没有可用的洞察：先跑 recap import，再跑 recap insights")  # noqa: RUF001

    sources = {
        "cover": total,
        "big-number": total,
        "ranking": _first(grouped, "conc.top_entity"),
        "heatmap": _pick_daily(grouped.get("vol.daily_series", [])),
        "clock": _first(grouped, "time.hour_rhythm"),
    }
    reasons = {
        "cover": NO_TOTAL,
        "big-number": NO_TOTAL,
        "ranking": NO_CONC,
        "heatmap": NO_DAILY,
        "clock": NO_HOUR,
    }

    skips: list[Skip] = []
    built: dict[str, dict[str, Any]] = {}
    for kind in templates.CARD_ORDER:
        if kind == "summary":
            continue
        ref = sources[kind]
        if ref is None:
            mixed = _mixed_reason(primary, dropped, kind) if primary is not None else None
            skips.append(Skip(kind, mixed or reasons[kind]))
            continue
        if ref.sensitivity == "high":
            # 自动生成的文案不该替用户做授权决定。
            skips.append(Skip(kind, SENSITIVE))
            continue
        built[kind] = _card(kind, ref, year, primary)

    # summary 放在最后: 它只引用前面真的画出来的卡, 所以必须先知道哪些卡成立了。
    evidence = _summary_evidence(built)
    if len(evidence) < 3:
        skips.append(Skip("summary", SUMMARY_SHORT))
    else:
        built["summary"] = _summary(evidence, year)

    cards = [built[kind] for kind in templates.CARD_ORDER if kind in built]
    if not cards:
        raise RecapError(
            "没有可用的洞察：可用的洞察都是高敏的，自动规划不会替你授权。\n"  # noqa: RUF001
            "手写 story.json 后显式传 --allow-sensitive，或先导入一个非高敏的数据源。"  # noqa: RUF001
        )
    return Plan(
        story={
            "version": 1,
            "meta": _meta(payload, year=year, theme=theme, tone=tone, locale=locale),
            "cards": cards,
        },
        skips=tuple(skips),
    )
