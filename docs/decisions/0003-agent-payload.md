# 0003 — agent 线：skill、最小载荷、去名与还原

- 状态：**已采纳**（2026-11-13，阶段 10）
- 影响范围：`recap skill install`、`recap insights --payload-preview` /
  `--entities=placeholder`、`recap init --local-only`、`recap render|preview --restore`、
  `src/recapkits/skill/`、`payload.py`、`redact/restore.py`

计划 §8.1 的威胁模型里，T2（用户的模型服务）在本阶段之前是**唯一没有控制、也没有
测试**的一条：用户只能把整份 `insights.json` 贴给模型，仓库名、艺人名、剧名全在里面。

## 决定一：skill 是随包的一份 Markdown

`src/recapkits/skill/SKILL.md` 随 wheel 发布，`importlib.resources` 读取。
`recap skill install` 只负责复制与拼 frontmatter，**不在运行时拼提示词**。

**理由：** skill 与校验器必须同源。拼出来的提示词无法在 CI 里被 lint，也无法保证
「示例里的写法真的能过 V1–V7」；校验器新增一个错误码而 skill 没跟上，用户会看到
agent 反复犯同一个错。

**硬约束：** ≤160 行 / ≤8 KB（`test_skill_stays_within_budget`）。计划 §6.7 的坑
是「skill 写太长被忽略」—— 一份会被跳过的 skill 等于没有。

**错误码覆盖是测试，不是文档承诺：** `test_every_validation_code_is_documented` 用
AST 扫 `src/` 里所有 `StoryError("CODE", ...)` 的第一个实参，与文档表格**双向**比对：
漏写会红，多写一个不存在的码也会红。用 AST 而非正则，是因为 `validate.py` 里每个
调用都跨行。

**内容顺序按 agent 的失败模式排**，不按模块结构：三句话 → 五条命令的循环 → 七条
硬规则 → 卡型速查 → 五种语气 → 两遍法 → 隐私 → 错误码表 → 一个最小故事。示例只留
一个最小故事，且它必须真的通过 `validate_story`（`test_example_cards_pass_the_validator`）。

**五种语气是文案配方，不是代码开关。** `deadpan`（默认）/ `warm` / `dry` /
`cinematic` / `playful` 只进 `meta.tone`，不改变校验行为。

## 决定二：install 只写当前项目，四个 target

| target | 落点 | frontmatter |
|---|---|---|
| `claude` | `.claude/skills/recapkits/SKILL.md` | 原样保留 `name` / `description` |
| `cursor` | `.cursor/rules/recapkits.mdc` | 换成 `description` / `globs:` / `alwaysApply: false` |
| `agents` | `./AGENTS.md` 的标记块 | 去掉 frontmatter，只留正文 |
| `print` | stdout | 原样输出，不写文件 |

**项目级而不是用户级：** skill 讲的是「这个工作区」的 `.recapkits/`；装到 `~/.claude`
会跨项目误导，也会在用户家目录留下我们无法测试的文件。

**幂等与冲突：** 内容相同打印 `未改动`；不同且没有 `--force` 就报错并给路径。
多个 target 一起装时**先预检冲突再落盘** —— 否则前一个已写、后一个报错，用户拿到
的是半成品加一句「加 --force」。

**`AGENTS.md` 是用户的文件：** 标记块 `<!-- recapkits:skill:start -->` …
`end` 之间的内容由我们管理，块外逐字节不变；写入前按字节读原文、探测原有行尾
（`\r\n` / `\n`），拼接与写回用同一种行尾。块内替换不需要 `--force`。

整文件 target 用 LF，由我们决定字节；`.gitattributes` 给 `SKILL.md` 锁了 `eol=lf`，
否则 Windows checkout 会装出与 Linux 不同的字节。

## 决定三：载荷最小化是另一个文件，不改 `insights.json`

`recap insights` 每次写两份：

| 文件 | 内容 | 谁用 |
|---|---|---|
| `.recapkits/out/insights.json` | 完整版，含 `series` / `score_parts` / `evidence_sql` | `render`、`redact`、`preview` |
| `.recapkits/agent/insights.json` | 最小版 | 用户自己的模型 |

**为什么不能裁完整版：** heatmap / clock 要 `series`，`--explain` 要 `score_parts`，
证据链审计要 `evidence_sql`。把完整版裁掉再让渲染去别处找数据，是把一个文件契约
拆成两个。

**保留：** `version` / `build_id` / `generated_from`；每条洞察的 `id`、`kind`、`source`、
`period`、`headline_fact`、`facts`、`score`、`novelty`、`sensitivity`、
`data_sufficiency`、`gated`、`caveats`、`series`。

**删除：** `score_parts`（`--explain` 专用）、`evidence_sql`（内部审计串）、
`evidence_rows`（同上）。**未知键一律丢弃**：外部 payload 可能有我们没见过的字段，
最小版不替它做决定。

**`series` 必须保留。** V3 要求 heatmap / clock 的被引洞察带正确轴的序列；去掉它，
这份「给 agent 的载荷」就校验不了它自己催生的故事 —— 一个必须先还原才能校验的
载荷是陷阱。skill 里明确写了：`series` 是渲染数据，不要读、不要引用。

它仍是一份合法的 `insights.json`，所以 agent 可以直接
`recap story --check story.json --insights .recapkits/agent/insights.json`。

