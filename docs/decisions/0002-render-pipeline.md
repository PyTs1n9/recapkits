# 0002 — 渲染管线：validate → bake → render

- 状态：**已采纳**（2026-11-11，阶段 5b）
- 影响范围：`recap render`、`recap preview`、`renderer/`、`story/bake.py`

## 决定一：渲染器不认识占位符

顺序固定为 **load → validate(V1–V7) → bake → render**：

- `validate` 先跑，所以报错指向原始文案与槽位，用户知道该改哪一句；
- `bake` 把每个 `{{insight_id.fact_key}}` 解析成 `facts[].display`，产出纯字符串；
- `render` 只接收已烘焙的字符串，TypeScript 侧没有一行占位符解析代码。

**理由：** 占位符语法若在两门语言里各写一遍，一定会漂移。而它的漂移不会崩溃，
只会表现为「校验通过但页面显示 `{{...}}`」—— 一种只有人眼看页面才能发现的失败。
把解析收敛到 Python 一处，这个失败模式在结构上不可能发生。

**代价与取舍：** 渲染器因此不能自己决定「显示哪个事实」。`big-number` 的巨型数字
由 bake 提供（主角洞察的 `headline_fact.display`），渲染器只负责排版。这是刻意的：
数据绑定属于管线，版式属于渲染器。阶段 6a 起，`big-number` 没有 `insight` 就没有数字，
借 `evidence` 承载数字的过渡通道已删除。

**防线：** `renderer/src/main.tsx` 的 `assertBaked` 会扫描所有字符串（含 ranking 的行与
summary-grid 的 fact），一旦发现 `{{` 或 `}}` 就直接失败。它不是占位符解析，而是
"你没跑 bake" 的显式报错。

## 决定一之补：`series` 只由 bake 搬运

`heatmap` 与 `clock` 需要序列，但渲染器仍然不查库、不重算：`bake_card` 把
`InsightRef.series` 原样搬进 `BakedCard.series`，只给这两种卡型。`ranking` 的
`rows` 与 `summary-grid` 的 `facts` 同理，都是 bake 从 `fact_list` 里整理出的纯字符串。

这条边界让"渲染器只读已烘焙数据"在新卡型上继续成立，也让 6c 的浏览器断言可以
只看 DOM，不需要再跑一遍 SQL。

## 决定二：字体确定性推迟到阶段 7（已由决定六取代）

阶段 5 的 `tokens.css` 用系统字体栈（Inter Tight / PingFang SC / Microsoft YaHei /
Noto Sans SC），没有 `@font-face`。当时的理由是：在浏览器里 CJK 字体本来就由系统提供，
随包字体只会让单文件变大；而 CJK 子集化需要按实际文案裁剪字形，是件正经工作。在还没有
像素输出的阶段为它付费没有回报。

阶段 6 的 PNG 与设计断言证明这个判断只对了一半：像素输出一旦出现，系统字体栈就让同一份
HTML 在 Windows 与 Linux 上落下不同的墨迹，边带断言被迫留 6px 容差。阶段 7 因此把字体
随包（见决定六），容差收回 0。

**当时的实测（Windows/YaHei，已作废）：** 巨型数字的字形墨迹底边落在 1593px，底栏在
1668px，安全区下沿 1680px；补偿值 `--display-baseline-shift` 为 0.12em。换成随包字体后
重测，墨迹底边仍是 1593px，但补偿值降到 0.073em（见决定六）。

## 决定三：渲染由 Node 执行，Python 只准备数据

`recap render` 调用 `src/recapkits/render/assets/cli.mjs`（Vite 的 SSR 单文件产物，
Preact 已打进 bundle）。Python 不拼 HTML 字符串。

**理由：** 版式只有一份实现。阶段 6 的 PNG 与阶段 7 的 MP4 截的就是同一个页面，
不需要维护两套几何。反之若 Python 拼模板，TS 组件就成了装饰品，两边必然分叉。

**代价：** `recap render` 需要环境里有 `node`。这是继 `git` 之后第二个外部依赖，
`doctor` 会报出它的**绝对路径与版本**（只报"可用"无法区分 nvm / 系统包管理器 / IDE
内置运行时）。产物本身没有运行时 JS —— 只有两段十几行的 `<script>`，都在 `<head>` 里：
一段按视口算缩放，一段在两帧之后写 `data-render-ready`（PNG 截图据此判断可以按快门）。
两段都不参与内容渲染。

