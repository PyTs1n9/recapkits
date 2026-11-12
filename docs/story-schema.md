# story.json 规范与校验器

`story.json` 是渲染器的唯一输入。**数字只能来自占位符**，文案不得手写任何数量、比例或排名。
`recap story --check` 是渲染前的闸门：通过才允许出图。

## 文件结构

```json
{
  "version": 1,
  "meta": { "year": 2024, "locale": "zh-CN", "theme": "neon", "tone": "deadpan",
            "tz": "Asia/Shanghai", "build_id": "b3:60bdae9b" },
  "cards": [
    { "id": "c1", "type": "cover",
      "copy": { "headline": "2024", "kicker": "本地生成 · 未上传" } },
    { "id": "c2", "type": "big-number", "insight": "vol.total:git:2024",
      "copy": { "headline": "{{vol.total:git:2024.events}} 次提交",
                "sub": "覆盖 {{vol.total:git:2024.active_days}} 个活跃日" },
      "evidence": ["vol.total:git:2024"] }
  ]
}
```

- `copy` 只允许 `headline` / `sub` / `kicker` 三个槽位。
- `insight` 是这张卡的主角，`evidence` 是它引用的证据链；占位符只能指向这两处列出的 id。
- `build_id` 取自 `insights.json`，用于确认故事与数据是同一批。

## 卡片类型与兼容

| 类型 | 可承载的洞察 | 额外要求 |
|---|---|---|
| `cover` | 任意（通常不引洞察） | — |
| `big-number` | `vol.*`、`time.*` | `evidence` 最多 2 条；数字由 `insight` 提供 |
| `ranking` | `conc.*` | 洞察需带 `rank_*` 事实（最多 5 行） |
| `heatmap` | `vol.daily_series` | 洞察必须带 `axis="day"` 的 `series` |
| `clock` | `time.hour_rhythm` | 洞察必须带 `axis="hour"` 的 `series` |
| `summary-grid` | 任意，但至少要 3 条被引洞察 | 最多取 9 个 fact |

六个类型均已实现；缺少必要数据时校验器直接报错，不会画个空屏。

### `big-number` 的写法

巨型数字**不写在文案里**，它由管线提供：取 `insight` 所指洞察的
`headline_fact.display`。`insight` 是数字的唯一来源；`evidence` 不再提供数字：

```json
{ "id": "c3", "type": "big-number", "insight": "vol.total:git:2024",
  "copy": { "kicker": "全年", "headline": "提交总数",
            "sub": "覆盖 {{vol.total:git:2024.active_days}} 个活跃日" } }
```

渲染结果是自下而上的四层：数字（320px）→ `headline`（140px）→ `sub`（56px）→ `kicker`。
`headline` 只允许一行、`sub` 最多两行，超出**渲染器报错**而不是静默截断 ——
被截断的文案会以"看起来对"的方式把错误数据发出去。

`ranking` 上线前，`big-number` 曾允许借首条 `evidence` 的 `headline_fact` 当数字。
这条通道已删除：一个语义两种表达方式，留着就一定会有人用错。现在
`big-number` 携带 3 条及以上 `evidence` 会报 `TYPE_EVIDENCE_MISMATCH`。

## `series`：供渲染的序列

`clock` 需要 24 小时分布，`heatmap` 需要逐日强度。这些数据**不能塞进 `display` 字符串**
（例如 `"0.01,0.02,..."`）：`display` 是标量文案，一旦承载序列，V1 的占位符校验就失去意义。

`insights.json` 的每条洞察可以带一个可选 `series`：

```json
"series": {
  "axis": "hour" | "weekday" | "day",
  "keys": ["0", "1", "2", "..."],
  "values": [0.011, 0.024, 0.031, "..."],
  "unit": "share" | "count"
}
```

约束：

- `len(keys) == len(values)`，否则报错。
- `axis="hour"` 时 `keys` 恰为 `"0".."23"`；`axis="weekday"` 时恰为 `"0".."6"`（0=周一）。
- `axis="day"` 时 `keys` 为 `YYYY-MM-DD`，覆盖审查窗口的每一天（含零值），长度等于窗口天数。
- `unit="share"` 时 `values` 之和为 1.0（容差 1e-6）。
- 无序列的洞察不写这个键（不写 `null`）。

`vol.daily_series` 是第 8 个检测器，专门产出 `axis="day"` 的逐日事件数；它的
`signal` 固定 `0.0`，不参与排名，但会被 `select()` 无条件附在输出末尾，确保
`heatmap` 引用它时一定能在 `insights.json` 里找到。

## 占位符

格式 `{{<insight_id>.<fact_key>}}`，按**最后一个点**切分。

