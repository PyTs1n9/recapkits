# spotify 口径与已知分歧

本文件记录 `recap import <导出目录> --source spotify` 的计数口径, 以及我们的数字与
Spotify 自己的年度回顾为什么会不一样。**默认镜像平台口径**, 否则首日就会被当成算错。

数据来源: Extended streaming history 里的 `Streaming_History_Audio_*.json`。
只读这一类文件; `AccountData.json`、`Playlist*.json`、`Follow.json` 等不读, 也不需要。

## 我们选的口径

| 规则 | 取值 | 理由 |
|---|---|---|
| 有效播放 | `ms_played > 30000` | 与平台公开的 30 秒门槛一致; **严格大于**, 30000 毫秒整不计入 |
| 私密会话 | `incognito_mode = true` 排除 | 用户明确表示不想留下记录 |
| 播客/有声书 | 计入时长与事件数, `title` / `subtitle` 为空 | `master_metadata_*` 全为 null; 节目名不是「艺人」, 不能进 `conc.top_entity` |
| 多文件重叠 | 按 `(source, ts_utc, uri, ms_played)` 哈希去重 | 同一行出现在两个文件里只留一条; **不按 ts 去重**, 同一秒的不同曲目是两次真实播放 |
| 旧版字段 | `trackName` / `artistName` / `msPlayed` 与新版双支持 | 新版非空才用新版; 两套都缺则记 `missing_ts` / `missing_ms_played` |
| 时区 | `tz_offset_min = None`, 本地时间由工作区 `--tz` 决定 | 导出只带 UTC; 写成 0 会把小时分布锁死在 UTC |

隐私: `conn_country` 与 `ip_addr` **入库前丢弃**, 不进 `events`、`meta_json`、`flags`、
`insights.json`、`insights.md` 或 HTML。`raw_row` 表保持为空 —— 把原始行抄回去等于
把刚丢掉的 PII 又捡回来。

## 与平台年度回顾的分歧

| 分歧 | 为什么合法 | 我们选哪边 |
|---|---|---|
| 总时长/总次数不可能与 Wrapped 完全一致 | 平台的统计窗口、四舍五入、去重规则未公开, 且 Wrapped 有时只统计到 10 月底 | 我们的窗口是自然年; 报告里写清窗口与覆盖率 |
| 「最多艺人」的名次 | 平台可能按收听时长或按播放次数排序; 两者在不同用户身上会给出不同第一名 | 明确按**事件数**排序, `share` 的分母是窗口内全部事件(含播客) |
| 播客与有声书 | 平台在 Wrapped 里单独成册; 我们把它们算进总时长, 但不参与实体榜 | 计入时长, 不产生实体 |
| 30 秒边界 | 平台未公开是否含等号 | 严格 `> 30000`; 边界行为有测试锁住 |
| 离线/重复上报 | 不同客户端的上报次数不同 | 同一 `(ts, uri, 时长)` 只算一次 |

## 已知 caveat

- **旧格式的 `endTime` 按 UTC 解读。** 2023 年前的导出没有 `ts`, 只有无偏移的
  `endTime`; 我们按 UTC 归一 (见 `tz.split_utc_and_offset`), 不猜「大概是本地时间」。
  更要紧的是: `endTime` 是**播放结束**时刻, 而新版 `ts` 是开始时刻。我们没有回推
  `-ms_played`, 因此老格式的本地小时可能比真实开始时间晚一首歌的长度。只有 2022 及
  更早的数据会遇到。
- **换时区会改变深夜占比。** 这是预期: 源不带偏移, 本地时间由工作区的 IANA 时区
  决定。同一份导出分别用 `Asia/Shanghai` 与 `America/New_York` 导入, `time.hour_rhythm`
  必须不同; 两次相同说明 `tz_offset_min` 被写成了 0。
- **`--since` / `--until` 按本地日期过滤。** 边界日的判定用工作区时区, 不是 UTC。

## 换口径的开关

没有 CLI 开关。要改 30 秒门槛, 改 `src/recapkits/adapters/spotify.py` 的
`MIN_PLAY_MS`, 同时更新本文件与 `tests/unit/test_adapter_spotify.py` 的边界用例。
