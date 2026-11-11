"""检测器入口: 体量与集中度, 并把时间与断裂类交给 temporal。

门槛见文档 §8.2: 活跃日不足 30 天不出节律与连续类, 事件不足 50 条不出集中度。
"""

import sqlite3

from recapkits.insights import scoring
from recapkits.insights.detectors import temporal
from recapkits.insights.detectors.common import (
    MIN_ACTIVE_DAYS,
    MIN_EVENTS_FOR_CONCENTRATION,
    daily_counts,
    make_insight,
    scope,
    standard_caveats,
)
from recapkits.insights.model import Fact, Insight, Period


def detect(conn: sqlite3.Connection, *, source: str, period: Period) -> list[Insight]:
    """跑全部检测器, 返回该源的候选洞察(未打分)。"""
    daily = daily_counts(conn, source, period)
    if not daily:
        return []

    total_events = sum(count for _, count in daily)
    found = _vol_total(conn, source, period, total_events, len(daily))
    found += _vol_busiest_day(daily, source, period)
    if total_events >= MIN_EVENTS_FOR_CONCENTRATION:
        found += _conc_top_entity(conn, source, period, total_events)
    if len(daily) >= MIN_ACTIVE_DAYS:
        found += temporal.detect(
            conn, source=source, period=period, daily=daily, total_events=total_events
        )
    return found


def _vol_total(
    conn: sqlite3.Connection,
    source: str,
    period: Period,
    total_events: int,
    active_days: int,
) -> list[Insight]:
    """体量: 事件总数、总时长、活跃天数、日均。"""
    sql = "SELECT COUNT(*) AS n, COALESCE(SUM(e.duration_s), 0.0) AS seconds " + scope(
        source, period
    )
    seconds = float(conn.execute(sql).fetchone()["seconds"])
    daily_avg = total_events / active_days if active_days else 0.0

    facts = [
        Fact("events", "事件数", total_events, "count", f"{total_events:,}"),
        Fact("active_days", "活跃天数", active_days, "count", f"{active_days:,}"),
        Fact("daily_avg", "日均事件", round(daily_avg, 2), "count", f"{daily_avg:.1f}"),
    ]
    if seconds > 0:
        hours = round(seconds / 3600.0, 2)
        facts.append(Fact("duration_hours", "总时长", hours, "duration", f"{hours:.1f} 小时"))

    return [
        make_insight(
            ident=f"vol.total:{source}:{period.start[:4]}",
            kind="vol.total",
            source=source,
            period=period,
            headline=Fact("events", "事件总数", total_events, "count", f"{total_events:,}"),
            facts=facts,
            sql=sql,
            rows=1,
            novelty="constant",
            signal=scoring.signal_vol_total(),
            caveats=standard_caveats(period),
        )
    ]


def _vol_busiest_day(daily: list[tuple[str, int]], source: str, period: Period) -> list[Insight]:
    """体量: 单日最大值, 附日期与数值; 并列时取更早的一天。"""
    best_day, best_count = daily[0]
    for day, count in daily[1:]:
        if count > best_count:
            best_day, best_count = day, count

    total_events = sum(count for _, count in daily)
    share = best_count / total_events
    daily_avg = total_events / len(daily)
    sql = (
        "SELECT l.local_date AS d, COUNT(*) AS n "
        + scope(source, period)
        + " GROUP BY l.local_date ORDER BY n DESC, d ASC LIMIT 1"
    )
    return [
        make_insight(
            ident=f"vol.busiest_day:{source}:{period.start[:4]}:{best_day}",
            kind="vol.busiest_day",
            source=source,
            period=period,
            headline=Fact("events", "单日最多事件", best_count, "count", f"{best_count:,}"),
            facts=[
                Fact("date", "日期", best_day, "date", best_day),
                Fact("events", "当日事件数", best_count, "count", f"{best_count:,}"),
                Fact("share", "占全部事件的比重", round(share, 4), "pct", f"{share:.0%}"),
            ],
            sql=sql,
            rows=1,
            novelty="record",
            signal=scoring.signal_busiest_day(best_count, daily_avg),
            caveats=standard_caveats(period, "并列时取更早的一天"),
        )
    ]


def _conc_top_entity(
    conn: sqlite3.Connection,
    source: str,
    period: Period,
    total_events: int,
) -> list[Insight]:
    """集中度: Top-5 实体与占比; headline 是 top1 的占比。"""
    sql = (
        "SELECT COALESCE(NULLIF(e.subtitle, ''), NULLIF(e.title, ''), '(未命名)') AS entity, "
        "COUNT(*) AS n " + scope(source, period) + " GROUP BY entity ORDER BY n DESC, entity ASC"
    )
    rows = conn.execute(sql).fetchall()
    if not rows:
        return []
    top = rows[:5]
    top_share = int(top[0]["n"]) / total_events

    facts = [
        Fact(f"rank_{rank}", str(row["entity"]), int(row["n"]), "count", f"{int(row['n']):,}")
        for rank, row in enumerate(top, start=1)
    ]
    facts.append(Fact("share", "占全部事件的比重", round(top_share, 4), "pct", f"{top_share:.0%}"))

    entity_kind = "repo" if source == "git" else "entity"
    return [
        make_insight(
            ident=f"conc.top_entity:{entity_kind}:{top[0]['entity']}:{period.start[:4]}",
            kind="conc.top_entity",
            source=source,
            period=period,
            headline=facts[-1],
            facts=facts,
            sql=sql,
            rows=len(rows),
            novelty="constant",
            signal=scoring.signal_top_entity(top_share),
            caveats=standard_caveats(
                period,
                "实体口径: 副标题优先, 缺失时退回标题",
                "Top-5 按事件数降序, 同数按名称升序",
            ),
        )
    ]
