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

| 类型 | 可承载的洞察 |
|---|---|
| `cover` | 任意（通常不引洞察） |
| `big-number` | `vol.*`、`time.*` |
| `ranking` | `conc.*` |
| `heatmap` | `disc.*`、`time.weekday_rhythm` |
| `clock` | `time.hour_rhythm` |
| `summary-grid` | 任意，但至少要 3 条被引洞察 |

阶段 5b 只实现了 `cover` 与 `big-number`；其余四种遇到即报错，不会画个空屏。

### `big-number` 的写法

巨型数字**不写在文案里**，它由管线提供：优先取 `insight` 所指洞察的
`headline_fact.display`，没有 `insight` 时退回首条 `evidence`。于是：

```json
{ "id": "c3", "type": "big-number",
  "copy": { "kicker": "年度执念", "headline": "提交集中度", "sub": "都指向同一仓库 alpha" },
  "evidence": ["conc.top_entity:repo:alpha:2024"] }
```

渲染结果是自下而上的四层：数字（320px）→ `headline`（140px）→ `sub`（56px）→ `kicker`。
`headline` 只允许一行、`sub` 最多两行，超出**渲染器报错**而不是静默截断 ——
被截断的文案会以"看起来对"的方式把错误数据发出去。

之所以能借 `evidence` 上卡（而不是必须写 `insight`），是因为 `ranking` 还没实现，
而集中度往往是整组里最值得看的数字。`insight` 为空时 V3 的类型兼容检查会跳过，
这是故意留的过渡通道。

## 占位符

格式 `{{<insight_id>.<fact_key>}}`，按**最后一个点**切分。

洞察 id 本身可能含点、冒号和连字符（例如 `vol.total:git:2024`、
`disc.longest_gap:git:2024:2024-03-10`），因此校验器接受 `[a-z0-9_.:-]` 的 id 片段。
连字符是阶段 5b 补进来的：`disc.*` 的 id 带日期，少了它这类洞察永远无法被引用。

`fact_key` 必须在该洞察的 `headline_fact` 或 `facts[].key` 里存在。

## 七条规则

| 编号 | 规则 | 错误码 |
|---|---|---|
| V1 | 占位符必须解析到被引洞察的 fact | `PLACEHOLDER_MALFORMED` / `PLACEHOLDER_UNKNOWN_INSIGHT` / `PLACEHOLDER_NOT_REFERENCED` / `PLACEHOLDER_UNKNOWN_FACT` |
| V2 | 数字不得手写（阿拉伯、全角、阿拉伯-印度、中文数词+量词、英文数词） | `NUMBER_NOT_IN_PLACEHOLDER` |
| V3 | 卡片类型与洞察类型兼容 | `CARD_TYPE_MISMATCH` / `CARD_UNKNOWN_INSIGHT` / `SUMMARY_NEEDS_EVIDENCE` |
| V4 | 槽位长度上限（v0 用估算度量） | `SLOT_TOO_LONG` |
| V5 | 高敏洞察需用户授权，`story.json` 里的 `allow_sensitive` 一律忽略 | `SENSITIVE_REQUIRES_CONSENT` |
| V6 | 专有名词必须来自被引洞察的事实或标签 | `NAME_NOT_IN_EVIDENCE` |
| V7 | 禁止因果与诊断表述 | `FORBIDDEN_CAUSALITY` |

V2 的放行项：年份 `(19|20)\d{2}`、序数（`第三`）、以及「一天不落」这类语气短语。

每条错误都给出 `code`、`card_index`、`slot`、`got`、`expected`、`hint`。`hint` 不是装饰：
写 skill 的 agent 通常只有一次修复机会。

## 命令行

```bash
recap story --check story.json                                  # 通过 0 / 失败 1
recap story --check story.json --allow-sensitive                # 用户显式授权高敏洞察
recap story --check story.json --allow-unknown-names            # 放行实体表外的名字
recap story --check story.json --insights path/to/insights.json # 指定数据源

recap render --format html --aspect 9:16                        # 出单文件 HTML
recap preview                                                   # 本地预览, 改文件自动刷新
```

`insights.json` 的查找顺序：`--insights` → 故事文件同目录的 `insights.json`
→ 当前工作区 `.recapkits/out/insights.json`。同目录优先，是为了让 fixture 自成一体。

## 渲染

`recap render` 的内部顺序是 **load → validate → bake → render**，见
[`docs/decisions/0002-render-pipeline.md`](decisions/0002-render-pipeline.md)。
`bake` 之后渲染器只看到纯字符串，所以产物里不会出现 `{{...}}`；万一有，
渲染器会直接失败而不是把字面量画出来。

产物默认写到 `.recapkits/out/recap-<年份>.html`：单文件、CSS 内联、无外部请求。
命令只打印绝对路径，不自动打开浏览器。

## 长度预算

画布宽 1080，左右各留 72，因此 `headline` 与 `sub` 的可用宽度是 936px，`kicker` 是 480px。
v0 的估算把 CJK 记 1.0em、拉丁记 0.55em 再乘槽位字号；渲染器落地后替换
`recapkits/story/measure.py` 里的 `default_measure` 即可，校验器不用改。
