# 0001 — 四个契约（冻结）

- 状态：**已冻结**（2026-11-11）
- 变更策略：**不新增表、字段、JSON key**。任何扩展先讨论，不得由实现侧自行决定。

本文件是四个契约的唯一事实源。以下内容在 `PROMPT-起步.md` §5 中定义为「照抄，不是参考」，因此**逐字抄录，不做改写、不在示例上增删字段**。

---

## 1. SQLite

```sql
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS raw_row (
  adapter   TEXT NOT NULL,
  src_file  TEXT NOT NULL,
  src_line  INTEGER NOT NULL,
  payload   TEXT NOT NULL,
  PRIMARY KEY (adapter, src_file, src_line)
);

CREATE TABLE IF NOT EXISTS events (
  id            INTEGER PRIMARY KEY,
  source        TEXT NOT NULL,
  kind          TEXT NOT NULL,
  ts_utc        TEXT NOT NULL,          -- ISO 8601，始终以 Z 结尾
  tz_offset_min INTEGER,                -- 仅当源自带偏移时非空
  title         TEXT,
  subtitle      TEXT,
  category      TEXT,
  duration_s    REAL,
  value         REAL,
  sensitivity   TEXT NOT NULL DEFAULT 'low',   -- low | medium | high
  flags         TEXT,                   -- JSON 对象字符串
  meta_json     TEXT,
  row_hash      TEXT NOT NULL           -- 幂等键，sha256 前 16 位
);
CREATE INDEX IF NOT EXISTS idx_ev_src_ts  ON events(source, ts_utc);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ev_rowhash ON events(row_hash);

CREATE TABLE IF NOT EXISTS event_local (
  event_id   INTEGER NOT NULL,
  tz         TEXT NOT NULL,
  local_date TEXT NOT NULL,             -- YYYY-MM-DD
  local_hour INTEGER NOT NULL,          -- 0..23
  PRIMARY KEY (event_id, tz)
);
CREATE INDEX IF NOT EXISTS idx_local_date ON event_local(tz, local_date, local_hour);

CREATE TABLE IF NOT EXISTS import_reports (
  id         INTEGER PRIMARY KEY,
  source     TEXT NOT NULL,
  src_hash   TEXT NOT NULL,
  rows       INTEGER NOT NULL,
  skipped    INTEGER NOT NULL,
  warnings   TEXT,
  coverage   REAL,                      -- 0..1，实际覆盖天数 / 应有天数
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS build (
  build_id TEXT PRIMARY KEY,
  options  TEXT NOT NULL,
  manifest TEXT NOT NULL                -- 只存哈希，永不存绝对路径
);
```

**`build.manifest` 只允许存哈希与计数，不得存任何绝对路径**（路径里可能含真实姓名）。

---

## 2. `insights.json`

```json
{
  "version": 1,
  "build_id": "b3:0000",
  "generated_from": { "sources": ["git"], "event_count": 1102, "tz": "Asia/Shanghai" },
  "insights": [
    {
      "id": "conc.top_entity:repo:recapkits:2026",
      "kind": "conc.top_entity",
      "source": "git",
      "period": { "start": "2026-01-01", "end": "2026-11-11", "tz": "Asia/Shanghai", "coverage": 0.86 },
      "headline_fact": {
        "key": "share", "label": "占全部提交的比重",
        "value": 0.31, "unit": "pct", "display": "31%"
      },
      "facts": [ { "key": "commits", "label": "提交数", "value": 412, "unit": "count", "display": "412" } ],
      "evidence_sql": "SELECT ...",
      "evidence_rows": 18344,
      "score": 1.42,
      "score_parts": { "deviation": 0.0, "rarity": 0.0, "discontinuity": 0.5, "concentration": 0.4, "obviousness": -0.45, "sensitivity": 0.0 },
      "novelty": "record",
      "sensitivity": "low",
      "caveats": ["仅统计作者日期在 2026 年内的非合并提交"]
    }
  ]
}
```

`display` 是**唯一允许被文案引用的形态**。`evidence_sql` 必须能直接执行并被测试验证。

---

## 3. `story.json`（本期只定义，不实现校验器）

```json
{
  "version": 1,
  "meta": { "year": 2026, "locale": "zh-CN", "theme": "neon", "tone": "deadpan",
            "tz": "Asia/Shanghai", "build_id": "b3:0000" },
  "cards": [
    { "id": "c1", "type": "cover",
      "copy": { "headline": "2026", "kicker": "本地生成 · 未上传" } },
    { "id": "c2", "type": "big-number", "insight": "vol.total_hours",
      "copy": { "headline": "{{vol.total_hours.hours}} 小时",
                "sub": "相当于 {{vol.total_hours.days}} 天。" },
      "evidence": ["vol.total_hours"] }
  ]
}
```

卡片类型限定为：`cover`、`big-number`、`ranking`、`heatmap`、`clock`、`summary-grid`。

---

## 4. 插件 manifest

```json
{
  "id": "recapkits-adapter-git",
  "type": "adapter",
  "version": "0.0.1",
  "engine": ">=0.0.1 <1",
  "entry": { "python": "recapkits.adapters.git_local:GitAdapter" },
  "capabilities": ["read:files", "exec:git"],
  "fixtures": [],
  "license": "MIT"
}
```

---

## 5. 三条硬规则（与契约直接相关）

1. **核心不发起任何网络请求。** 不引入 `requests`/`httpx`，不使用 `urllib.request`；`src/` 下不得出现 `http://` 或 `https://` 字面量（注释里的文档链接除外）。CI 用 grep 检查。
2. **不调用任何 LLM。** 项目里不出现 `openai`、`anthropic`、`ollama` 之类。
3. **本地时间只能经 `tz.py`。** 任何业务代码和 SQL 里不得出现 `datetime.now()`、`.astimezone()`、`strftime('%H')`、`CURRENT_TIMESTAMP`。CI 用 grep 检查。

## 6. 另外三条（同样不可协商）

4. **运行时零第三方依赖。** 只用标准库。开发依赖只允许 `ruff`、`pyright`、`pytest`、`hypothesis`。
5. **适配器必须容错且幂等。** 未知字段 → 警告并继续；必需字段缺失 → 失败并指名文件与列；同一文件导入两次，计数不变。
6. **契约冻结。** 见本文件开头。
