# 隐私：威胁模型与证据

这份文档只回答两个问题：数据会去哪里，以及凭什么相信。每条控制都指向一个能在
`pytest` 里跑的测试名；没有证据的就写「未做」，不写成已完成的承诺。

## 1. 威胁模型 T1–T6

| # | 对手 | 它能做什么 | 本阶段的控制 | 证据 |
|---|---|---|---|---|
| T1 | **我们自己** | 想收数据就得先有服务器、端点或存储桶 | 一个都没有。`src/` 里出现 URL 字面量或出站客户端，CI 直接失败 | `test_core_has_no_outbound_addresses` |
| T2 | **用户的模型服务** | 用 agent 写故事时会收到载荷 | 三层，默认最严：只写最小版（删 `score_parts` / `evidence_sql` / `evidence_rows`）；`--entities=placeholder` 换成与 `recap redact` 同一本盐的假名；`--local-only` 完全不生成外发载荷。还原只发生在 `render` / `preview` 的数据层，PII 与被抑制的词不进还原表 | `test_insights_writes_a_smaller_agent_payload`、`test_the_agent_payload_can_validate_its_own_story`、`test_the_agent_payload_has_no_real_names`、`test_a_suppressed_name_never_comes_back`、`test_local_mode_writes_no_agent_payload` |
| T3 | **网络** | 被动观测 | 完整链路在只有 loopback 的 netns 里跑通，HTML 与联网时逐字节相同 | `test_full_chain_is_byte_identical_without_network` |
| T4 | **视频的观众** | 看到渲染出来的一切 | `recap redact` 换名/移除/清 PII；高敏洞察需 `--allow-sensitive`；PNG 清 `tEXt`/`zTXt`/`iTXt`，MP4 清 `udta` | `test_redacted_pair_has_no_urls_paths_or_home_dirs`、`test_redacted_pair_passes_the_full_validator`、`test_strip_text_chunks_drops_metadata_only`、`test_mp4_structure_is_verified` |
| T5 | **共用/借用设备** | 读取构建目录 | 所有产物只在当前目录的 `.recapkits/`，没有全局缓存；`init` 把 `.recapkits/` 写进 `.gitignore` | `test_init_writes_config_and_gitignore` |
| T6 | **未来** | 读到长期留存的数据 | 一个构建目录，没有历史、没有索引、没有后台进程；全项目只有一个命令监听端口，且必须绑 `127.0.0.1` | `test_only_the_preview_server_opens_a_port`、`test_the_preview_server_binds_loopback_only` |

T2 的三层控制对应三种场景：

- **默认**：`recap insights` 每次写两份。`out/insights.json` 给渲染，`agent/insights.json`
  给模型。后者删掉 `score_parts`（打分过程）与 `evidence_sql` / `evidence_rows`（内部
  审计串），保留 `series` 是因为 heatmap / clock 的校验需要序列 —— 没有它，agent 拿到
  的载荷校验不了自己写的故事。它仍是一份合法的 `insights.json`。
- **去名**：`--entities=placeholder` 把实体名与 `conc.*` 的 id 段换成假名，并与
  `recap redact` 共用 `.recapkits/redactions.json` 这一本盐，所以两份脱敏导出可以比对。
  原名留在 `agent/restore.json`，它**等于原文**，不能分享。
- **不出门**：`recap init --local-only` 之后不再写 `agent/`，`--payload-preview`、
  `--entities=placeholder`、`skill install` 全部报错。这是工作区属性，不是每条命令的
  开关 —— 会忘的开关不是隐私承诺。

还原只发生在 `render --restore` 与 `preview --restore`，位置在 `validate` 之前：渲染层
拿到的是烘焙后的字符串，哪一段是假名已经丢了，漏一层就是原名泄漏到画面里。

**PII 与 `redact.txt` 里点名的词不进还原表**，被抑制实体的 id 也不进 —— 顺着 id 还原
等于绕过抑制表，真名会随真 insights 的 `label` 回到画面。这类故事会校验失败，是失败
而不是泄漏。设计细节见 [`decisions/0003-agent-payload.md`](decisions/0003-agent-payload.md)。

`render --restore` 用本机真数据烘焙，所以 PII 的保护范围是「外发载荷 + story 文本」，
不是「片子」。要让产物也不含 PII，用 `recap redact --render`。

## 2. `recap redact` 做了什么

读工作区的 `insights.json` 与 `story.json`，写 `.recapkits/redacted/` 下的同名两份。
**两份必须同时写**：故事的占位符在烘焙时从 insights 取数，只改文案会被旧数据原样
带回。写盘前再验一次「每个占位符都能在新 insights 里解析」；失败就不落盘。

四个阶段，顺序即保证：

1. **结构化 PII**：邮箱、E.164 电话、URL、IPv4/IPv6、经纬度、`@handle`、卡号
   （Luhn）、IBAN（mod-97）、绝对路径（盘符 / `~` / `/home` / `/Users`）。
   校验位是真的算过的 —— 16 位纯数字的播放时长不该被当成卡号。
