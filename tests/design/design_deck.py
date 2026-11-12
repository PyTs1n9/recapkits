"""设计断言用的六卡语料: 覆盖全部卡型、两种比例与几处边界文本。

刻意不用 `tests/fixtures/` 里的静态 JSON: 设计断言要同时跑到 heatmap 与 clock 的
序列, 而这两条必须覆盖整年, 366 个日期写在测试代码里比写在夹具里更好维护。
"""

from recapkits.insights.model import day_keys

CONC = "conc.top_entity:repo:alpha:2024"
DAILY = "vol.daily_series:git:2024"
HOUR = "time.hour_rhythm:git:2024"
TOTAL = "vol.total:git:2024"
STREAK = "disc.longest_streak:git:2024:2024-05-01"
GAP = "disc.longest_gap:git:2024:2024-03-10"


def _fact(key: str, label: str, value, unit, display: str) -> dict:
    return {"key": key, "label": label, "value": value, "unit": unit, "display": display}


def _insight(ident: str, kind: str, headline: dict, facts: list[dict], series: dict | None = None):
    payload = {
        "id": ident,
        "kind": kind,
        "source": "git",
        "period": {
            "start": "2024-01-01",
            "end": "2024-12-31",
            "tz": "Asia/Shanghai",
            "coverage": 0.51,
        },
        "headline_fact": headline,
        "facts": facts,
        "evidence_sql": "SELECT 1",
        "evidence_rows": 1,
        "score": 0.5,
        "score_parts": {"signal": 0.5, "deviation": 0.0, "discontinuity": 0.0, "sensitivity": 0.0},
        "novelty": "constant",
        "sensitivity": "low",
        "data_sufficiency": "ok",
        "gated": ["deviation", "discontinuity"],
        "caveats": [],
    }
    if series is not None:
        payload["series"] = series
    return payload


def _daily_series() -> dict:
    keys = day_keys("2024-01-01", "2024-12-31")
    values = [0.0] * len(keys)
    for offset in range(70, 120):
        values[offset] = float(2 + offset % 5)
    return {"axis": "day", "keys": list(keys), "values": values, "unit": "count"}


def _hour_series() -> dict:
    values = [0.004 + (hour % 7) * 0.002 for hour in range(24)]
    total = sum(values)
    return {
        "axis": "hour",
        "keys": [str(hour) for hour in range(24)],
        "values": [value / total for value in values],
        "unit": "share",
    }


def insights_payload() -> dict:
    """六张卡要用到的全部洞察。"""
    return {
        "version": 1,
        "build_id": "b3:design",
        "generated_from": {"sources": ["git"], "event_count": 220, "tz": "Asia/Shanghai"},
        "insights": [
            _insight(
                TOTAL,
                "vol.total",
                _fact("events", "事件总数", 220, "count", "220"),
                [
                    _fact("active_days", "活跃天数", 96, "count", "96"),
                    _fact("daily_avg", "日均事件", 2.29, "count", "2.3"),
                ],
            ),
            _insight(
                CONC,
                "conc.top_entity",
                _fact("share", "占全部事件的比重", 0.62, "pct", "62%"),
                [
                    _fact("rank_1", "一个特别特别长的仓库名字", 137, "count", "137"),
                    _fact("rank_2", "beta", 21, "count", "21"),
                    _fact("rank_3", "delta", 21, "count", "21"),
                    _fact("rank_4", "gamma", 21, "count", "21"),
                    _fact("rank_5", "epsilon", 21, "count", "21"),
                    _fact("share", "占全部事件的比重", 0.62, "pct", "62%"),
                ],
            ),
            _insight(
                DAILY,
                "vol.daily_series",
                _fact("events", "窗口内事件数", 380, "count", "380"),
                [_fact("days", "窗口天数", 366, "count", "366")],
                _daily_series(),
            ),
            _insight(
                HOUR,
                "time.hour_rhythm",
                _fact("late_night_share", "深夜占比 22:00-03:00", 0.38, "pct", "38%"),
                [
                    *[_fact(f"h{hour:02d}", f"{hour} 点", 9, "count", "9") for hour in range(24)],
                    _fact("peak_hour", "最活跃小时", "2 点", None, "2 点"),
                ],
                _hour_series(),
            ),
            _insight(
                STREAK,
                "disc.longest_streak",
                _fact("days", "最长连续活跃天数", 21, "count", "21 天"),
                [
                    _fact("days", "连续天数", 21, "count", "21 天"),
                    _fact("start", "起始日", "2024-05-01", "date", "2024-05-01"),
                    _fact("end", "结束日", "2024-05-21", "date", "2024-05-21"),
                ],
            ),
            _insight(
                GAP,
                "disc.longest_gap",
                _fact("days", "最长空档天数", 7, "count", "7 天"),
                [
                    _fact("days", "空档天数", 7, "count", "7 天"),
                    _fact("start", "起始日", "2024-03-10", "date", "2024-03-10"),
                    _fact("end", "结束日", "2024-03-16", "date", "2024-03-16"),
                ],
            ),
        ],
    }


def story() -> dict:
    """六张卡, 每张都带 kicker/标题/副标题, 让骨架对齐也在断言范围内。"""
    return {
        "version": 1,
        "meta": {
            "year": 2024,
            "locale": "zh-CN",
            "theme": "neon",
            "tone": "deadpan",
            "tz": "Asia/Shanghai",
            "build_id": "b3:design",
        },
        "cards": [
            {
                "id": "cover",
                "type": "cover",
                "copy": {
                    "headline": "2024",
                    "kicker": "本地生成 · 未上传",
                    "sub": "一整年的提交记录",
                },
            },
            {
                "id": "total",
                "type": "big-number",
                "insight": TOTAL,
                "copy": {
                    "kicker": "全年",
                    "headline": "提交总数",
                    "sub": "覆盖 {{vol.total:git:2024.active_days}} 个活跃日",
                },
            },
            {
                "id": "ranking",
                "type": "ranking",
                "insight": CONC,
                "copy": {
                    "kicker": "年度执念",
                    "headline": "提交集中度",
                    "sub": "{{conc.top_entity:repo:alpha:2024.share}} 的提交都指向这个仓库",
                },
            },
            {
                "id": "heatmap",
                "type": "heatmap",
                "insight": DAILY,
                "copy": {
                    "kicker": "全年节奏",
                    "headline": "什么时候在写",
                    "sub": "格子按日排布；空白表示尚未发生",  # noqa: RUF001
                },
            },
            {
                "id": "clock",
                "type": "clock",
                "insight": HOUR,
                "copy": {
                    "kicker": "生物钟",
                    "headline": "作息的形状",
                    "sub": "深夜的提交比白天更密",
                },
            },
            {
                "id": "summary",
                "type": "summary-grid",
                "insight": TOTAL,
                "copy": {"kicker": "总览", "headline": "全年总览"},
                "evidence": [HOUR, STREAK, GAP, CONC],
            },
        ],
    }
