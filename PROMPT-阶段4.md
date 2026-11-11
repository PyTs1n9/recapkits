# 阶段 4：修打分闸门 + 重建黄金语料 + story 校验器

阶段 3 已验收通过（42 测试绿、ruff/pyright 干净、幂等实测成立、`evidence_sql` 可执行且行数一致、无禁用 API）。本次任务有三项，**必须先做 4a，因为它会改变黄金快照**。

同目录有 `recapkits-开发计划.md`（完整设计）与 `PROMPT-起步.md`（阶段 1–3 的原始契约），只在需要解释"为什么"时查阅。

---

## 4a — 修正薄数据下的打分层闸门（约 2 小时）

### 我实测到的现象

对只有 4 条事件、1 个活跃日的数据集，输出是：

```
 1. +0.900  vol.busiest_day        单日最多事件 4
    deviation +0.00  rarity +0.00  discontinuity +0.50  concentration +0.40  obviousness +0.00
 2. -0.450  vol.total              事件总数 4
```

"单日最多事件 4，占 100%"算术上正确，语义上为零，却排在第一位。

### 根因

检测器的样本门槛是对的（`time.*` / `disc.*` / `conc.top_entity` 都被正确抑制了）。**问题在打分层**：`concentration` 与 `discontinuity` 两个分量在数据量不足时仍然参与计算——

- `concentration` 在只有一个活跃日时，`top1_share` 恒为 1.0，于是恒得 +0.40；
- `discontinuity` 在 `novelty == "record"` 时恒得 +0.50，而"只有一天数据"必然产生 record。

两个分量都在奖励"数据少"这件事，方向反了。

### 要做的修改

**1. 在 `scoring.py` 里加入数据充足度闸门**

```
sufficiency 判定（基于当前 period）：
  active_days < 3   或  events < 20   → "insufficient"
  active_days < 30                    → "thin"
  否则                                 → "ok"

分量闸门：
  active_days < 7  或  events < 30    → concentration 置 0.0
  active_days < 30                    → discontinuity 置 0.0
```

**2. 被置零的分量必须可解释**

`score_parts` 里保留该键（值 `0.0`），并新增 `gated: list[str]` 列出被闸门关闭的分量。`--explain` 输出形如：

```
 1. +0.000  vol.total              事件总数 4
    deviation +0.00  rarity +0.00  discontinuity +0.00(闸门)  concentration +0.00(闸门)  obviousness -0.45
    数据充足度: insufficient (4 事件 / 1 活跃日)
```

**3. Insight 增加字段 `data_sufficiency`: `"insufficient" | "thin" | "ok"`**

当它为 `"insufficient"` 时：

- 只保留 `vol.total` 一条洞察（其余全部丢弃，即使分数为正）；
- `vol.total` 的 `caveats` 追加 `"数据量不足（N 条事件 / M 个活跃日），本回顾仅供参考"`。

**4. 契约变更（本次唯一被授权改契约的地方）**

`insights.json` 每条 insight 增加 `data_sufficiency`，`score_parts` 保留被置零的键，新增顶层键 `gated`。同步更新 `docs/decisions/0001-contracts.md`，并在该文件顶部加一行变更记录（日期 + 原因）。

其他任何字段都不许动。

---

## 4b — 重建黄金语料（约 3 小时）

### 现状问题

`tests/golden/snapshots/git_year_2024.insights.json` 只有 **3 条事件、覆盖率 0.0082**。后果是 7 个检测器里有 5 个被样本门槛抑制，这个测试实际只验证了 `vol.*`，却看起来像在验证全部——它是个冒烟测试，不是回归测试。而且它把 4a 的缺陷固化成了"期望值"（`vol.busiest_day +0.767` 排第一）。

### 要做的

**直接构造 `events` 行，不经过 git 适配器。** 适配器有自己的测试；这里要测的是洞察与打分。

固定语料（全部硬编码时间戳，**不依赖当前日期**）：

| 维度 | 要求 |
|---|---|
| 年份 | 2024-01-01 → 2024-12-31 |
| 事件数 | 220 条 `kind="commit"` |
| 活跃日 | 46 天 |
| 最长连续 | 2024-05-01 → 2024-05-21（21 天） |
| 最长空档 | 2024-03-10 → 2024-03-16（7 天） |
| 集中度 | 仓库 `alpha` 占 62%，其余分散在 4 个仓库 |
| 深夜占比 | 22:00–03:00 的提交占 38% |
| 周末占比 | 12% |
| 时区 | `Asia/Shanghai`，事件全部带 `tz_offset_min=480` |

**断言：**

1. 7 个 kind 全部出现（`vol.total`、`vol.busiest_day`、`conc.top_entity`、`time.hour_rhythm`、`time.weekday_rhythm`、`disc.longest_streak`、`disc.longest_gap`）。
2. `data_sufficiency == "ok"`。
3. `disc.longest_streak` 的值为 21，`disc.longest_gap` 的值为 7。
4. `conc.top_entity` 的 `headline_fact.display` 约为 `62%`。
5. 排序稳定：连跑 3 次，`insights.json` 逐字节一致。
6. 每条 `evidence_sql` 在测试库上可执行，且 `evidence_rows` 与实际行数一致。

**再补一个"薄数据"用例**（新文件 `tests/golden/test_thin_data.py`）：4 条事件、1 个活跃日 → 断言只输出 1 条洞察、`data_sufficiency == "insufficient"`、`gated` 同时含 `concentration` 与 `discontinuity`。这个用例的作用是锁死 4a 的修复，防止以后回退。

---

## 4c — story 契约与校验器（约 12 小时）

### 约束

**不能用 pydantic，不能用 jsonschema**（运行时零第三方依赖）。手写 dataclass + 手写校验，错误信息自己组织。

