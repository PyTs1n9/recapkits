# recapkits

本地优先、插件化的「任意数据的年度回顾」引擎。把数据导出丢进来，在本机生成可分享的竖向故事卡片。不上传、不遥测、不需要账号。

## 前置条件

- **Python 3.11+** 与 **uv**：`uvx` 会自行管理 Python，本机只需装 uv。
- **出 HTML / PNG / MP4 另需 Node 22+**。只算数据、只看 `insights.md`、只校验或自动生成
  `story.json` 时不需要 Node。
- **出 PNG 与 MP4 另需可选依赖 Playwright 与一个本机浏览器**：`uv sync --extra png`，
  截图会优先用已装的 Chrome / Edge，都没有才回落到 Playwright 自带的 chromium
  （约 150 MB）。只出 HTML 时不需要它。
- **出 MP4 另需 ffmpeg 5.1+**（系统依赖，不随包安装）：编码参数 `-fps_mode` 需要 5.1
  及以上。没有 ffmpeg 时 `recap render --format mp4` 会在读故事文件之前退出。

`recap doctor` 会打印实际生效的 node / ffmpeg 绝对路径与版本。找不到或版本不够时，
`recap <路径>`、`recap render` 会在读取任何导出数据之前立即停止，不会让你等完解析才看到失败。

## quickstart

一条命令：导入目录、算洞察、自动写一份能过校验的故事、出 HTML。

```bash
uvx recapkits ~/code
```

产物在 `.recapkits/out/recap-<年份>.html`：单文件、无外部请求，手机可直接打开。中途不需要
手写 `story.json` —— 缺故事时 `story --auto` 会从已选洞察规划六类卡片，跳过的卡会逐条打印
理由。已经存在手写故事时它不会覆盖。

想逐步控制，用分步命令：

```bash
uvx recapkits init --tz Asia/Shanghai --year 2024
uvx recapkits import ~/code --source git
uvx recapkits insights --top 10
uvx recapkits story --auto          # 或手写 story.json, 再 story --check
uvx recapkits render --format html --aspect 9:16
```

`render` 需要环境里有 **Node 22+**：HTML 由 `renderer/` 构建出的单文件渲染器产出
（Preact SSR），这样版式只有一份实现，PNG/MP4 截的是同一个页面。

### 数据源

`--source` 取 `auto | git | spotify | netflix`，默认 `auto`：按各适配器对目录的打分取最高者；
两个源同时命中且最高分与次高分相差不到 0.2 时**报错并要求显式指定** —— 宁可不猜，
也不按字母序偷选一个。

| `--source` | 目录里应该有什么 | 读哪些文件 |
|---|---|---|
| `git` | 一个仓库，或包含多个仓库的目录 | `.git` 里的提交记录 |
| `spotify` | Extended streaming history 解压后的目录 | `Streaming_History_Audio_*.json` |
| `netflix` | 导出包解压后的目录 | `ViewingActivity.csv`（可含 `Profiles/*/`） |

```bash
uvx recapkits init --tz Asia/Shanghai --year 2024
uvx recapkits import ~/Downloads/Spotify\ Extended\ Streaming\ History --source spotify
uvx recapkits import ~/Downloads/netflix-report --source netflix
uvx recapkits import ~/code --source git
```

三个源可以同时导入，洞察按源分开算。多源同时存在时，`story --auto` **只讲一个源的故事**：
按已选洞察的多数票定主源，其余源的卡不会混进同一份故事，而是进跳过表并写明「本回顾以
X 为主源，Y 的洞察未入卡」—— 把 git 的日序列和 spotify 的总时长拼在一起，读者无从解释。

口径（30 秒门槛、私密会话、续播去重、排除预告片等）以及「我们的数字和平台年度回顾
为什么不一样」，逐条写在 `docs/adapters/spotify/KNOWN_DIVERGENCES.md` 与
`docs/adapters/netflix/KNOWN_DIVERGENCES.md`。默认镜像平台口径，换口径的开关也记在那里。

每个源导入两次，事件数不变、`insights.json` 逐字节相同：`row_hash` 是幂等键。

想在改文案时实时看效果，用 `recap preview`（全项目唯一占用端口的命令）：

