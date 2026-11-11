# 起步任务：recapkits 脚手架 + 第一段端到端

你是这个项目的实现者。下面是一次完整的工作交接，包含全部必要上下文——**你不需要读其他文档，也不要为了找背景而推迟动手。**

---

## 0. 项目是什么

`recapkits` 是一个本地优先、插件化的「任意数据的年度回顾」引擎。用户把数据导出（Spotify、Netflix、git 仓库……）丢进来，在本机生成一份可分享的竖向故事卡片（HTML / PNG / MP4）。

三条产品事实决定了所有实现选择：

1. **全程在本机完成。** 不上传、不遥测、不登录。
2. **数字来自 SQL，文字来自 agent。** 统计一律由确定性代码算，模型只负责选和写，且**只能通过占位符引用数字**。
3. **没有 LLM 也能用。** 确定性模式必须能独立产出完整故事。

同目录下有 `recapkits-开发计划.md`，是完整设计文档。**只在需要解释"为什么"时查阅，不要通读。**

---

## 1. 本次任务范围：只做这三个阶段

按顺序做。每阶段完成后自检，通过再进下一阶段，每阶段结束提交一次 commit。

### 阶段 1 — 脚手架与契约（目标：半天）

| 产出 | 要求 |
|---|---|
| `pyproject.toml` | 见 §4.1，原样使用 |
| `LICENSE` | MIT，版权行 `Copyright (c) 2026 <作者>` |
| `.gitignore` | Python + Node + macOS/Windows + `.recapkits/` |
| `.github/workflows/ci.yml` | ubuntu/macos/windows × Python 3.11/3.12/3.13；步骤：`uv sync` → `ruff check .` → `ruff format --check .` → `pyright` → `pytest -q` |
| 目录结构 | 见 §3，照此创建 |
| `docs/decisions/0001-contracts.md` | 把 §5 的四个契约**原样抄入**，再加三条硬规则（§2） |
| `README.md` | 三行 quickstart + 隐私声明 + 非目标。从 §2 和 §0 提炼，不要写长 |

### 阶段 2 — 时间与数据地基（目标：1 天）

- `src/recapkits/tz.py` —— 严格按 §6 的语义实现。这是全项目最容易写错的文件。
- `src/recapkits/db.py` —— §5.1 的 DDL、连接管理、建表、幂等插入 helper。
- `tests/unit/test_tz.py` —— 覆盖 §6.4 的六个场景 + hypothesis 属性测试。
- `tests/unit/test_db.py` —— 同一批事件插两次，计数不变。

### 阶段 3 — 第一个适配器与 CLI（目标：1.5 天）

- `src/recapkits/adapters/base.py` —— `Adapter` Protocol + `IngestReport` 数据类。
- `src/recapkits/adapters/git_local.py` —— 按 §7 实现。
- `src/recapkits/insights/engine.py`、`scoring.py`、`detectors/generic.py` —— 7 个检测器 + 打分，按 §8。
- `src/recapkits/emit.py` —— 输出 `insights.json`（§5.2 的字段）。
- `src/recapkits/cli.py` —— `init` / `import` / `insights` / `doctor` 四个子命令，用 argparse，**不要引入 click/typer**。
- `tests/golden/test_insights_git.py` —— 用一个在测试里临时构造的 git 仓库跑通，断言 `insights.json` 快照。

### 本次明确不做（不要提前实现，也不要"顺手加上"）

- 渲染器、卡片、主题、HTML / PNG / MP4
- `story.json` 的校验器（**只定义 schema，不实现**）
- spotify / netflix / csv_generic / apple_health / google_takeout 适配器
- agent skill、redact 模式、`--auto` 规划器
- 任何 Web UI、任何 TUI

做完阶段 3 就停下汇报，等下一步指令。

---

## 2. 六条不可协商（违反任何一条 = 实现错误）