**快速失败：** `require_node()` 在 `recap <路径>` 的第一条语句执行，早于工作区读取、
导入、建库与洞察计算；`recap render` / `recap preview` 也在读取 `story.json` 与
`insights.json` 之前执行。缺 node 或主版本 `< 22` 时立即退出，并提示可以先跑
`recap insights` 拿数据结论。理由：跑了三分钟解析、写完 61 MB 数据库才在最后一步
报"找不到 node"，比直接拒绝更糟。

**CI 防线：** render 测试用 `skipif(needs_node)`，无 node 的环境会全部跳过而仍然
"全绿"。`node-gate` job 用一条独立断言（`command -v node` + 主版本 ≥ 22 + 测试输出
不含 `skipped`）把这种假绿挡住。

## 决定四：PNG 用真实浏览器截同一个页面

`recap render --format png` 不重画，它把 `build_html()` 的产物落到临时文件，用 Playwright
打开、逐张 `.stage` 截图。**版式仍然只有一份实现**：截的就是用户能打开的那个 HTML。

**浏览器选择：** 先试本机 `chrome`，再试 `msedge`（Playwright 的 `channel` 参数），
都没有才回落到 Playwright 自带的 chromium，并明确提示这一步多占约 150 MB。理由是
开发者机器上普遍已有 Chrome/Edge，为一个截图动作再装一份浏览器没有意义。

**像素必须可预测，四件事缺一不可：**

1. 视口固定为舞台尺寸（`1080×1920` / `1080×1350`），`deviceScaleFactor: 1`；
2. 强制 `--stage-scale: 1`：页面里的 `fit()` 会按窗口把舞台再缩一次，缩放比例随窗口
   变化，像素就对不上设计稿了；截图后还会断言 PNG 的 IHDR 宽高，不符即报错；
3. 等三件事再按快门：`document.fonts.ready`、两帧 `requestAnimationFrame`、页面上的
   `data-render-ready` 标记。标记由产物里的第二个 `<script>` 在两帧之后写上，位置在
   `<head>`，不参与内容渲染。等一个 sleep 是碰运气，等标记是等事实；
4. 固定浏览器启动参数（`--disable-gpu` / `--disable-lcd-text` /
   `--font-render-hinting=none` / `--force-color-profile=srgb` /
   `--disable-partial-raster` / `--disable-skia-runtime-opts` / `--hide-scrollbars`），
   并断言舞台落在整数像素上。这些不是性能调优，是把"显卡、字体微调、色彩配置"三个
   变量从画面里拿掉。

**阶段 7 的结论：PNG 是字节级确定，不是像素容差。** 同一份 HTML 渲染两次，每个文件的
sha256 相同（`tests/unit/test_render_png_deterministic.py`）。`--hide-scrollbars` 让布局
宽度回到 1080，`translate(-50%)` 不再落在半像素上，截图矩形因而就是整数。这条确定性是
MP4 的前提：每一帧都是同一批截图的复用，帧哈希不稳就谈不上视频回归。

**元数据：** 截图会带 `tEXt` / `zTXt` 块（源路径、软件版本），产物不该泄露本机路径。
写盘前重编码，剥掉这三类文本块并保留其余块 —— 保留的块逐字节拷贝，CRC 不用重算。

**命名与清理：** `recap-<年份>-01.png` 起，序号补零，文件名的字典序等于卡片顺序。
写之前先删同目录的 `recap-*.png`：卡片变少时残留的旧图会让"文件数"撒谎。

**可选依赖：** Playwright 在 `[project.optional-dependencies].png` 里，核心依赖仍是零
第三方包。只出 HTML 的用户不该为 40 MB 的包付安装成本；缺它时报一句"uv sync --extra png"，
而不是 ImportError。

## 决定五：三条设计断言按真实像素判定

「看起来还行」不是验收标准。`pytest -m design` 跑三条会失败的断言，全部基于同一个
浏览器里的同一批截图（`tests/design/`）：每张卡拍三张图 —— 原图、文字全透明、去掉
卡片的空白舞台。

**一、溢出。** 横向用 `scrollWidth <= clientWidth + 1`；纵向用 `Range` 数**渲染后的
行数**，与槽位预算比（`sub` / `label` / `caveat` 两行，其余一行）。纵向不用
`scrollHeight`：当 `line-height` 小于字体墨迹比（Windows/YaHei 约 1.32em）时，Chrome
把字形墨迹的溢出也计入 scrollHeight —— 实测 72px/1.1 的「137次」是 client 79 /
scroll 87 / Range 墨迹 95，照搬这条判据会对每个正常文本块误报。覆盖这条的另一半是
"槽位盒子不得越过底栏与安全区"。