```bash
uvx recapkits preview          # 只绑 127.0.0.1，端口随机，按 Ctrl+C 停止
```

出图（每张卡一张 PNG，便于逐张发布）：

```bash
uvx --with 'recapkits[png]' recapkits render --format png --aspect 9:16   # 也支持 4:5
```

图写到 `.recapkits/out/cards/`（9:16）与 `.recapkits/out/cards-4x5/`（4:5），
文件名为 `recap-<年份>-01.png` …，序号补零，字典序就是卡片顺序。两个比例分开目录，
跑第二个不会把第一个覆盖掉。截图用真实浏览器渲染同一个页面：视口与舞台同宽、缩放固定为 1，并在
字体就绪、两帧绘制之后才按快门。同目录里上一轮的 `recap-*.png` 会先被清掉。

在本仓库里开发时用 `uv sync --extra png` 装可选依赖，命令换成 `./uv run recap render …`。

出视频（六张卡约 24 秒，1080×1920）：

```bash
uvx --with 'recapkits[png]' recapkits render --format mp4 --aspect 9:16
```

视频写到 `.recapkits/out/recap-<年份>.mp4`（4:5 为 `recap-<年份>-4x5.mp4`），帧率默认 30
（`--fps` 可改）。只有封面与大数字有 900ms 入场动画，其余四张单帧停留 —— 这是刻意的混合
采集：帧状态由浏览器的动画时钟驱动，同一份输入每次编码出的画面一致，不靠 sleep 凑帧。
`--out` 在 mp4 路径上是**文件**，与 PNG 的目录语义相反。MP4 复用 PNG 的截图链路，所以同样
需要 Playwright 与浏览器。

## 让 agent 写得更好

校验器能拦住不合格的文案，但它不负责写。把写故事的活交给 Claude Code / Cursor：

```bash
uvx recapkits skill install --target claude   # 或 cursor / agents / print
# 在你的 agent 里：按 recapkits skill，把 .recapkits/agent/insights.json 写成
# .recapkits/story.json
uvx recapkits story --check .recapkits/story.json --insights .recapkits/agent/insights.json
```

`recap insights` 会同时写两份：完整版在 `out/`（渲染用），最小版在 `agent/`（给模型）。
最小版删掉 `score_parts` / `evidence_sql` / `evidence_rows`，约小 15%，但仍是一份合法的
`insights.json`，agent 写完的故事可以直接用它校验。`recap insights --payload-preview`
先告诉你发出去多少字节。

不想让模型看见真实仓库名、艺人名：`recap insights --entities=placeholder` 会写一份假名
载荷并在 `.recapkits/agent/restore.json` 留还原表；出片时
`recap render --restore .recapkits/agent/restore.json` 把名字换回来。**还原表含原名，
等于原文，不要分享。** 完全不想外发就 `recap init --local-only`。

细节、失败模式与两个 runtime 的实测表见 [`docs/agent.md`](docs/agent.md)。

## 已知限制

- **生僻字回退系统字体。** 随包的是 GB/T 2312 一级字（3755 个）+ ASCII + 常用标点；二级字
  与「龘」这类生僻字会用系统字体渲染。版式不会崩（行盒按回退字形计算），但那一两个字的风格
  与随包字体不一致，在不同机器上也可能略有差异。仓库名、项目名里出现生僻字时会遇到。
- **播客与有声书计入时长，但不进「最多艺人」。** Spotify 导出里这几类行的
  `master_metadata_*` 全为 `null`；它们仍是真实的收听，所以算进总时长与事件数，只是不产生
  艺人实体。把它们聚成一个「（未命名）」会让榜单变成一句假话。
- **Netflix 导出没有流派元数据。** 从片名结构反推出来的口味结论一律不出卡；`Title` 里的季与集
  分开存放，榜单按剧集而不是按季排名。
- **时区改变结果，这是预期。** spotify 与 netflix 的导出只带 UTC，源不带偏移，本地小时由
  `init --tz` 决定。同一份导出分别按 `Asia/Shanghai` 与 `America/New_York` 导入，
  `time.hour_rhythm` 的深夜占比必须不同；两次相同说明偏移被错写成了 0。
