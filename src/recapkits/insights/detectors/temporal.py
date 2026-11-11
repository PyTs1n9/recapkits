"""时间与断裂类检测器: 24 小时、星期、连续、空档。

全部基于 event_local, 所以分布反映的是"当时的本地时间", 不是 UTC。
四条都要求活跃日 >= 30, 门槛由调用方把关。
"""

import sqlite3
from datetime import date, timedelta

from recapkits.insights import scoring
from recapkits.insights.detectors.common import make_insight, scope, standard_caveats
from recapkits.insights.model import Fact, Insight, Period

LATE_NIGHT_HOURS = frozenset({22, 23, 0, 1, 2, 3})
WEEKDAY_LABELS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def detect(
    conn: sqlite3.Connection,
    *,
    source: str,
    period: Period,
    daily: list[tuple[str, int]],
    total_events: int,
) -> list[Insight]:
    """返回时间与断裂类的全部候选。"""
    return [
        *_hour_rhythm(conn, source, period, total_events),
        *_weekday_rhythm(conn, source, period),
        *_longest_streak(daily, source, period),
        *_longest_gap(daily, source, period),
    ]


def _hour_rhythm(
    conn: sqlite3.Connection, source: str, period: Period, total_events: int
) -> list[Insight]:
    """24 小时分布与深夜占比(22:00 至 03:00)。"""
    sql = (
        "SELECT l.local_hour AS h, COUNT(*) AS n "
        + scope(source, period)
        + " GROUP BY l.local_hour ORDER BY l.local_hour"
    )
    rows = conn.execute(sql).fetchall()
    counts = [0] * 24
    for row in rows:
        counts[int(row["h"])] = int(row["n"])

    late = sum(counts[hour] for hour in LATE_NIGHT_HOURS)
    late_share = late / total_events
    peak_hour = counts.index(max(counts))

    facts = [
        Fact(f"h{hour:02d}", f"{hour} 点", counts[hour], "count", f"{counts[hour]:,}")
        for hour in range(24)
    ]
    facts.append(
        Fact(
            "late_night_share",
            "深夜占比 22:00-03:00",
            round(late_share, 4),
            "pct",
            f"{late_share:.0%}",
        )
    )
    facts.append(Fact("peak_hour", "最活跃小时", f"{peak_hour} 点", None, f"{peak_hour} 点"))

    return [
        make_insight(
            ident=f"time.hour_rhythm:{source}:{period.start[:4]}",
            kind="time.hour_rhythm",
            source=source,
            period=period,
            headline=facts[-2],
            facts=facts,
            sql=sql,
            rows=len(rows),
            novelty="constant",
            signal=scoring.signal_hour_rhythm(late_share),
            caveats=standard_caveats(period, "本地小时由 tz.py 从 UTC 换算, 源带偏移时优先用偏移"),
        )
    ]


def _weekday_rhythm(conn: sqlite3.Connection, source: str, period: Period) -> list[Insight]:
    """7 天分布与最活跃星期, 周一起算。"""
    sql = (
        "SELECT CAST(strftime('%w', l.local_date) AS INTEGER) AS wd, COUNT(*) AS n "
        + scope(source, period)
        + " GROUP BY wd ORDER BY wd"
    )
    rows = conn.execute(sql).fetchall()
    counts = [0] * 7
    for row in rows:
        counts[(int(row["wd"]) + 6) % 7] = int(row["n"])

    busiest = counts.index(max(counts))
    total = sum(counts)
    busiest_share = counts[busiest] / total
    facts = [
        Fact(f"wd_{index + 1}", WEEKDAY_LABELS[index], counts[index], "count", f"{counts[index]:,}")
        for index in range(7)
    ]
    facts.append(
        Fact(
            "busiest_share",
            "最活跃星期的比重",
            round(busiest_share, 4),
            "pct",
            f"{busiest_share:.0%}",
        )
    )

    return [
        make_insight(
            ident=f"time.weekday_rhythm:{source}:{period.start[:4]}",
            kind="time.weekday_rhythm",
            source=source,
            period=period,
            headline=Fact(
                "busiest_weekday",
                "最活跃的星期",
                WEEKDAY_LABELS[busiest],
                None,
                WEEKDAY_LABELS[busiest],
            ),
            facts=facts,
            sql=sql,
            rows=len(rows),
            novelty="constant",
            signal=scoring.signal_weekday_rhythm(busiest_share),
            caveats=standard_caveats(period, "星期由本地日期推出, 周一起算"),
        )
    ]


