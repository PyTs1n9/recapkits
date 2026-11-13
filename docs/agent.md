# 让 agent 写得更好

recapkits 的校验器（V1–V7）能拦住几乎所有「写得不像」的文案，但它不负责**写**。
这份文档讲怎么把写故事的活交给 agent，同时不让它看到不该看的东西。

- 目标读者：已经在用 Claude Code / Cursor / 其他编码 agent 的人。
- 不涉及：调用任何 LLM API。recapkits 本身仍然不发一个包外的请求。

## 1. 三份文件，各管一件事

`recap insights` 之后，工作区里会多出这些：

| 路径 | 是什么 | 能给模型看吗 |
|---|---|---|
| `.recapkits/out/insights.json` | 完整版：含 `score_parts`、`evidence_sql`、`evidence_rows` | 不推荐 |
| `.recapkits/agent/insights.json` | 最小版：只留决策字段，仍可被 `--check` 使用 | 可以 |
| `.recapkits/agent/restore.json` | 假名 → 原名（仅 `--entities=placeholder` 时生成） | **不能** |

最小版删掉的三项都是「本机工具用的」：`score_parts` 给 `--explain`，`evidence_sql` 与
`evidence_rows` 给证据链审计。它保留 `series`，因为 heatmap / clock 的校验需要序列 ——
没有它，agent 拿到的载荷校验不了自己写的故事。

`--payload-preview` 会先告诉你发出去多少：

```bash
recap insights --top 10 --payload-preview
# payload      20,408 字节 · 8 条洞察
# agent        17,244 字节 · 8 条洞察（-16%）
# 删除         evidence_sql 2,255 · score_parts 746 · evidence_rows 163
```

## 2. 安装 skill

skill 讲的是**这个工作区**的 `.recapkits/`，所以只装到当前项目：

```bash
recap skill install --target claude    # .claude/skills/recapkits/SKILL.md
recap skill install --target cursor    # .cursor/rules/recapkits.mdc
recap skill install --target agents    # ./AGENTS.md 的标记块
recap skill install --target print     # 只打印, 不写文件
```

一次可以装多个：`--target claude --target cursor --target agents`。`print` 只能单独用。

重复安装是幂等的：内容相同打印 `未改动`；不同且没有 `--force` 会报错并给出路径。
`AGENTS.md` 的标记块由我们管理，块内直接替换、块外一个字不动（行尾也保留）。

装了 skill 之后，在 agent 里说一句「按 recapkits skill，把
`.recapkits/agent/insights.json` 写成 `story.json`」即可。

## 3. 循环

```bash
recap insights --top 10                                              # 1
recap story --auto --out .recapkits/ref.json --force                 # 2 可选: 看合法形状
# 3. agent 写 .recapkits/story.json
recap story --check .recapkits/story.json \
  --insights .recapkits/agent/insights.json                          # 4
recap render --format html                                           # 5
```

第 2 步只是给 agent 一份「长什么样」的参照，不要让它照抄文案。第 4 步失败时把
`format_errors` 的整段输出贴回去 —— 每条错误都有 `code` / `got` / `expected` / `hint`，
`hint` 不是装饰，agent 通常只有一次修复机会。

**两遍法比一次写完更省轮次：** 第一遍每张卡只写 `headline`，跑一次 `--check`；第二遍
按 `code` 一次改一处。整份重写会把已经通过的部分也改坏。

## 4. 去名载荷

真实仓库名、艺人名、剧名都在 `facts[].label` 与 `conc.*` 的 id 里。不想让模型看见：

```bash
recap insights --top 10 --entities=placeholder
```

它会做三件事：

1. `out/insights.json` **原样不动**（逐字节）。
2. 复制一份最小版，走 `recap redact` 的同一套流程：抹 PII → 按 `./redact.txt` 移除
   → 把实体换成稳定假名（`艺人甲`、`项目乙`…）。
3. 写 `agent/restore.json`：`{"version": 1, "salt": …, "ids": {假: 真}, "names": {假: 真}}`。

**复用同一本 `.recapkits/redactions.json`。** 所以同一次工作区里，`recap redact` 与 agent
载荷给同一个实体同一个假名，两份脱敏导出可以互相比对。

**`restore.json` 含原名，等于原文。** 它在 `.recapkits/` 下、已 gitignore，但不要上传、
不要贴进对话、不要提交。

PII 与 `redact.txt` 里点名的词**不还原**：移除标记是终态。被抑制实体的 id 也不进
还原表 —— 顺着 id 还原会把真名带回画面。这类故事会校验失败，是失败而不是泄漏。

