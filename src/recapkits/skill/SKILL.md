---
name: recapkits
description: 读 recapkits 工作区的 agent/insights.json，写出能过校验的 story.json。
---

# 把一年的数据写成分镜脚本

## 你要做什么（三句话）

工作区在 `.recapkits/`，数据在 `agent/insights.json`（没有就用 `out/insights.json`）。
把它写成 `.recapkits/story.json`：一份分镜脚本，每张卡只描述数据里发生过的事。
数字、专有名词、敏感度三样都不能自己编 —— 校验器会逐条指出。

## 循环（五条命令，按顺序）

```bash
recap insights --top 10                    # 1. 产物: agent/insights.json
recap story --auto --out .recapkits/ref.json --force   # 2. 看合法形状(可选)
# 3. 你写 story.json —— 只有这一步是你做的
recap story --check .recapkits/story.json --insights .recapkits/agent/insights.json
recap render --format html                 # 5. 退出 0 才出片
```

第 2 步只看 JSON 形状，**不要照抄文案**。

## 七条硬规则

1. 数字只来自 `{{id.fact}}`；文案里不写任何数字，年份除外。
2. 占位符只能指向本卡 `insight` / `evidence` 里列出的 id。
3. 专有名词必须出现在被引洞察的 `facts[].label` 或 `display` 里。
4. 只描述发生了什么，不解释原因、不诊断人。
5. `allow_sensitive` 永远不写进 JSON；高敏洞察先问用户要不要用。
6. 先写 `headline`，再补 `sub` / `kicker`；不写「这一年」「让我们一起」。
7. 写完必须跑 `--check`，按 `code` 逐条改；**不要整份重写**。

## 卡型速查

| 卡型 | 主角洞察 | 硬要求 |
|---|---|---|
| `cover` | 不用 | 通常只放年份与一句 kicker |
| `big-number` | `vol.*` / `time.*` | 数字由管线取 `headline_fact`；evidence 最多 2 条 |
| `ranking` | `conc.*` | 洞察带 `rank_*` 事实，最多 5 行 |
| `heatmap` | `vol.daily_series` | 必须有 `axis="day"` 的 series |
| `clock` | `time.hour_rhythm` | 必须有 `axis="hour"` 的 series |
| `summary-grid` | 任意 | 至少 3 条被引洞察 |

`series` 是渲染数据：不要读、不要引用、不要写进 copy。

## 五种语气

写进 `meta.tone`。同一个事实，五种说法：

- `deadpan`（默认，陈述事实）：`{{i.fact}}` 天。其余日子没有记录。／全年账已经结清。
- `warm`（对朋友说话）：有 `{{i.fact}}` 天你在。／不在的那些天，也算数。
- `dry`（自嘲但不刻薄）：`{{i.fact}}` 天。比我预想的像样。／剩下的日子，我假装没看见。
- `cinematic`（画面感，短句）：屏幕亮到深夜。`{{i.fact}}` 次保存。／然后是很长的空白。
- `playful`（轻快，不玩梗）：`{{i.fact}}` 次，手速在线。／还有 `{{i.fact}}` 天在潜水。

## 两遍法：写 → 批 → 改

第一遍：一张卡只写 `headline`，一个事实。跑 `--check`。
第二遍：按 `code` 一次改一处，读完 `got` / `expected` / `hint` 三个字段。
同一处两轮还不过，就换一条洞察 —— 有些卡型天生不适合某些数据。

## 隐私

- 只把 `agent/insights.json` 交给模型；完整版含 `evidence_sql`，不要贴。
- `agent/restore.json` 里是真名，**不要上传、不要贴进对话**。
- 原始导出（CSV / JSON / zip）永远不要发给模型。
- `story.json` 里只有引用和文案，贴它不等于贴数据。

## 错误码 → 修法

| code | 修法 |
|---|---|
| `PLACEHOLDER_MALFORMED` | 写成 `{{id.fact}}`；检查花括号成对 |
| `PLACEHOLDER_UNKNOWN_INSIGHT` | 这个 id 不在 insights.json 里，抄一个真实存在的 |
| `PLACEHOLDER_NOT_REFERENCED` | 把该 id 加进本卡 `evidence`，或改用 `insight` |
| `PLACEHOLDER_UNKNOWN_FACT` | fact key 抄错，去 `facts[].key` 里找 |
| `NUMBER_NOT_IN_PLACEHOLDER` | 删掉手写数字换成占位符；年份可以留 |
| `NAME_NOT_IN_EVIDENCE` | 换成被引洞察 label / display 里的名字，或删掉 |
| `FORBIDDEN_CAUSALITY` | 删掉「导致」「因为…所以」「说明你」，只写发生了什么 |
| `SLOT_TOO_LONG` | 缩短文案；细节挪到另一张卡 |
| `SENSITIVE_REQUIRES_CONSENT` | 换一条低敏洞察；授权只能由用户在命令行给 |
| `CARD_UNKNOWN_INSIGHT` | `insight` 字段的 id 不存在，抄准 |
| `CARD_TYPE_MISMATCH` | 换卡型或换同族洞察，见卡型表 |
| `CARD_SERIES_MISSING` | 换一条带 series 的洞察 |
| `CARD_SERIES_AXIS_MISMATCH` | heatmap 要 day 轴，clock 要 hour 轴 |
| `TYPE_EVIDENCE_MISMATCH` | big-number 的 evidence 减到 2 条以内 |
| `SUMMARY_NEEDS_EVIDENCE` | 补 evidence 到 3 条，或换卡型 |

## 一个最小故事

```json
{
  "version": 1,
  "meta": {
    "year": 2024, "locale": "zh-CN", "theme": "neon",
    "tone": "deadpan", "tz": "<generated_from.tz>", "build_id": "<build_id>"
  },
  "cards": [
    { "id": "cover", "type": "cover",
      "copy": { "headline": "2024", "kicker": "本地生成 · 未上传" } },
    { "id": "total", "type": "big-number", "insight": "vol.total:git:2024",
      "copy": { "headline": "全年提交", "sub": "{{vol.total:git:2024.active_days}} 个活跃日" },
      "evidence": ["vol.total:git:2024"] }
  ]
}
```

`meta` 三个字段抄 insights.json：`tz` 抄 `generated_from.tz`，`build_id` 抄顶层同名键。
id 换成你那份里真实存在的；上面这份只是形状，不是可直接用的文案。