洞察 id 本身可能含点、冒号和连字符（例如 `vol.total:git:2024`、
`disc.longest_gap:git:2024:2024-03-10`），因此校验器接受 `[a-z0-9_.:%-]` 的 id 片段。
连字符是阶段 5b 补进来的：`disc.*` 的 id 带日期，少了它这类洞察永远无法被引用。

`conc.*` 的 id 里有一段来自用户的实体名（仓库目录名）。它在拼接前会按 UTF-8 字节转义，
只保留 `[a-z0-9_-]`，其余写成 `%xx`：中文仓库名 `龘-repo` 得到
`conc.top_entity:repo:%e9%be%98-repo:2024`。转义是可逆且单射的，因此中文、大写字母、
空格、点号都不会让洞察"算得出来但引不到"；展示用的原名在 `facts[].label` 里，不受影响。

`fact_key` 必须在该洞察的 `headline_fact` 或 `facts[].key` 里存在。

## 七条规则

| 编号 | 规则 | 错误码 |
|---|---|---|
| V1 | 占位符必须解析到被引洞察的 fact | `PLACEHOLDER_MALFORMED` / `PLACEHOLDER_UNKNOWN_INSIGHT` / `PLACEHOLDER_NOT_REFERENCED` / `PLACEHOLDER_UNKNOWN_FACT` |
| V2 | 数字不得手写（阿拉伯、全角、阿拉伯-印度、中文数词+量词、英文数词） | `NUMBER_NOT_IN_PLACEHOLDER` |
| V3 | 卡片类型与洞察类型兼容，且所需序列存在、轴正确 | `CARD_TYPE_MISMATCH` / `CARD_UNKNOWN_INSIGHT` / `SUMMARY_NEEDS_EVIDENCE` / `CARD_SERIES_MISSING` / `CARD_SERIES_AXIS_MISMATCH` / `TYPE_EVIDENCE_MISMATCH` |
| V4 | 槽位长度上限（估算用于早失败；真实布局由设计断言判定） | `SLOT_TOO_LONG` |
| V5 | 高敏洞察需用户授权，`story.json` 里的 `allow_sensitive` 一律忽略 | `SENSITIVE_REQUIRES_CONSENT` |
| V6 | 专有名词必须来自被引洞察的事实或标签 | `NAME_NOT_IN_EVIDENCE` |
| V7 | 禁止因果与诊断表述 | `FORBIDDEN_CAUSALITY` |

V2 的放行项：年份 `(19|20)\d{2}`、序数（`第三`）、以及「一天不落」这类语气短语。

每条错误都给出 `code`、`card_index`、`slot`、`got`、`expected`、`hint`。`hint` 不是装饰：
写 skill 的 agent 通常只有一次修复机会。

## `--auto` 生成的故事

`recap story --auto` 从 `insights.json` 的**已选列表**（`select()` 已经截断并附回
`vol.daily_series`）规划一份故事，不再自己重排、不再重算分数 —— 两套排序必然漂移。

**卡片顺序固定：** `cover → big-number → ranking → heatmap → clock → summary`。卡片 id
用语义名而不是 `c1..c6`，因为它们会出现在渲染器的报错里。跳过一张卡必须打印理由
（闸门关闭 / 数据不足 / `--top` 截断），不静默消失：

| 卡型 | 需要的洞察 | 缺失时的理由 |
|---|---|---|
| `cover` / `big-number` | `vol.total` | 没有 `vol.total`：先跑 `recap import` |
| `ranking` | `conc.top_entity` | 事件不足 50 条时不出集中度 |
| `heatmap` | `vol.daily_series` | 工作区没有事件，或数据不足时它与其余洞察一起被闸门关闭 |
| `clock` | `time.hour_rhythm` | 活跃日不足 30 天时被闸门关闭 |
| `summary-grid` | 至少 3 条可引洞察 | `--top` 太小，或数据源太少 |

`vol.total` 完全没有时不是"跳过"，是**报错**：一个只有空故事的工作区不该产出文件。
`summary-grid` 的 `evidence` 只引用前面真的画出来的卡，且不含 `vol.daily_series`（它的
facts 是"窗口天数"，放进总览是噪声）。

**模板只允许三种成分：** CJK 文案、`{{id.fact}}` 占位符、年份字面量。去掉占位符与年份
之后不得出现 `[0-9A-Za-z]` —— 一条测试遍历全部模板就能同时守住 V2 与 V6，不用逐条背
规则。同理，模板里不写"前三""前五"这类序数：它们现在只是靠 `CHINESE_NUMBER` 缺量词才
漏过去，规则一收紧就翻脸。

**自动生成的故事同样要过 `--check`。** 生成后立刻 `Story.from_dict` →
`validate_story(allow_sensitive=False)`，零错误才写盘；有错就打印 `format_errors` 并退出
1，不留下半成品 —— 写出坏 `story.json` 只会把失败推迟到 render，用户会看到两条互相矛盾
的错误。