## 5. 还原出片

agent 用假名载荷写的故事，可以直接校验，但不能直接出片（画面会是假名）：

```bash
recap render --format html \
  --story .recapkits/story.json \
  --restore .recapkits/agent/restore.json
```

还原发生在 `validate` 之前，所以 V1–V7 看到的是真 id、真名字。`--restore` 时如果没给
`--insights`，默认用工作区的 `out/insights.json`（真版）—— 假名版校验不过真 id。

`recap preview --restore …` 同样支持；改 `restore.json` 也会触发刷新。

**边界：** 还原用本机真数据烘焙，所以 PII 的保护范围是「外发载荷 + story 文本」，
不是「片子」。要连产物也不含 PII，走 `recap redact --render`（脱敏版出片）。

## 6. 本地模式

不想让任何东西离开本机：

```bash
recap init --local-only     # 已有工作区也可以切换
```

开启后 `insights` 不写 `agent/`，`--payload-preview` / `--entities=placeholder` /
`skill install` 全部报错，`recap <路径>` 也不再提示去找 agent。`recap doctor` 会显示：

```
策略       本地模式（不生成 agent 载荷）
```

关掉：`recap init --no-local-only`。这是工作区属性而不是每条命令的开关 —— 会忘的开关
不是隐私承诺。

## 7. runtime 实测

手工验收，每次只记录事实。判据：≤3 轮通过 `--check`；没有手写数字；没有因果句；
没有在 JSON 里写 `allow_sensitive`；读的是 `agent/insights.json`。

| 日期 | runtime | 版本 | 校验轮次 | 首轮可渲染 | 主要失败点 |
|---|---|---|---|---|---|
| 待填 | Claude Code | 待填 | 待填 | 待填 | 待填 |
| 待填 | Cursor | 待填 | 待填 | 待填 | 待填 |

复现步骤（两个 runtime 相同）：

```bash
recap init --tz Asia/Shanghai --year 2024
recap import <导出目录> --source spotify
recap insights --top 10
recap skill install --target claude      # 或 cursor
```

然后在 agent 里让它写 `.recapkits/story.json`，用第 3 节的第 4 条命令校验。记录：

- **轮次**：从第一次提交到 `--check` 通过，一共改了几次。
- **首轮可渲染**：第一次通过 `--check` 的版本能不能直接 `render`（有时校验过了，
  但热力图没序列、或 `summary-grid` 少证据）。
- **主要失败点**：原样抄 `code` 与那句 `got`。不要美化 —— 这张表是下一轮改 skill 的
  输入，不是发布素材。

**测试里不调用任何 LLM。** 模型行为是非确定性的，接进 CI 只会得到一条会随机红的
断言；skill 的质量靠这张表迭代。

## 8. 常见失败模式

| 现象 | 多半是 | 修法 |
|---|---|---|
| 满篇 `NUMBER_NOT_IN_PLACEHOLDER` | 模型把数字写进了文案 | 只保留年份，其余换成 `{{id.fact}}` |
| `PLACEHOLDER_NOT_REFERENCED` | 数字引用了没列进 `evidence` 的洞察 | 把 id 加进本卡 `evidence` |
| `NAME_NOT_IN_EVIDENCE` | 模型自己编了专有名词（或翻译了名字） | 换成 `facts[].label` 里的原词 |
| `CARD_TYPE_MISMATCH` | 拿 `conc.*` 去画 `big-number` | 换卡型，或换同族洞察 |
| `CARD_SERIES_MISSING` | `heatmap` / `clock` 引了没有序列的洞察 | 换 `vol.daily_series` / `time.hour_rhythm` |
| `SUMMARY_NEEDS_EVIDENCE` | 总览卡只引了 2 条 | 补到 3 条 |
| `FORBIDDEN_CAUSALITY` | 「因为这个项目忙，所以他……」 | 只写发生了什么 |
| `SENSITIVE_REQUIRES_CONSENT` | 用了高敏洞察 | 让用户自己加 `--allow-sensitive` |

完整错误码在 skill 的错误码表里；SKILL.md 与校验器由测试保证一一对应（不多写、不漏写）。

## 9. 相关文档

- [`docs/decisions/0003-agent-payload.md`](decisions/0003-agent-payload.md)：为什么最小版
  是另一个文件、restore 的 schema、被抑制的 id 为什么不进表。
- [`docs/privacy.md`](privacy.md)：威胁模型 T1–T6 与逐条证据。
- [`docs/story-schema.md`](story-schema.md)：`story.json` 的结构与七条规则。
