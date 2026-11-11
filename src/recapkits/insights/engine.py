"""洞察引擎: 定窗口、跑检测器、打分、按全序取卡。"""

import sqlite3
from dataclasses import replace
from datetime import date

from recapkits.db import list_sources
from recapkits.insights import scoring
from recapkits.insights.detectors import common, generic
from recapkits.insights.model import Insight, Period
from recapkits.tz import utc_now_iso

#: 本期没有上一期数据, 同比类分量一律关闭; 阶段 6 接入上一期后改成 True。
HAS_PREVIOUS = False


def review_window(year: int, today: str | None = None) -> tuple[str, str]:
    """回顾窗口 (start, end); 当年只到今天, 不跨年。"""
    start = f"{year}-01-01"
    return start, min(f"{year}-12-31", today or utc_now_iso()[:10])


def build_period(
    conn: sqlite3.Connection, *, tz: str, year: int, today: str | None = None
) -> Period:
    """构造统计窗口; 当年只到"今天", 未来年份直接报错。"""
    start, end = review_window(year, today)
    if start > end:
        raise ValueError(f"{year} 年尚未开始, 请换一个年份")
    return Period(start=start, end=end, tz=tz, coverage=coverage(conn, tz=tz, start=start, end=end))


def coverage(conn: sqlite3.Connection, *, tz: str, start: str, end: str) -> float:
    """活跃本地日 / 窗口天数, 0..1; 这是"我们有多少天真的看到了数据"。

    导入报告与 `period.coverage` 共用这一个口径, 不再另算"数据跨度"。
    """
    days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    if days <= 0:
        return 0.0
    row = conn.execute(
        "SELECT COUNT(DISTINCT local_date) AS n FROM event_local "
        "WHERE tz = ? AND local_date BETWEEN ? AND ?",
        (tz, start, end),
    ).fetchone()
    return round(int(row["n"]) / days, 4)


def source_stats(conn: sqlite3.Connection, period: Period) -> dict[str, tuple[int, int]]:
    """每个源的 (事件数, 活跃天数); CLI 用它解释数据充足度。"""
    return {
        source: common.period_stats(conn, source, period)
        for source, count in list_sources(conn)
        if count > 0
    }


def run(conn: sqlite3.Connection, *, tz: str, year: int, today: str | None = None) -> list[Insight]:
    """跑所有源的检测器并打分, 返回全部候选(未截断)。"""
    period = build_period(conn, tz=tz, year=year, today=today)
    gated = scoring.gated_components(has_previous=HAS_PREVIOUS)
    candidates: list[Insight] = []
    for source, count in list_sources(conn):
        if count == 0:
            continue
        events, active_days = common.period_stats(conn, source, period)
        level = scoring.sufficiency(events, active_days)
        for insight in generic.detect(conn, source=source, period=period):
            if level == "insufficient" and insight.kind != "vol.total":
                continue
            parts = scoring.score_parts(
                signal=insight.signal,
                novelty=insight.novelty,
                sensitivity=insight.sensitivity,
                gated=gated,
            )
            scored = replace(
                insight,
                score=scoring.total(parts),
                score_parts=parts,
                data_sufficiency=level,
                gated=gated,
            )
            if level == "insufficient":
                note = f"数据量不足（{events} 条事件 / {active_days} 个活跃日），本回顾仅供参考"  # noqa: RUF001
                scored = replace(scored, caveats=[*scored.caveats, note])
            candidates.append(scored)
    return candidates


def select(insights: list[Insight], top: int = 10) -> list[Insight]:
    """按 (score desc, kind, id) 全序排序, 同一 kind 最多取 1 个。"""
    if top < 1:
        raise ValueError("--top 必须大于 0")
    ordered = sorted(insights, key=lambda item: (-item.score, item.kind, item.id))
    picked: list[Insight] = []
    seen_kinds: set[str] = set()
    for insight in ordered:
        if insight.kind in seen_kinds:
            continue
        seen_kinds.add(insight.kind)
        picked.append(insight)
        if len(picked) >= top:
            break
    return picked
