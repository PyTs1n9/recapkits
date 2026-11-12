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
内置运行时）。产物本身没有运行时 JS —— 唯一的 `<script>` 是十行缩放代码，放在
`<head>` 里，不参与内容渲染。

**快速失败：** `require_node()` 在 `recap <路径>` 的第一条语句执行，早于工作区读取、
导入、建库与洞察计算；`recap render` / `recap preview` 也在读取 `story.json` 与
`insights.json` 之前执行。缺 node 或主版本 `< 22` 时立即退出，并提示可以先跑
`recap insights` 拿数据结论。理由：跑了三分钟解析、写完 61 MB 数据库才在最后一步
报"找不到 node"，比直接拒绝更糟。

**CI 防线：** render 测试用 `skipif(needs_node)`，无 node 的环境会全部跳过而仍然
"全绿"。`node-gate` job 用一条独立断言（`command -v node` + 主版本 ≥ 22 + 测试输出
不含 `skipped`）把这种假绿挡住。

## 资产同步

`renderer/dist/` 是构建产物（不入库），`src/recapkits/render/assets/` 入库，两者
由 `scripts/sync-renderer.py` 对齐；CI 用 `--check` 比较文件清单与 sha256。这条检查
防的是"改了前端忘了重建"—— 它一旦失效，用户拿到的 wheel 里会是旧界面，而且不会报错。
