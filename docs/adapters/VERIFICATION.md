# 适配器核验状态

计划 §11.7 要求每个一等适配器经 **≥2 份独立真实导出**验证，DoD 把它列为发布条件。
本文件把「已经验过的」与「还等人提供样本的」分开写清楚：合成 fixture 全绿不等于真实
导出验过，这两件事不能互相冒充。

数据来源：`tests/fixtures/`（由 `scripts/make-fixtures.py` 以固定 seed 生成，
`--check` 逐字节比对）、`tests/unit/test_adapter_*.py`、`tests/golden/test_insights_*.py`。

## 逐文件行账

恒等式：**已解析 + 已跳过(有原因) == 源文件行数**。整份跳过（坏文件、缺文件）不计行数，
单独成行。表格由 `recap import` 的逐文件账输出整理而来，可一条命令复现。

### spotify（`tests/fixtures/spotify`）

| 文件 | 源行数 | 解析 | 跳过 | 跳过原因 |
|---|---:|---:|---:|---|
| `Streaming_History_Audio_2015-2022_0.json` | 6 | 6 | 0 | — |
| `Streaming_History_Audio_2023-2024_0.json` | 103 | 99 | 4 | `incognito` 1、`short_play` 3 |
| `Streaming_History_Audio_2024_1.json` | 109 | 108 | 1 | `short_play` 1 |
| `Streaming_History_Audio_2024_broken.json` | — | 0 | 整份 | 不是合法 JSON，记警告后继续下一个文件 |
| **合计** | **218** | **213** | **5** | 入库 209 条（4 条跨文件重复被 `row_hash` 吸收） |

### netflix（`tests/fixtures/netflix`）

| 文件 | 源行数 | 解析 | 跳过 | 跳过原因 |
|---|---:|---:|---:|---|
| `ViewingActivity.csv` | 158 | 143 | 15 | `bad_duration` 1、`empty_title` 1、`preview` 5、`resume_duplicate` 3、`supplemental` 5 |
| `Profiles/Bob/ViewingActivity.csv` | 39 | 37 | 2 | `resume_duplicate` 2 |
| **合计** | **197** | **180** | **17** | 全部入库，无跨档案重复 |

`Profiles/` 下两个档案合并为一个源，报告打印「已合并 2 个档案，未写入档案名」；
档案数由 `profile_hash` 去重统计，明文只参与哈希。

## 编码矩阵

netflix 的编码 × 边界逐格结果在 `docs/adapters/netflix/KNOWN_DIVERGENCES.md`
的「编码矩阵」一节，**10 格**每一格都对应
`tests/unit/test_adapter_netflix_encoding.py` 里一条真实断言，`uv sync` 之外不需要
任何依赖：

| 格 | 结果 |
|---|---|
| UTF-8 无 BOM / UTF-8 带 BOM / `cp1252`（重音片名 `Amélie`） | 解析 1 条，重音字符原样保留 |
| CRLF 行尾 | 解析 1 条 |
| 字段内嵌逗号与引号 | 解析 1 条，原串一字不差 |
| 单个坏字节 `0x81` | 跳过该行（`bad_encoding`），整份 CSV 继续 |
| 孤立 NUL 行 | 跳过该行（`bad_row`, 列数不符） |
| 空文件 | 整份跳过，其余文件照常导入 |
| 超长字段（> 128 KB） | 整份跳过（CSV 结构错误） |
| 缺必需列 | 报错并指名文件与列，不猜列名映射 |

## 幂等、时区与隐私

| 检查 | 结果 |
|---|---|
| 同一目录导入两次 | spotify 新增 0 条 / netflix 新增 0 条；事件数 209 + 180 不变 |
| 两次 `insights.json` | sha256 `c621de06b922de64…` 两次相同，逐字节一致 |
| `Asia/Shanghai` vs `America/New_York` | 深夜占比 59% vs 40%，`tz_offset_min` 为 `None`，源不带偏移 |
| `conn_country` / `ip_addr` / `Profile Name` 明文 | DB、`insights.json`、`insights.md`、HTML 全文零命中 |
| `raw_row` 表 | 0 行 |

## 核验状态

| 项 | git | spotify | netflix |
|---|---|---|---|
| 合成 fixture 覆盖的边界 | 已验（适配器 + 黄金测试） | **已验（24 条）** | **已验（41 条，含编码矩阵 10 格）** |
| 真实导出 #1 | 已在开发机上验（本仓库自身） | 待提供 | 待提供 |
| 真实导出 #2 | 待提供 | 待提供 | 待提供 |
| 分歧文档 | — | 已写 | 已写 |

**当前结论：** 两个适配器在合成语料上全部验收项通过；**真实导出核验尚未开始**，
不因为「合成数据看起来合理」而记为通过。样本到位后按同一套命令复跑逐文件行账、
幂等与 PII 扫描，把两轮的日期与结论补进上表。
