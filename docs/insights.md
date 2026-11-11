# 洞察与打分

`recap insights` 产出候选洞察并按分数排序。本文记录**分数是怎么算出来的**，以及每个
检测器自报的 `signal` 锚点。改排序只需要改 `scoring.py` 顶部的常量，不需要动检测器。

打分二期（阶段 5a）换掉了整套公式。一期的问题不是权重没调好，而是结构错位，见文末
「为什么删掉三个分量」。

## 公式

```
score = 1.00*signal + 0.40*deviation + 0.30*discontinuity − 1.00*sensitivity
```

| 分量 | 取值 | 何时为 0 |
|---|---|---|
| `signal` | 每个检测器**自己报告**的 0..1 强度，必填 | 从不（最低 0.0） |
| `deviation` | `clamp(|稳健 z| / 3)`，与上一期比 | 无上一期数据时 0.0，并记入 `gated` |
| `discontinuity` | 有上一期且与上期不同：record/absence=1.0、shift=0.5 | 无上一期数据时 0.0，并记入 `gated` |
| `sensitivity` | high → −1.00 | 非高敏 |

`score_parts` 存**已加权**的分量，所以 `score == sum(score_parts)` 是硬不变量，
`--explain` 的逐项打印不会被质疑口径。`novelty` 字段保留（文案要用，也要显示给用户看），
但不再以二值标签的形式驱动打分。

## signal 锚点

每个锚点都写成「多少算没有信号、多少算满格」，而不是拍一个系数：这样调阈值时，
讨论的是数据的形状，不是分数的手感。

| kind | signal 公式 | 锚点含义 |
|---|---|---|
| `vol.total` | `0.05` 常数 | 只作开场卡锚点，不参与竞争 |
| `vol.busiest_day` | `clamp((峰值日事件数 / 日均事件数 − 1.5) / 8.5)` | 1.5× 日均 = 无信号；10× = 满格 |
| `conc.top_entity` | `clamp((top1_share − 0.20) / 0.60)` | 20% = 没有集中；80% = 极端集中 |
| `time.hour_rhythm` | `clamp((深夜占比 − 0.10) / 0.40)` | 10% ≈ 均匀分布；50% = 极端夜行 |
| `time.weekday_rhythm` | `clamp((最大星期占比 − 1/7) / (0.40 − 1/7))` | 1/7 = 完全均匀；40% = 极端偏向某天 |
| `disc.longest_streak` | `clamp(连续天数 / 60)` | 60 天 = 满格 |
| `disc.longest_gap` | `clamp(空档天数 / 21)` | 21 天 = 满格 |

常量集中在 `src/recapkits/insights/scoring.py` 顶部（`SIGNAL_BUSIEST_DAY_FLOOR` 之类），
命名与上表一一对应。

## 数据充足度 vs. 排序

两件事，别混：

- **该不该出卡** 由 `data_sufficiency` 管（活跃日 < 3 或事件 < 20 为 `insufficient`，
  此时只留 `vol.total`；活跃日 < 30 为 `thin`）。4a 的判定原样保留。
- **出了卡怎么排序** 由上面的公式管。

## 为什么删掉三个分量

| 删除 | 理由 |
|---|---|
| `rarity` | 静态先验表尚未存在，恒为 0；「稀有」这件事已由各类 signal 的锚点承担 |
| `concentration` | 被 signal 取代。它只是 `conc.top_entity` 的强度指标，不该是所有 kind 的通用分量 |
| `obviousness` | **职责错位**：它想解决「每个用户都有第一」的问题，但那是**选卡的冗余问题**，不是分数的惊喜度问题。选卡已有「同一 kind 最多取 1 个」的规则，惩罚项属于重复治理 |

一期的实测症状（220 事件 / 46 活跃日）：`time.*` 恒为 0、`disc.*` 恒为 0.5 左右且与量级
无关、`conc.top_entity` 因 0.40 − 0.45 结构性封顶为负。根因是「六个通用分量」假设每个
检测器都能激活同样的分量，而事实上只有 `novelty` 在工作，且它是二值的。

二期在同一语料上的排名见 `tests/golden/test_corpus.py` 的
`test_concentration_and_hour_rhythm_lead_the_ranking`：62% 的集中度与 38% 的深夜占比
占据前二，且都 ≥ 0.65。

## 回归锁

`tests/unit/test_scoring_signals.py::test_time_kinds_no_longer_score_zero` 与
`test_weekday_rhythm_scores_when_a_weekday_dominates` 是本期最重要的一条测试：
它们分别造出「全部事件在深夜」与「全部事件在周一」的语料，断言 `time.*` 的分数会被
signal 真的抬起来。任何把 `time.*` 退回恒 0 的改动都会让这两条失败。