**不覆盖手写故事：** `story.json` 已存在时拒绝，除非 `--force`。**高敏洞察不自动使用：**
`sensitivity == "high"` 直接跳过，理由写「需要 --allow-sensitive」—— 自动生成的文案不该
替用户做授权决定。

`recap <路径>` 在缺故事时调用同一个规划器，然后直接渲染 HTML；`--no-auto` 保留旧行为
（只到 insights 为止）。

## 命令行

```bash
recap story --check story.json                                  # 通过 0 / 失败 1
recap story --check story.json --allow-sensitive                # 用户显式授权高敏洞察
recap story --check story.json --allow-unknown-names            # 放行实体表外的名字
recap story --check story.json --insights path/to/insights.json # 指定数据源

recap story --auto                                              # 自动规划到 .recapkits/story.json
recap story --auto --out story.json --force                      # 指定路径并覆盖
recap story --auto --year 2025 --theme neon --tone deadpan       # 换年份 / 主题 / 语气

recap insights --md                                            # 同时写 insights.json 与 insights.md
recap insights --no-md                                         # 只写 JSON
recap insights --payload-preview                               # 报出含/不含 series 的字节差
recap render --format html --aspect 9:16                        # 出单文件 HTML
recap render --format png --aspect 4:5                          # 逐卡 PNG 到 out/cards-4x5/
recap render --format mp4 --aspect 9:16                         # 出 MP4, 需要 ffmpeg 5.1+
recap preview                                                   # 本地预览, 改文件自动刷新
```

`--check` 与 `--auto` 互斥且必选其一。

`insights.json` 的查找顺序：`--insights` → 故事文件同目录的 `insights.json`
→ 当前工作区 `.recapkits/out/insights.json`。同目录优先，是为了让 fixture 自成一体。

## 渲染

`recap render` 的内部顺序是 **load → validate → bake → render**，见
[`docs/decisions/0002-render-pipeline.md`](decisions/0002-render-pipeline.md)。
`bake` 之后渲染器只看到纯字符串，所以产物里不会出现 `{{...}}`；万一有，
渲染器会直接失败而不是把字面量画出来。

产物默认写到 `.recapkits/out/recap-<年份>.html`：单文件、CSS 内联、无外部请求。
命令只打印绝对路径，不自动打开浏览器。

`--format png` 走同一条管线，只把最后一步换成真实浏览器逐卡截图：输出到
`.recapkits/out/cards/`（9:16）或 `.recapkits/out/cards-4x5/`（4:5），文件名为
`recap-<年份>-01.png`…，序号补零，写之前先清掉该目录上一轮的 `recap-*.png`。
两个比例分开目录，是因为图名不含比例，同一目录会互相覆盖。截图要等字体就绪、两帧绘制与页面上的 `data-render-ready` 标记，
视口与舞台同尺寸、缩放固定为 1，否则像素对不上设计稿（见
[`docs/decisions/0002-render-pipeline.md`](decisions/0002-render-pipeline.md) 的决定四）。

`--format mp4` 复用同一批截图：动画只在采集时由 `data-motion="on"` 打开，帧状态由
`currentTime` 驱动；六张卡约 24s / 729 帧，写到 `.recapkits/out/recap-<年份>.mp4`
（4:5 为 `recap-<年份>-4x5.mp4`）。`--out` 在这里是**文件**，与 PNG 的目录语义相反；
`--fps` 默认 30。ffmpeg 是系统依赖，缺失时在读 `story.json` 之前退出。
详见 [`docs/decisions/0002-render-pipeline.md`](decisions/0002-render-pipeline.md) 的决定六。

## 长度预算

画布宽 1080，左右各留 72，因此 `headline` 与 `sub` 的可用宽度是 936px，`kicker` 是 480px。
校验器把 CJK 记 1.0em、拉丁记 0.55em 再乘槽位字号，这是**早失败**用的估算；
渲染器组件用同一套启发式做卡片内检查。

最终判据是阶段 6c 的真实布局测量：每个可能溢出的文本块都带 `data-fit="<槽位>"`，
浏览器里横向断言 `scrollWidth <= clientWidth + 1`，纵向断言**渲染后的行数**不超过
槽位预算（`sub` / `label` / `caveat` 两行，其余一行）。

纵向为什么不用 `scrollHeight <= clientHeight + 1`：当 `line-height` 小于字体的墨迹比
（Windows/YaHei 约 1.32em）时，Chrome 会把字形墨迹的溢出也算进 `scrollHeight` ——
实测 72px/1.1 的「137次」是 client 79 / scroll 87，照搬这条判据会让每个正常文本块
都报错。行数才是「放不放得下」的答案，墨迹越界交给安全区的像素断言。

估算可以偏保守，但不能替代测量 —— 估算是为了早报错，测量才是最终判据。