**`--payload-preview` 是外发清单，三行：**

```
payload      20,408 字节 · 8 条洞察
agent        17,244 字节 · 8 条洞察（-16%）
删除         evidence_sql 2,255 · score_parts 746 · evidence_rows 163
```

分项按「删掉这个键能省下的字节」计（含键名、引号、逗号），三项之和**恰好等于**
总差值 —— 用户会拿计算器对。只算值的字节会低估 432 B。

`--payload-preview --json` 把最小版原样打到 stdout（这正是「贴给 agent」的那份），
其余情况只打计数与字段名，不打内容。非 TTY 也照常打计数：它不是样本，是用户主动
要的清单。

## 决定四：`--entities=placeholder` 复用 redact 的盐

```
recap insights --top 10 --entities=placeholder
```

写三份：

1. `out/insights.json`：**原样**，一个字节不改（测试逐字节比对）。
2. `agent/insights.json`：先最小化，再走 redact 的四阶段（PII → `redact.txt` → 假名）。
   实体名、`conc.*` id 段、`rank_*` 标题一起换。
3. `agent/restore.json`：

```json
{
  "version": 1,
  "salt": "…",
  "ids":   { "<假 id>": "<真 id>" },
  "names": { "<假名>": "<原名>" }
}
```

在 `.recapkits/` 下、已 gitignore；**它含原名，等于原文，不能分享**。

**为什么复用同一本 `redactions.json`：** 同一次工作区里，`recap redact` 与 agent 载荷
必须给同一个实体同一个假名，否则「两份脱敏导出可以比对」这条承诺就断了。

**PII 与抑制词不可还原。** 移除标记是终态：用户点名要消失的词、邮箱、路径，不该
因为 render 又回到片子里。还原表里不装它们，也不装被抑制实体的 **id** —— 顺着 id
还原等于绕过抑制表，真名会随真 insights 的 `label` 回到画面。这类故事会校验失败
（`CARD_UNKNOWN_INSIGHT` / `PLACEHOLDER_UNKNOWN_INSIGHT`），**是失败而不是泄漏**。

**还原只做两件事：** 把 story 的 `insight` / `evidence` / 占位符 id 映射回真 id；
把 copy 里占位符之外的假名按长度降序换回原名。未在表里的 id 与假名原样保留，交给
校验器报出可定位的错误（agent 编的拉丁词会走到这条路径）。

**为什么不在渲染层还原：** 渲染层拿到的是烘焙后的字符串，哪一段是假名已经丢了；
PNG / MP4 共用同一条截图链路，漏一层就是原名泄漏到画面里。还原必须发生在数据层、
`validate` 之前。

**还原点只有两个：** `recap render --restore PATH` 与 `recap preview --restore PATH`。
`story --check` 不需要还原 —— agent 直接用最小版 insights 校验。

**`--restore` 时会切换默认 insights。** 没显式给 `--insights` 时用工作区的
`out/insights.json`（真版），而不是故事同目录那份：`redacted/story.json` 旁边放的
是假名 insights，拿它校验还原后的真 id 只会得到一片 `CARD_UNKNOWN_INSIGHT`。

**性质测试：** `restore(redact(story)) == story`（对没有 PII / 抑制词的 fixture 逐字段
相等）。这比手写一份「agent 故事」更强：任何 copy 写法都能被这条性质覆盖。

## 决定五：`--local-only` 是工作区策略

`recap init --local-only` 把 `"local_only": true` 写进 `config.json`，`Workspace.local_only`
随配置加载（默认 `False`）。已有工作区上只改这一个字段，`tz` / `year` / `created_at`
一个字不动；`--no-local-only` 改回来；不带这个 flag 时 `init` 仍然「不覆盖」。

开启后：

- `insights` 不写 `agent/`；`--payload-preview` 与 `--entities=placeholder` 直接报错。
- `skill install` 报错，不写任何文件。
- `recap <路径>` 不再打印「把 insights.json 交给 agent」的提示。
- `doctor` 多一行：`策略       本地模式（不生成 agent 载荷）`。
- 已有的 `agent/` 不删除，只提示路径 —— 用户的数据，删不删由用户决定。

**为什么不做成每条命令的 flag：** 会忘。隐私承诺应该是工作区的属性，和 tz / year
一样；一次设置，所有命令一致。

**为什么已有工作区也能切换：** 否则阶段 8/9 建的工作区永远回不到本地模式。

## 决定六：验收分自动与人工两层

自动（CI 可跑）：install 的四个 target、幂等、标记块、`--force`、本地模式拒绝；
SKILL.md 的长度、小节、错误码全覆盖、五种语气；最小版的字段取舍、字节数、
`--payload-preview` 输出、`--json`；placeholder 的「真 insights 不变、零原名、restore
性质、渲染还原」；本地模式的四个入口。

人工（两个 runtime）：Claude Code 与 Cursor 各跑一次，记录校验轮次与首轮是否可渲染。
**测试里不调用任何 LLM**（D4）：模型行为只能人工验收，把非确定性接进 CI 只会得到
一条会随机红的断言。

判据：≤3 轮通过 `--check`；没有手写数字；没有因果句；读的是 `agent/insights.json`
而不是完整版；只说改了哪些文件。结果记在 [`docs/agent.md`](../agent.md) 的实测表里，
失败点原样记 —— 那张表是下一轮改 skill 的输入，不是发布素材。
