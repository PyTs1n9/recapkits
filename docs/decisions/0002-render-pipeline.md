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

## 决定二：HTML 阶段不解决字体确定性

`tokens.css` 用系统字体栈（Inter Tight / PingFang SC / Microsoft YaHei / Noto Sans SC），
**没有 `@font-face`，这是故意的**。字体确定性与 CJK 子集化推迟到阶段 7。

**理由：** 在浏览器里 CJK 字体本来就由系统提供，随包字体只会让单文件变大；而 CJK
子集化需要按实际文案裁剪字形，是件正经工作。在还没有像素输出的阶段为它付费没有回报。

**已知后果：** `big-number` 巨型数字的视觉底边与行的距离是字体相关的。当前用
`line-height: 0.9` + `--display-baseline-shift: 0.12em`，实测（1080×1920，
Windows/YaHei）字形的墨迹底边落在 1671px，安全区下沿是 1680px。补偿值是 token，
换字体后只重测这一个值，由阶段 6c 的安全区断言验证，不需要肉眼比对。

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

**像素必须可预测，三件事缺一不可：**

1. 视口固定为舞台尺寸（`1080×1920` / `1080×1350`），`deviceScaleFactor: 1`；
2. 强制 `--stage-scale: 1`：页面里的 `fit()` 会按窗口把舞台再缩一次，缩放比例随窗口
   变化，像素就对不上设计稿了；截图后还会断言 PNG 的 IHDR 宽高，不符即报错；
3. 等三件事再按快门：`document.fonts.ready`、两帧 `requestAnimationFrame`、页面上的
   `data-render-ready` 标记。标记由产物里的第二个 `<script>` 在两帧之后写上，位置在
   `<head>`，不参与内容渲染。等一个 sleep 是碰运气，等标记是等事实。

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

**这两条为什么必须是像素**：估算与真实渲染的差异只在真实渲染里出现 —— 同一个字号在
不同字体下的墨迹宽度、以及阴影/抗锯齿这类"不是布局但会出界"的东西，只有像素看得见。

**CI：** `node-gate` 里多一步 `pytest -m design`，并和渲染测试一样断言输出不含
`skipped` —— 缺浏览器时跳过可以让套件"全绿"，那是最糟的一种绿。

## 资产同步

`renderer/dist/` 是构建产物（不入库），`src/recapkits/render/assets/` 入库，两者
由 `scripts/sync-renderer.py` 对齐；CI 用 `--check` 比较文件清单与 sha256。这条检查
防的是"改了前端忘了重建"—— 它一旦失效，用户拿到的 wheel 里会是旧界面，而且不会报错。