def _longest_streak(daily: list[tuple[str, int]], source: str, period: Period) -> list[Insight]:
    """最长连续活跃天数。"""
    best = (1, daily[0][0], daily[0][0])
    run_start = daily[0][0]
    run_len = 1
    for index in range(1, len(daily)):
        previous = date.fromisoformat(daily[index - 1][0])
        current = date.fromisoformat(daily[index][0])
        if (current - previous).days == 1:
            run_len += 1
        else:
            run_start, run_len = daily[index][0], 1
        if run_len > best[0]:
            best = (run_len, run_start, daily[index][0])

    sql = (
        "SELECT l.local_date AS d, COUNT(*) AS n "
        + scope(source, period)
        + " GROUP BY l.local_date ORDER BY l.local_date"
    )
    return [
        make_insight(
            ident=f"disc.longest_streak:{source}:{period.start[:4]}:{best[1]}",
            kind="disc.longest_streak",
            source=source,
            period=period,
            headline=Fact("days", "最长连续活跃天数", best[0], "count", f"{best[0]} 天"),
            facts=[
                Fact("days", "连续天数", best[0], "count", f"{best[0]} 天"),
                Fact("start", "起始日", best[1], "date", best[1]),
                Fact("end", "结束日", best[2], "date", best[2]),
            ],
            sql=sql,
            rows=len(daily),
            novelty="record",
            signal=scoring.signal_streak(best[0]),
            caveats=standard_caveats(period, "按本地日期去重后计算, 同日多次事件只算一天"),
        )
    ]


def _longest_gap(daily: list[tuple[str, int]], source: str, period: Period) -> list[Insight]:
    """最长空档天数与起止; "没有发生"是一等公民。"""
    if len(daily) < 2:
        return []
    best_days = 0
    best_after = daily[0][0]
    for index in range(1, len(daily)):
        previous = date.fromisoformat(daily[index - 1][0])
        current = date.fromisoformat(daily[index][0])
        gap = (current - previous).days - 1
        if gap > best_days:
            best_days, best_after = gap, daily[index - 1][0]
    if best_days <= 0:
        return []

    gap_start = date.fromisoformat(best_after) + timedelta(days=1)
    gap_end = gap_start + timedelta(days=best_days - 1)
    sql = (
        "SELECT l.local_date AS d, COUNT(*) AS n "
        + scope(source, period)
        + " GROUP BY l.local_date ORDER BY l.local_date"
    )
    return [
        make_insight(
            ident=f"disc.longest_gap:{source}:{period.start[:4]}:{gap_start.isoformat()}",
            kind="disc.longest_gap",
            source=source,
            period=period,
            headline=Fact("days", "最长空档天数", best_days, "count", f"{best_days} 天"),
            facts=[
                Fact("days", "空档天数", best_days, "count", f"{best_days} 天"),
                Fact("start", "起始日", gap_start.isoformat(), "date", gap_start.isoformat()),
                Fact("end", "结束日", gap_end.isoformat(), "date", gap_end.isoformat()),
            ],
            sql=sql,
            rows=len(daily),
            novelty="absence",
            signal=scoring.signal_gap(best_days),
            caveats=standard_caveats(period, "只统计窗口内部的空档, 不含窗口两端"),
        )
    ]