1. **核心不发起任何网络请求。** 不引入 `requests`/`httpx`，不使用 `urllib.request`。CI 里加一条 grep 检查：`src/` 下不得出现 `http://` 或 `https://` 字面量（注释里的文档链接除外）。
2. **运行时零第三方依赖。** 只用标准库。开发依赖只允许 `ruff`、`pyright`、`pytest`、`hypothesis`。想加别的先问。
3. **不调用任何 LLM。** 项目里不出现 `openai`、`anthropic`、`ollama` 之类。
4. **本地时间只能经 `tz.py`。** 任何业务代码和 SQL 里不得出现 `datetime.now()`、`.astimezone()`、`strftime('%H')`、`CURRENT_TIMESTAMP`。grep 应能证明这一点。
5. **适配器必须容错且幂等。** 未知字段 → 警告并继续；必需字段缺失 → 失败并**指名文件与列**；同一文件导入两次，计数不变。
6. **契约冻结。** 不新增表、字段、JSON key，除非先问我。§5 是照抄的，不是参考的。

---

## 3. 目录结构

```
recapkits/
├── pyproject.toml
├── LICENSE
├── README.md
├── .gitignore
├── .github/workflows/ci.yml
├── docs/
│   └── decisions/0001-contracts.md
├── src/recapkits/
│   ├── __init__.py          # 只放 __version__
│   ├── cli.py
│   ├── db.py
│   ├── tz.py
│   ├── emit.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── git_local.py
│   └── insights/
│       ├── __init__.py
│       ├── engine.py
│       ├── scoring.py
│       └── detectors/
│           ├── __init__.py
│           └── generic.py
└── tests/
    ├── conftest.py
    ├── unit/{test_tz.py, test_db.py}
    ├── golden/test_insights_git.py
    └── fixtures/README.md    # 说明：只放合成数据，永不提交真实导出
```

---

## 4. 工程约定

### 4.1 `pyproject.toml`

```toml
[project]
name = "recapkits"
version = "0.0.1"
description = "Local-first, plugin-based year-in-review engine for any data export"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
recap = "recapkits.cli:main"

[dependency-groups]
dev = ["ruff", "pyright", "pytest", "hypothesis"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/recapkits"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.pyright]
include = ["src"]
typeCheckingMode = "basic"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

### 4.2 代码风格

- 全部函数带类型标注；`from __future__ import annotations` 不必要（3.11 够用）。
- 不用 dataclass 之外的容器抽象；**没有第二个实现就不要抽接口**。
- 单文件不超过 250 行。
- 每个公开函数一行 docstring 说明语义与单位，不要写段落。
- 注释语言：中文或英文择一，全项目一致。

### 4.3 提交粒度

每阶段结束提交一次，message 用 Conventional Commits：`feat(bootstrap): ...` / `feat(engine): ...`。

---

## 5. 四个契约（照抄，不要改字段名）

### 5.1 SQLite

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

### 5.2 `insights.json`

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

### 5.3 `story.json`（本次只定义，不实现校验器）

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

### 5.4 插件 manifest

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

## 6. `tz.py` 的语义（全项目最容易写错的地方）

### 6.1 两个时间来源

- 数据库只存 `ts_utc`（ISO 8601，`Z` 结尾）。
- `tz_offset_min` **仅当数据源本身带偏移时才写入**（例如 git 提交的 `+08:00`、Apple Health 的 `+0900`）。Spotify / Netflix 的导出只给 UTC，该字段为 `NULL`。

### 6.2 解析顺序

```python
def resolve_local(ts_utc: str, tz_offset_min: int | None, tz_name: str) -> tuple[str, int]:
    """返回 (local_date 'YYYY-MM-DD', local_hour 0-23)。

    1) tz_offset_min 不为 None：用它（源自带偏移最可信）
    2) 否则：用 zoneinfo.ZoneInfo(tz_name) 从 UTC 转本地
    绝不读系统时区，绝不调用 datetime.now()。
    """