2. **用户抑制表**：`./redact.txt`，一行一个词，`#` 开头忽略，大小写不敏感，
   长词先替换（「张三丰」不会被「张三」先吃掉）。命中就整体换成「已移除」，
   不再分配假名 —— 用户点名要它消失，不是要它换个名字。
3. **一致化假名**：`conc.*` 的 Top-5 实体与 id 段。假名由
   `HMAC-SHA256(salt, name)` 的字节序分配序号，序号用天干（甲、乙、丙…）而不是
   阿拉伯数字 —— 假名会作为 `label` 进文案，而 V2 会拦手写数字。
4. **审计**：`--report` 按类别打印计数；样本只在 stderr 是 TTY 时打印，重定向到
   文件或 CI 日志时只有计数。报告不回显 `redactions.json` 的内容。

**id 与标题一起换。** `conc.top_entity:repo:%54he%20%4didnight:2024` 的实体段就是
`The Midnight`；只改 label 不改 id，等于把实体名写进了要分享的文件。重写后的 id
仍匹配 `[a-z0-9_.:%-]+`，`story --check` 照常通过。

## 3. `recap redact` 没做什么

- **不推断人名。** 没有 NER。中文人名若不在 `redact.txt`、也不在 `conc.*` 的实体表
  里，不会被处理。这是刻意的：猜错名字比漏掉更糟。
- **不识别照片、人脸、声纹。** 没有这类输入。
- **不处理聊天正文。** 没有聊天适配器；阶段 8 的三个源都不含正文。
- **不重写 `insights.md`。** 那个文件仍是原名版；要分享的是 `redacted/` 目录里的
  两份 JSON，或由它们渲染出的 `-redacted` 片子。把 `out/insights.md` 直接发出去
  等于绕过了整个流程。
- **不做匿名化保证。** 数字、日期、排名、时间分布仍是真实的。换掉名字只挡住
  「这是谁」，挡不住「这是一个 2024 年深夜活跃、集中在某个项目上的人」。样本越小，
  反推越容易。
- **不覆盖原文件。** `--out` 默认 `.recapkits/redacted/`；`--render` 的产物名带
  `-redacted`，工作区里正常渲染的 HTML / MP4 不会被覆盖。

## 4. 假名的稳定性

同一份 `redactions.json`（盐 + 映射）下，两次脱敏的产物逐字节相同
（`test_two_runs_write_identical_bytes`），所以两份脱敏导出可以互相比对。

换一台机器、删掉 `.recapkits/`、或映射文件损坏后重建，序号会重排；报告里会写
「首次生成盐」或「使用临时盐」。**`redactions.json` 是「原名 → 假名」的完整映射，
等于原文**，它和 `insights.json` 一样不能分享；分享的是 `redacted/` 目录里的两份。

「实体替换」那一行是**被 `redact.txt` 移除的实体数 / 发现的实体数**。超过 80% 会
提示可能过度脱敏 —— 抑制表写得太宽时，故事会变成一串「已移除」，只有用户能判断
哪个名字其实可以留。

## 5. 出网证据的范围

`tests/unit/test_offline_egress.py` 在 `unshare -rn` 建的网络命名空间里跑完整链路：

```text
init -> import spotify -> insights -> story --auto -> render --format html
```

- 断言退出码为 0，**并且** HTML 的 sha256 与联网时相同。后者比「命令成功」更强：
  它排除了「渲染时悄悄取了远程字体/远程 CSS，失败后回退」这种情形。
- 它证明的是：**这些命令的内容不依赖网络**。
- 它**不是**抓包证明。DNS 查询、失败的连接尝试都不在它的观测范围内；eBPF /
  tcpdump 需要 root 与平台特定工具，本阶段不做。真正的「零外联」判据仍是源码扫描
  （`test_core_has_no_outbound_addresses`）与「产物里没有 URL」
  （`test_render_produces_self_contained_html`）。
- Windows 与 macOS 没有 `unshare`，Linux 上也可能被 AppArmor / 内核策略挡住：这些
  环境里本测试会跳过，本地预期 1 skipped。CI 的 `egress-gate` 先放开 Ubuntu 的
  AppArmor 限制，再用 `-rs` 把任何 skip 判成失败：证据缺了就是失败，不是跳过。

## 6. 已知缺口

- 没有 `recap clean`：删工作区目前就是 `rm -rf .recapkits`（或 Windows 资源管理器）。
- 真实导出核验尚未开始，见 [`adapters/VERIFICATION.md`](adapters/VERIFICATION.md)。
- 脱敏后的 PNG / MP4 仍可能通过画面内容泄露信息：脱敏保的是文案与文件名，
  不是像素。发布前逐张过一遍仍是必要的。
- agent skill 的模型行为只有人工验收（两个 runtime 的实测表在
  [`agent.md`](agent.md)），测试里不调用 LLM。