新增：

```
src/recapkits/story/
├── __init__.py
├── schema.py        # Story / Card / Meta 的 dataclass + from_dict
└── validate.py      # V1–V7 + 结构化错误
```

CLI 增加子命令：`recap story --check story.json`，通过退出码 0，失败退出码 1 并打印错误表。

### 七条规则

| 编号 | 规则 | 实现要点 |
|---|---|---|
| **V1** | 占位符必须解析到被引洞察的 fact | 正则 `\{\{([a-z0-9_]+\.[a-z0-9_]+)\}\}`；只允许引用该卡 `insight` / `evidence` 里列出的 id；未解析即错 |
| **V2** | 数字不得手写 | 见下方"V2 细则" |
| **V3** | 卡片类型与洞察类型兼容 | 写死兼容表：`cover`→任意、`big-number`→`vol.*`/`time.*`、`ranking`→`conc.*`、`heatmap`→`disc.*`/`time.weekday_rhythm`、`clock`→`time.hour_rhythm`、`summary-grid`→任意（≥3 个 evidence） |
| **V4** | 槽位长度上限 | 见下方"V4 可注入度量" |
| **V5** | 高敏洞察需用户授权 | **`story.json` 里的 `allow_sensitive` 一律忽略**，只认 CLI 参数。必须有测试证明"写进 JSON 无效" |
| **V6** | 专有名词必须来自实体表 | 允许集合 = 被引洞察所有 `facts[].display` + `label` 的分词。文案里出现表外的大写开头词组（拉丁）或书名号/引号内内容（中文）→ 报错。提供 `--allow-unknown-names` 逃生阀 |
| **V7** | 禁止因果与诊断 | 词表匹配：`导致 / 因为.*所以 / 说明你 / 证明你 / 你有.*倾向 / 暴露了 / depressed / anxious / burned out / addicted`。命中即错，并指出命中的词 |

### V2 细则（这是最容易做错的一条）

必须拦住的形态：`1234`、`１２３４`（全角）、`١٢٣`（阿拉伯-印度数字）、`三`、`三十一`、`两`、`three`、`thirty-one`。

误伤控制（必须放行的）：`一天不落`、`一直`、`一样`、`一起`、`第一`（序数）、`一年`（当且仅当由占位符给出时则本来就不该出现）、年份 `2026`。

实现建议：汉字数词采用"数词 + 量词"模式匹配，量词表 `个/天/次/小时/分钟/秒/年/月/日/条/部/首/张/页/倍/成/万/千`；单独出现的"一"不匹配。年份白名单 `(19|20)\d{2}`。

每条错误返回：

```json
{ "code": "NUMBER_NOT_IN_PLACEHOLDER", "card_index": 1, "slot": "sub",
  "got": "四", "expected": "使用 {{vol.total.days}}",
  "hint": "引用被引洞察里的 fact，或删掉这个数字" }
```

`hint` 不是可选项——agent 只有一次修复机会，错误信息决定它是自愈还是放弃。

### V4 可注入度量

不要等渲染器。定义一个可替换的度量函数：

```python
Measure = Callable[[str, str, str], float]   # (slot, text, theme) -> px

def default_measure(slot: str, text: str, theme: str) -> float:
    """v0 估算：CJK 字符计 1.0em，拉丁字符计 0.55em，按槽位字号折算。"""

SLOT_BUDGET_PX = {"headline": 1080 - 2 * 72, "sub": 1080 - 2 * 72, "kicker": 480}
```

渲染器落地后，把 `default_measure` 换成真实字体度量，校验器代码不动。**接口签名不要改。**

### 必测（≥14 个对抗用例）

`tests/unit/test_validator.py` 至少覆盖：

1. 合法 story 通过
2. 占位符指向不存在的 insight
3. 占位符指向存在但未被该卡引用的 insight
4. 手写阿拉伯数字
5. 手写全角数字
6. 手写中文数词「三」
7. 手写英文数词 `three`
8. 放行「一天不落」（防误伤）
9. 放行年份 `2026`
10. 越权 `allow_sensitive`（写在 JSON 里，应被忽略）
11. 专有名词不在实体表
12. 槽位超长
13. 类型不兼容（`ranking` 配 `vol.total`）
14. V7 命中「说明你」

---

## 4d — 收尾

- 更新 `docs/decisions/0001-contracts.md`（4a 的变更 + 变更记录行）
- 新建 `docs/story-schema.md`（V1–V7 的对外说明，给写 skill 的人看）
- `.gitignore` 增加 `.workbuddy/`（当前未被忽略，会污染提交）
- 提交：`feat(story): validator with placeholder-only numbers` + `fix(scoring): sufficiency gates`

---

## 本次不做

- 渲染器、卡片、主题、HTML / PNG / MP4
- spotify / netflix / csv_generic 适配器
- MMR 多样性选卡
- 同比（YOY）
- `--auto` 规划器

做完停下汇报：改了哪些文件、7 个 kind 是否全部出现、14 个对抗用例是否全过、遗留问题。

---

## 验收命令

```bash
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run pyright
uv run recap story --check tests/fixtures/story-valid.json      # 退出码 0
uv run recap story --check tests/fixtures/story-bad-sum.json    # 退出码 1
uv run recap insights --top 10 --explain                        # 能看到「闸门」标注
```

另外我会手工核对三件事：

1. 连跑 3 次 `insights --json`，输出逐字节一致。
2. 把 `tests/fixtures/story-bad-sensitive.json` 里的 `allow_sensitive: true` 改成 `false`，校验结果**不变**（证明该字段被无视）。
3. 薄数据用例：`data_sufficiency == "insufficient"` 且 `gated` 含两个分量。