```

**UTC → 本地这个方向永远不会产生歧义时刻**，所以不需要处理 ambiguous / nonexistent 时间。不要为此增加 `AmbiguousLocalTime` 之类的东西。

### 6.3 派生表

`event_local` 由 `rebuild_local(tz_name)` 全量重建：先 `DELETE FROM event_local WHERE tz = ?`，再批量插入。切换时区只需重建这一层，几秒完成。用 `executemany` 分批（每批 5000 行）。

### 6.4 必须通过的测试

| # | 场景 | 断言 |
|---|---|---|
| 1 | 春季前进日 `America/New_York`，`2026-03-08T06:59:00Z` / `07:00:00Z` | local_hour 分别是 1 和 3（跳过 2 点） |
| 2 | 秋季回退日 `America/New_York`，`2026-11-01T05:30:00Z` / `06:30:00Z` | 两次的 local_hour 都是 1 |
| 3 | 闰年 `2028-02-29T12:00:00Z` | local_date 为 `2028-02-29` |
| 4 | 午夜边界 `2026-03-11T15:59:00Z` / `16:00:00Z`（`Asia/Shanghai`） | local_date 分别是 `03-11` 和 `03-12`，hour 23 / 0 |
| 5 | 源带偏移优先 | `tz_offset_min=540`、配置 `UTC` 时，仍得到 `+09:00` 的本地时间 |
| 6 | 跨年 `2026-12-31T16:30:00Z`（`Asia/Shanghai`） | local_date 为 `2027-01-01`，hour 为 0 |

属性测试（hypothesis）：随机 UTC 时刻 + 从固定六个时区里随机选一个，断言 `local → 重新构造 UTC == 原值`；`local_hour` 恒在 `0..23`；`local_date` 恒可被 `date.fromisoformat` 解析。

---

## 7. `git_local.py` 的具体要求

**检测**：给一个目录，向下最多 3 层找含 `.git` 的目录，跳过 `node_modules`、`.venv`、`venv`、`dist`、`build`、`.recapkits`。返回 0..1 置信度。

**解析**：对每个仓库执行

```
git -C <repo> log --no-merges --pretty=format:%H%x1f%aI%x1f%cI%x1f%s
```

- `subprocess.run(..., capture_output=True, text=True, encoding="utf-8", errors="replace")`，超时 120 秒。
- 行内以 `\x1f` 分隔；`%aI` 形如 `2026-03-11T23:41:07+08:00`。
- 一个 commit → 一条 event：`source="git"`、`kind="commit"`、`ts_utc` 由 `%aI` 转 UTC、`tz_offset_min` 取 `%aI` 的偏移、`title=subject`、`subtitle=仓库目录名`、`duration_s=NULL`、`value=1.0`。
- `row_hash = sha256(f"{source}|{ts_utc}|{commit_hash}")[:16]`。
- 遇到 git 不存在、非仓库、权限错误：记 `IngestReport.warnings`，继续下一个仓库，**不要抛异常中断整次导入**。

**导入报告**：仓库数、提交数、跳过数（合并提交）、时间范围、覆盖率、警告列表。

**先写测试再造数据**：在 `tests/golden/` 里用 `tmp_path` 建一个 3 次提交的仓库（设置固定的 `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE` 环境变量），断言解析结果确定。

---

## 8. 洞察引擎的具体要求

### 8.1 数据结构

```python
@dataclass(frozen=True)
class Fact:
    key: str
    label: str
    value: float | str
    unit: str | None      # count | pct | duration | rank | date | None
    display: str

@dataclass(frozen=True)
class Insight:
    id: str
    kind: str
    source: str
    period: Period
    headline_fact: Fact
    facts: list[Fact]
    evidence_sql: str
    evidence_rows: int
    score: float
    score_parts: dict[str, float]
    novelty: str          # record | rare | shift | constant | absence
    sensitivity: str      # low | medium | high
    caveats: list[str]