**二、安全区。** 四条边带（上下各 240px、左右各 72px）与空白舞台逐像素比对，CIELAB
Cie76 的 ΔE > 2 即失败。基准不能用单一色值：`--skin-bg-image` 是渐变，任何单色都会在
某一角误判；两张图相减，渐变本身抵消。这条抓到过真问题：ranking 的右对齐数值压在
1008px 那条线上、热图面板的外阴影横向漏进右带。

**三、对比度。** 在"文字全透明"那张图上取每个文字框的背景像素（取最亮的一个作最坏
情况），与 `getComputedStyle().color` 按 alpha 合成后算 WCAG：正文 4.5:1、大字号
（≥48px）3:1。用透明图而不是拼祖先链的 `background-color`，是因为舞台是渐变，拼出来
的值会偏。

**这三条为什么必须是像素**：估算与真实渲染的差异只在真实渲染里出现 —— 同一个字号在
不同字体下的墨迹宽度、以及阴影/抗锯齿这类"不是布局但会出界"的东西，只有像素看得见。

**CI：** `node-gate` 里多一步 `pytest -m design`，并和渲染测试一样断言输出不含
`skipped` —— 缺浏览器时跳过可以让套件"全绿"，那是最糟的一种绿。

## 决定六：字体随包，构建期子集化

`src/` 的硬约束是零第三方依赖（Windows 的 `tzdata` 除外）。因此**不能**在渲染时用
fonttools 按文案裁字形 —— 那会把 fonttools 变成运行期依赖，HTML 输出会因此要求用户装
一个 C 扩展。字体在提交前裁好，运行时只读两份纯 ASCII 文本。

**管线：** `scripts/build-fonts.py` 按固定 URL + sha256 取源字体（URL 钉在提交号上，
不是 `main`：上游改一次文件，sha256 就会失配，而失配必须是一次显式失败），子集化成
WOFF2，再转 base64 写入 `renderer/src/assets/*.b64`。`fonttools` 与 `brotli` 只在
`[dependency-groups].dev`，不进 `dependencies`、也不进 `[png]`。脚本幂等：同样的输入
跑两次，产物字节相同。

**为什么是 `.b64` + `?raw` 而不是二进制 `.woff2` + `?inline`：** `?raw` 是这个项目每天
都在用的机制；二进制资产要么依赖 vite 的 `?inline` 行为（版本相关，不是既有路径），
要么引入一个自定义插件。`.b64` 是纯 ASCII，`normalize()` 的 LF 处理顺手覆盖，产物仍然
只有 `dist/cli.mjs` 一个文件，`sync-renderer --check` 的文件清单逻辑一行都不用改。

**字形集：** GB/T 2312 一级字（3755 个）+ ASCII + 常用标点，共 3883 个码位、3932 个
字形（含复合字形的组件）。一级字覆盖现代中文日常文本 99% 以上；**二级字与生僻字回退
系统字体**，这是已知限制，写在 README 里而不是只留一句代码注释。

**实测与预算：**

| 项 | 上限 | 实测 |
|---|---|---|
| CJK WOFF2 | 1.6 MB | 1,024,896 B |
| 拉丁 WOFF2 | 60 KB | 25,556 B |
| `cli.mjs` | 2.4 MB | 1,467,086 B |
| 含字体的单文件 HTML | 2.6 MB | 1,429,318 B（三卡 9:16） |
| wheel | 4 MB（R12 原定 3 MB） | **1,178,297 B** |

R12 原定 wheel < 3 MB，阶段任务书担心随包字体与它冲突。实测并不冲突：WOFF2 本身已经
是压缩格式，base64 后的 1.4 MB 进 wheel 只占 1.18 MB。因此**不把 R12 放宽到 4 MB**，
3 MB 的口径原样保留；4 MB 只是任务书给的兜底上限。

**字族顺序：** `"Inter Tight", "Noto Sans SC", sans-serif`。Inter 先吃掉数字与拉丁
（巨型数字的字重与 tabular-nums 依赖它），Noto 逐字回退接住 CJK。**不列任何系统字族**：
留着就等于允许回退，而回退正是跨平台差异的来源。

**基线补偿重测：** `--display-baseline-shift` 从 0.12em 降到 **0.073em**。随包字体下
（1080×1920）字形墨迹底边 1593px、底栏 1668px、安全区下沿 1680px，与旧值的视觉关系
一致，但补偿量小了 15px —— 这就是"换字体会动版式"的具体表现。4:5 下按 em 等比缩放，
墨迹底边 1046px、底栏 1100px。

**容差归零：** `SAFE_BAND_TOLERANCE` 6 → 0。随包字体让两个平台读同一份字形，容差的
前提消失。变异验证：给 `ranking` 注入 `padding-left: 71px`（向内侵入 1px），9:16 与
4:5 分别报 ΔE 129.3 / 129.5，断言失败；还原后全绿。最终 12 张卡（6 型 × 2 比例）的
最大边带 ΔE 为 **0**，最低对比度 **4.83:1**（阈值 4.5:1）。