- 不做音频；不做 1:1 比例；只有 `neon` 一套主题。

## 改渲染器

```bash
pnpm --dir renderer install
pnpm --dir renderer build
python scripts/sync-renderer.py    # 把 dist/ 同步到 src/recapkits/render/assets/
```

`--check` 模式只比较两侧的文件清单与 sha256，CI 用它守住"改了前端忘了重建"。

字体由 `python scripts/build-fonts.py` 生成（dev 依赖里有 fonttools 与 brotli）：按固定
URL + sha256 取源字体，子集化成两份 WOFF2，再转 base64 入库。`--check` 只校验 manifest
与文件哈希，不下载；同样的输入跑两次，产物字节相同。

改完版式跑一次 `./uv run pytest -m design`：溢出、安全区、对比度三条断言会在真实
浏览器里重测六张卡 × 两个比例（需要 Node、Playwright 与一个浏览器）。安全区容差已经是
0，内容侵入 1px 就会失败。

## 本地工具链

uv 跟着项目走，不依赖全局安装：

```bash
./uv sync                 # Git Bash / WSL：仓库根的 uv 入口
uv sync                   # cmd：在仓库根目录会命中 uv.cmd
. .\scripts\env.ps1       # PowerShell：把 .tools\uv 与 .venv 前置到本次会话 PATH
```

`.tools/` 不入库（uv 二进制约 31 MB）。换机后执行一次 `powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1` 即可就位并同步依赖。

提交前可以本地跑一次导出守卫：

```bash
./uv run python scripts/guard-exports.py
```

它拦两类事故：`tests/fixtures/` 之外的导出特征文件（`*Streaming_History_Audio*`、
`ViewingActivity.csv`、超过 1 MB 的 `export.xml`），以及 fixture 里的邮箱、非文档网段
IPv4 与高熵令牌。CI 每次都跑，本地跑是为了在 `git add .` 之后、推送之前就发现。

## 隐私

全程在本机完成：不上传、不遥测、不登录，核心代码不发起任何网络请求。所有中间产物只落在当前目录的 `.recapkits/`，可随时删除。

这条不是口号：`tests/unit/test_core_is_offline.py` 扫 `src/` 下全部 `.py` 与 `.mjs`，
禁止网络地址与出站客户端（`urllib.request`、`http.client`、`requests` 等），本地时间只允许
经 `tz.py`，并且只允许 `preview` 一个文件占用端口、必须绑 `127.0.0.1`。CI 每次推送都跑。

`tests/unit/test_offline_egress.py` 进一步在只有 loopback 的网络命名空间里跑完整链路，
要求 HTML 与联网时逐字节相同；CI 的 `egress-gate` 不允许它被跳过。

发布前生成一份可分享的脱敏版：

```bash
uvx recapkits redact           # 写 .recapkits/redacted/{insights,story}.json
uvx recapkits redact --report  # 只审计：计数，TTY 下每类最多 5 个样本
uvx recapkits redact --render  # 顺手出 recap-<年份>-redacted.html 与 .mp4
```

它抹结构化 PII（邮箱、电话、URL、IP、坐标、卡号/IBAN、绝对路径）、按 `./redact.txt`
移除你点名的词、把 Top-5 实体换成稳定假名，并把 id 与占位符一起重写。不推断人名，
不识别照片，不处理聊天正文；数字与排名仍是真实的，换名字不等于匿名。
`redactions.json` 是完整的「原名 → 假名」映射，等于原文，不要分享它。
细节与逐条证据见 [`docs/privacy.md`](docs/privacy.md)。

要用 agent 写故事时，默认只交出 `agent/insights.json`（最小版）；`--entities=placeholder`
把它换成假名；`recap init --local-only` 则完全不生成外发载荷。这三层都有测试断言，
不是文档承诺。

## 非目标（v1）

不做托管服务与接收数据的网页；不做账号登录与抓取，只用官方导出与本地文件；不做移动端 App；不做 dashboard；不推断健康状况、精神状态或亲密关系——数据只描述行为，不解释人。

## 许可证

MIT，见 [LICENSE](LICENSE)。