```

### 8.2 本次实现 7 个检测器

| kind | 含义 | 关键约束 |
|---|---|---|
| `vol.total` | 总事件数 / 总时长 | 同时给出日均 |
| `vol.busiest_day` | 单日最大值 | 附该日日期与数值 |
| `conc.top_entity` | Top-5 实体及占比 | `headline_fact` 是 top1 的占比 |
| `time.hour_rhythm` | 24 小时分布 + 深夜占比（22:00–03:00） | 必须走 `event_local` |
| `time.weekday_rhythm` | 7 天分布 + 最活跃星期 | 必须走 `event_local` |
| `disc.longest_streak` | 连续活跃天数 | 用 `local_date` 去重后算 |
| `disc.longest_gap` | 最长空档天数与起止 | `novelty = "absence"` |

**样本门槛**：活跃日 < 30 时，`time.*` 与 `disc.*` 一律返回空列表；事件数 < 50 时 `conc.top_entity` 返回空。宁缺不凑。

**同比不做。** 本次没有上一期数据，任何跨期比较必须留到以后，且必须同窗口截断。

### 8.3 打分（确定性，无随机，无学习权重）

```
score = 1.00*deviation + 0.60*rarity + 0.50*discontinuity + 0.40*concentration
        − 0.45*obviousness − 1.00*sensitivity

deviation     = clamp(|robust_z| / 3, 0, 1)；无上一期数据时为 0.0
rarity        = 0.0（静态先验表尚未实现，接口留出）
discontinuity = 1.0 if novelty in {record, absence} else 0.5 if novelty == "shift" else 0.0
concentration = clamp(top1_share * 2, 0, 1)
obviousness   = 1.0 if kind in {vol.total, conc.top_entity} else 0.0
sensitivity   = 1.0 if sensitivity == "high" else 0.0
```

每个分量都必须写进 `score_parts`，`--explain` 逐项打印。**排序必须是全序**：`(score desc, kind, id)`，否则快照测试会随机失败。

### 8.4 选卡

本次只做最简版：按 score 降序，**同一 kind 最多取 1 个**，取满 `--top N`（默认 10）。多样性惩罚（MMR）留到以后。

---

## 9. CLI 的具体要求

```
recap init [--tz Asia/Shanghai] [--year 2026]
recap import <path> [--source auto|git] [--since DATE] [--until DATE]
recap insights [--json] [--top N] [--explain]
recap doctor
```

- `init`：在当前目录建 `.recapkits/`，写 `config.json`（含 tz、year、created_at），并往 `.gitignore` 追加 `.recapkits/`。工作区已存在时不覆盖，只提示。
- `import`：检测适配器 → 入库 → 打印报告（源、行数、跳过、覆盖率、警告）。退出码 0 表示至少成功导入一个源。
- `insights`：默认人类可读（每行一个分数 + 一句事实），`--json` 输出完整 §5.2 结构，`--explain` 追加 score_parts。
- `doctor`：打印 Python 版本、`git` 是否可用、工作区状态、时区、数据库里的源与事件数。**不打印任何数据内容，只打印计数。**

所有命令失败时给**可操作的一句**（例如"未找到 git：请安装 git 或改用 --source csv"），不要打 traceback（`--debug` 时才打）。

---

## 10. 完成标准（我会这样验收）

```bash
uv sync
uv run pytest -q                                  # 全绿
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run recap init --tz Asia/Shanghai
uv run recap import ~/code --source git           # 退出码 0，打印报告
uv run recap insights --top 10 --explain          # 有分数、有分项、有事实
uv run recap doctor                               # 计数正确
```

外加三条人工检查：

1. `grep -rn "datetime.now\|astimezone\|strftime('%H')\|urllib.request" src/` 无命中。
2. 把同一个仓库导入两次，`recap doctor` 里的事件数不变。
3. `insights.json` 里每条 `evidence_sql` 都能在 sqlite3 里直接跑通。

---

## 11. 工作方式

- **不确定就问，不要猜。** 尤其是导出格式、字段语义、边界行为。列成编号问题，等回答，不要用"假设……"继续写。
- **一次只推进一个阶段。** 阶段结束时输出：改了哪些文件、跑通了哪些命令、遗留问题、下一阶段要做什么。
- **先写测试再写实现**，适配器、`tz.py`、打分三处必须如此。
- **不写没被要求的抽象**：没有第二个适配器之前，`base.py` 里不要出现工厂、注册表、插件加载器。entry point 注册留到有第三个适配器时再说。
- **不要美化 README**，三行能跑就行；文案是最后一件事。
- 如果某个决定会改变 §5 的契约，**停下来问**，不要自己扩展字段。