归零过程中修了两处真实几何问题：封面 3px 基座的 2px 圆角会把抗锯齿溢出 1px 进左边带
（改方端）；热图面板的黑色外阴影在近黑底上目视不可见，却横向溢出 7px、ΔE 1.05（去掉
外阴影，面板靠描边、渐变与内高光成立）。

**许可：** Noto Sans SC 与 Inter Tight 均为 SIL OFL 1.1。`build-fonts.py` 按固定 URL
取两份 OFL 文本，写到 `renderer/public/fonts/`，由 vite 拷进 `dist/`，再随
`sync-renderer.py` 进 wheel；同目录的 `NOTICE.txt` 记录家族名、来源 URL、源 sha256、
子集范围与产物字节数。

## 决定七：MP4 的帧是纯函数

`recap render --format mp4` 不重画、不录屏：它打开同一份 HTML，把
`document.getAnimations()` 全部 `pause()`，再把 `currentTime` 设成 `N × 1000 / fps`，
逐状态截图，最后交给 ffmpeg。不用 `sleep`、不用 `animation-delay` 凑帧 —— 后两者都会让
"第 N 帧"取决于机器快慢。

**只有两处动画。** `cover` 的入场（kicker → 细线 → 年份 → 基座 → 副标题）与
`big-number` 的数字入场，各 900ms；其余四张单帧复制。这是 §3.8 的混合采集策略，也是
20 小时做得完的前提。动画只在 `html[data-motion="on"]` 时定义，且
`animation-play-state: paused`：HTML 打开后是静态的（`data-motion` 缺省），不会自己动；
MP4 采集前显式打开它。有一条测试断言"没有 data-motion 时页面上零动画"。

**停留用 concat 的 `duration` 表达，不复制帧。** 6 张卡 × 1080×1920 的 PNG 若按 30fps
复制停留帧，临时目录会到 1 GB，而那些帧本来就是同一位图的重复。实测：六卡 24.3s /
729 帧，9:16 为 1,143,911 B，4:5 为 865,530 B。

**`-frames:v` 是必须的。** concat 会忽略最后一帧的 `duration`，补一帧重复文件又会多出
**一整帧**：147 帧的片子实测出来 148 帧，4.900s 变 4.934s。按时间轴总帧数截断之后，
成片时长才是精确的 `帧数 / fps`。

**ffmpeg 与 node 同等待遇。** 不引入 `imageio-ffmpeg`（那是把二进制塞进依赖）；
`doctor` 报绝对路径与版本；`--format mp4` 在读 `story.json` 之前调用
`require_ffmpeg()`，缺工具立即退出。`-fps_mode` 需要 5.1+，不为老版本维护 `-vsync`
分支。

**结构自检不引入 ffprobe。** `mp4box.py` 用 stdlib 解析顶层 box，断言四件事：`moov`
在 `mdat` 之前（`+faststart` 生效）、`mvhd` 时长与时间轴误差 ≤ 1 帧、`tkhd` 宽高就是
1080×1920 或 1080×1350、`udta` 里没有条目且全文不含 `encoder` / `©too`。

最后一条要说清一个实测事实：ffmpeg 8.1.1 的 mp4 muxer **无条件**写一个空的
`udta/meta/hdlr(mdirappl)/ilst` 容器，`-map_metadata -1` 与 `bitexact` 都去不掉它。
删掉它需要重写 `stco` 的 chunk 偏移（`moov` 在 `mdat` 之前），代价远大于收益。所以
断言落在"容器里没有条目"而不是"没有容器"—— 空容器不携带本机路径或软件版本，而
`encoder` / `©too` 两条文本标记仍然逐字节检查。

## 资产同步

`renderer/dist/` 是构建产物（不入库），`src/recapkits/render/assets/` 入库，两者
由 `scripts/sync-renderer.py` 对齐；CI 用 `--check` 比较文件清单与 sha256。这条检查
防的是"改了前端忘了重建"—— 它一旦失效，用户拿到的 wheel 里会是旧界面，而且不会报错。

字体接进来之后，`assets/` 里是 4 个文件：`cli.mjs`（字体已 base64 内联）与
`fonts/` 下的两份 OFL 加一份 NOTICE。许可证之所以走 `renderer/public/fonts/` →
`dist/fonts/` → `assets/fonts/`，而不是直接放进 `assets/`：`sync-renderer.py` 会用
`dist/` 整个替换 `assets/`，任何只存在于 `assets/` 的文件都会被下一次同步删掉。
