"""检测器共用的 SQL 片段、阈值与构造器。

每条 SQL 都限定在 (source, tz, local_date 区间) 内, 并且同时充当 evidence_sql:
测试会把它原样交给 sqlite3 执行, 所以它必须自包含, 不能带占位符。
"""

import sqlite3

from recapkits.insights.model import Fact, Insight, Period

#: 低于这些门槛就不出对应类别的洞察, 宁缺不凑。
MIN_EVENTS_FOR_CONCENTRATION = 50
MIN_ACTIVE_DAYS = 30


def lit(value: str) -> str:
    """把字符串写成 SQL 字面量; 只用于受控值(源名、时区名、日期)。"""
    return "'" + value.replace("'", "''") + "'"


def scope(source: str, period: Period) -> str:
    """三个条件的公共片段: 源、时区、本地日期闭区间。"""
    return (
        "FROM events e JOIN event_local l ON l.event_id = e.id "
        f"WHERE e.source = {lit(source)} AND l.tz = {lit(period.tz)} "
        f"AND l.local_date BETWEEN {lit(period.start)} AND {lit(period.end)}"
    )


def standard_caveats(period: Period, *extra: str) -> list[str]:
    """每条洞察都带窗口与覆盖率, 免得读者把"没数据"当成"没发生"。"""
    head = f"窗口 {period.start} 至 {period.end}, 覆盖率 {period.coverage:.0%}"
    return [head, *extra]


def daily_counts(conn: sqlite3.Connection, source: str, period: Period) -> list[tuple[str, int]]:
    """每个活跃本地日的事件数, 按日期升序。"""
    sql = (
        "SELECT l.local_date AS d, COUNT(*) AS n "
        + scope(source, period)
        + " GROUP BY l.local_date ORDER BY l.local_date"
    )
    return [(str(row["d"]), int(row["n"])) for row in conn.execute(sql)]


def make_insight(
    *,
    ident: str,
    kind: str,
    source: str,
    period: Period,
    headline: Fact,
    facts: list[Fact],
    sql: str,
    rows: int,
    novelty: str,
    signal: float,
    caveats: list[str],
) -> Insight:
    """组装一条未打分的洞察; `signal` 必填, 分数由 scoring 统一填充。"""
    return Insight(
        id=ident,
        kind=kind,
        source=source,
        period=period,
        headline_fact=headline,
        facts=facts,
        evidence_sql=sql,
        evidence_rows=rows,
        signal=signal,
        score=0.0,
        score_parts={},
        novelty=novelty,
        sensitivity="low",
        data_sufficiency="ok",
        gated=[],
        caveats=caveats,
    )


def period_stats(conn: sqlite3.Connection, source: str, period: Period) -> tuple[int, int]:
    """(事件数, 活跃天数); 数据充足度与闸门都吃这两个数。"""
    sql = "SELECT COUNT(*) AS n, COUNT(DISTINCT l.local_date) AS d " + scope(source, period)
    row = conn.execute(sql).fetchone()
    return int(row["n"]), int(row["d"])
