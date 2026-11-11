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
由 bake 提供（主角洞察的 `headline_fact.display`，没有主角时退回首条 `evidence`），
渲染器只负责排版。这是刻意的：数据绑定属于管线，版式属于渲染器。

**防线：** `renderer/src/main.tsx` 的 `assertBaked` 会扫描所有字符串，一旦发现 `{{`
或 `}}` 就直接失败。它不是占位符解析，而是"你没跑 bake"的显式报错。

## 决定二：HTML 阶段不解决字体确定性

`tokens.css` 用系统字体栈（Inter Tight / PingFang SC / Microsoft YaHei / Noto Sans SC），
**没有 `@font-face`，这是故意的**。字体确定性与 CJK 子集化推迟到 PNG/MP4 阶段（阶段 6/7）。

**理由：** 在浏览器里 CJK 字体本来就由系统提供，随包字体只会让单文件变大；而 CJK
子集化需要按实际文案裁剪字形，是件正经工作。在还没有像素输出的阶段为它付费没有回报。

**已知后果：** `big-number` 巨型数字的视觉底边与行的距离是字体相关的。当前用
`line-height: 0.9` + `0.12em` 下移补偿，实测（1080×1920，Windows/YaHei）字形的墨迹
底边落在 1671px，安全区下沿是 1680px。阶段 6 随包字体落地后需要重测这一个值 ——
注释写在了 `base.css` 里，改那里一处即可。

## 决定三：渲染由 Node 执行，Python 只准备数据

`recap render` 调用 `src/recapkits/render/assets/cli.mjs`（Vite 的 SSR 单文件产物，
Preact 已打进 bundle）。Python 不拼 HTML 字符串。

**理由：** 版式只有一份实现。阶段 6 的 PNG/MP4 截的就是同一个页面，不需要维护两套
几何。反之若 Python 拼模板，TS 组件就成了装饰品，两边必然分叉。

**代价：** `recap render` 需要环境里有 `node`。这是继 `git` 之后第二个外部依赖，
`doctor` 会报出它的可用性。产物本身没有运行时 JS —— 唯一的 `<script>` 是十行缩放
代码，放在 `<head>` 里，不参与内容渲染。

## 资产同步

`renderer/dist/` 是构建产物（不入库），`src/recapkits/render/assets/` 入库，两者
由 `scripts/sync-renderer.py` 对齐；CI 用 `--check` 比较文件清单与 sha256。这条检查
防的是"改了前端忘了重建"—— 它一旦失效，用户拿到的 wheel 里会是旧界面，而且不会报错。
