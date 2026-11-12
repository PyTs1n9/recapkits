# 阶段 6：四个卡片类型 + PNG 输出 + 设计断言

阶段 5 已验收：112 测试绿、bundle 27 KB 零网络 API、HTML 8,939 字节零外链零 `{{`、DOM 为 8 个独立舞台。顺带修的两个缺陷（占位符缺 `-`、Windows 换行）都是真问题，判断准确。

本阶段先补齐 §0.1 / §0.2 两个前置，再做 §0.3 的契约变更，最后做 6a；6b / 6c 排在其后。顺序不是建议，是依赖关系：没有 `series` 契约，`clock` 与 `heatmap` 只能把序列塞进 `display`，那是不可逆的技术债。

---

## 本轮四项决定（先读这一节）

这四条是已经拍板的结论，实施时不再讨论；下面的细节章节只负责把它们展开成可执行的验收。

### 决定 1：接受 Node 依赖对 D2 的偏离，但必须付四个代价

D2 原文是「渲染器构建产物打进 wheel，**终端用户不需要 Node**」。现在 `render_html()` 要 `shutil.which("node")`，等于任何渲染都需要 Node。这是实质偏离，不是实现瑕疵。

**决定：接受，不返工。** 目标受众是开发者（Node 普遍存在）；把 JS 运行时打进包要 +30 MB，换来的只是「非开发者少装一个东西」，而他们本来也要装 uv。替代方案（用 Playwright 跑 bundle）会把「轻量路径」变成「必须下 Chromium」，更差。

接受偏离必须支付四个代价，缺一不可：

1. **快速失败。** `recap <路径>`（无子命令）的第一条语句必须是 `require_node()`，早于工作区读取、导入、建库与洞察计算。缺 node 时立即退出，输出固定为：

   ```
   渲染需要 Node 22+。检测未通过：找不到 node。
   装好后再跑一次；或先用 `recap insights` 拿到数据结论（不需要 Node）。
   ```

   `recap render` 与 `recap preview` 同样在读取 `story.json` / `insights.json` 之前检查。**绝不能**跑完三分钟解析、写完 61 MB 数据库，才在最后一步失败。

2. **README 首屏写清楚。** 在「前置条件」一节写「Python 3.11+ / uv；出 HTML、PNG、MP4 另需 Node 22+」，位置在 quickstart 之前。不要藏进 FAQ 或 troubleshooting。

3. **`doctor` 报路径与版本。** 输出形如 `node       v22.22.2  C:\Program Files\nodejs\node.exe`；缺 node 时给出安装提示，版本低于 22 时明确标出「低于 22，render 不可用」。只报「可用」不算完成。

4. **CI 独立断言。** 新增 `node-gate` job：显式 `command -v node`、校验主版本 ≥ 22，并跑 render 测试后断言输出不含 `skipped`。因为 render 测试用了 `skipif(needs_node)`，在无 node 的环境里会全部跳过而仍然「全绿」；跳过可以，「因为跳过而全绿」必须被一条独立断言挡住。

### 决定 2：`series` 进契约，并新增第 8 个检测器

阶段 6 授权在洞察契约中新增可选字段：

```json
"series": {
  "axis": "hour" | "weekday" | "day",
  "keys": ["0", "1", "2", "..."],
  "values": [0.011, 0.024, 0.031, "..."],
  "unit": "share" | "count"
}
```

约束：

- `len(keys) == len(values)`，否则报错。
- `axis="hour"` 时 `keys` 恰为 `"0".."23"`；`axis="weekday"` 时恰为 `"0".."6"`（0=周一）。
- `axis="day"` 时 `keys` 为 `YYYY-MM-DD`，覆盖审查窗口的每一天（含零值），长度等于窗口天数。
- `unit="share"` 时 `values` 之和为 1.0（容差 1e-6）。
- 无序列的 Insight 不写这个键（不要写 `null`）。

**新增 `vol.daily_series`（第 8 个检测器）**：输出全年逐日事件数，供 `heatmap` 使用。`novelty="constant"`，`signal` 固定 `0.0`；它只供渲染，不参与排名。`select()` 必须把它从排序池里排除，并在截断后无条件附回输出，否则 `story.json` 引用它时会在 `insights.json` 里找不到。

**明确禁止**把序列写进 `display` 字符串（例如 `"0.01,0.02,..."`）。`display` 继续是标量，V1 的占位符校验规则不变；序列只走 `series`。这不是风格问题：一旦序列以字符串形态进入 `display`，引用它的文案会变得不可校验，也无法在不破坏向后兼容的情况下收回。

`series` 会进 `insights.json`，agent 也要读它。365 个浮点约 3 KB，可接受。但 `recap insights --payload-preview` 必须显示带与不带 `series` 的字节差，让用户知道自己要发出去多少。

### 决定 3：巨型数字的基线补偿提升为 token

`base.css` 里的 `margin: 0 0 0.12em` 是 magic number，换字体就失效。改为：

```css
:root {
  /* 巨型数字的视觉底边补偿。换字体后只重测这一个值，由 §6c 的安全区断言验证，
   * 不需要肉眼比对。line-height 0.9 是几何，0.12em 是字体相关的修正。 */
  --display-baseline-shift: 0.12em;
}
```

`base.css` 只引用 `var(--display-baseline-shift)`，不再出现字面量。阶段 7 引入随包字体时，改动范围就是「改一个 token + 跑一次 §6c」。

### 决定 4：6c 的三条断言必须是机器可判定的

不是「检查一下」，是三条会失败的自动化断言，全部进 CI：

1. **真实布局后的溢出测量**（替代 em 估算作为最终判据）。
2. **像素级安全区扫描**（每张 PNG 扫四条边带，断言无与背景色 ΔE > 2 的像素）。
3. **WCAG 对比度**（正文 4.5 / 大字号 3.0）。

细节见 §6c。估算仍然保留，但只用于「早失败」；最终判据是浏览器里的真实布局与 PNG 里的真实像素。

---

## 执行顺序

```
0.1 Node 快速失败 → 0.2 insights.md → 0.3 series 契约 + 第 8 检测器
→ 6a 四个卡片 → 停，汇报
→ 6b PNG → 6c 三条断言 → 6d 收尾
```

本轮只做到 **6a 结束**。6b / 6c 的代码不要提前开工；但 6a 产出的 DOM 必须带好 `data-fit` 标记，否则 6c 无从下手。

---

## 0. 两个前置与一个契约变更

### 0.1 Node 依赖与 D2 冲突 —— 见决定 1

实现要点：

- 新增 `render/node.py::node_info()`，返回 `(path, version, major)`；`require_node()` 在缺失或 `major < 22` 时抛 `RecapError`。
- `cli.main()` 识别无子命令路径：第一个非选项参数不是已知子命令时，交给 `recap <路径>` 的解析器，而不是报 argparse 用法错误。
- `recap <路径>` 的处理器第一行调用 `require_node()`；工作区不存在时自动 `init`，随后 `import` → `insights --md` → 有 `story.json` 就 `render`，没有就打印下一步。
- 测试必须证明「缺 node 时没有创建 `.recapkits/`」，而不只是证明退出码为 1。

### 0.2 没有 Node 的用户不能空手而归

`recap insights` 增加 `--md`（默认开，`--no-md` 可关）：写 `.recapkits/out/insights.md`，人类可读，包含：

- 排名表（kind / 一句话事实 / 分数 / 数据充足度）
- 每条的分项拆解（与 `--explain` 同口径）
- 被 `gated` 关闭的分量与原因
- 末尾一行：「要出图需要 Node 22+，或把 insights.json 交给你的 agent 生成故事」

理由：解析了三分钟却因为缺 node 什么也拿不到，是最差的失败模式。`insights.md` 让这条路至少有产出。

### 0.3 契约缺口：卡片需要序列数据

`time.hour_rhythm` 现在只把「深夜占比 38%」作为单个数字输出，但 `clock` 卡需要 24 个小时的分布，`heatmap` 卡需要 365 天的强度。当前 `Fact.value` 只允许 `float | str`，**没有地方放序列**。

按决定 2 增加 `series`，并新增 `vol.daily_series`。实现落点：

- `insights/model.py`：`Series` dataclass，构造时校验长度、axis 键集、`share` 求和。
- `insights/detectors/temporal.py`：`time.hour_rhythm` 与 `time.weekday_rhythm` 各带一条 `share` 序列。
- `insights/detectors/generic.py`：`vol.daily_series` 用 `period.start..period.end` 补齐零值日期。
- `insights/engine.py`：`select()` 把 render-only 洞察排除出排序池，并在截断后附回。
- `emit.py`：有 `series` 才写键，无则整键省略。
- `story/validate.py`：`heatmap` 必须引用 `axis="day"`，`clock` 必须引用 `axis="hour"`；缺失或轴不符是新错误码。
- `story/bake.py`：把 `series` 原样带给渲染器；渲染器不查库、不重算。

---

## 6a — 四个卡片类型（约 24 小时）

| 类型 | 版式 | 数据来源 | 必须处理的边界 |
|---|---|---|---|
| `ranking` | 3–5 行，序号 + 名称 + 数值，等宽对齐 | `conc.*` | 只有 1 项；名称超长（中文 12 字以上）；数值需要单位 |
| `heatmap` | 53 列 × 7 行（闰年且 1 月 1 日为周日时 54 列），单元格 16×16，间距 1，按 1 月 1 日所在周对齐 | `vol.daily_series` | 全年 0 事件（全暗）；闰年 366 天；窗口不足一年（未发生的日期画成「空」而非「零」） |
| `clock` | SVG 24 段楔形，午夜在顶端，顺时针，每段 15° | `time.hour_rhythm` 的 `series` | 某小时为 0（楔形退化为线）；分布完全均匀 |
| `summary-grid` | 两列网格，6–9 个 fact，第一个占双列 | ≥3 条 `evidence` | 只有 3 个 fact；某个 `display` 特别长 |

**热图间距为什么是 1 而不是 2：** 53 列 × 16 + 52 × 2 = 952 px，而左右各 72 px 安全区之后的内容宽度只有 936 px。952 会越过安全区 8 px，直接触发 §6c 的边带扫描。改成间距 1 后总宽 900 px；闰年且 1 月 1 日为周日需要 54 列时是 917 px，仍在 936 px 内。单元格尺寸不变。这是几何约束推导出的结果，不是审美偏好。

**每个类型的四条硬性要求：**

1. **中文按字符断行**，不按空格。用 20 字以上的中文标题和带标点的长句各测一遍。
2. **溢出必须报错，不得静默截断。** 组件内的估算负责早失败；6c 的真实布局测量是最终判据。报错信息指名卡片 id 与槽位/单元下标。
3. **零值与单值是合法输入**，不得崩，也不得画出误导性的图（例如全 0 的 clock 应该显示成均匀的细环，并附 caveat）。
4. **不引入新的数据来源**：只读 `story.json`（已烘焙）里的字符串与 `series`，不查库。

每个可能溢出的文本块必须带 `data-fit="<槽位>"`，供 6c 的浏览器断言枚举。

**4:5 的紧凑模式：** 舞台从 1920 降到 1350，但安全区仍是上下各 240，内容高度只有
870。四张卡都用 `data-aspect="4:5"` 的样式覆盖下调字号与间距（不改单元格/楔形几何），
其中 `summary-grid` 的 9 个 fact 必须仍能放进 870px。9:16 的组件内估算继续按大尺寸
做早失败，因此只会偏保守。

### `ranking` 落地后必须删掉的过渡通道

`big-number` 目前借用 `evidence` 承载 `conc.*`。`ranking` 上线后：

- 删除 `bake.py` 里「没有 `insight` 时退回首条 `evidence`」的路径；
- `story-schema.md` 里对应的说明一并移除；
- 加一条测试：`big-number` 携带 3 个及以上 `evidence` 时报 `TYPE_EVIDENCE_MISMATCH`。

一个语义两种表达方式，留着就一定会有人用错，而且会在校验器里形成「两种都对」的模糊地带。

---

## 6b — PNG 输出（约 10 小时）

- 用 Playwright；**先找本机 `chrome` / `msedge`**（`channel` 参数），找不到才回落到 bundled chromium 并明确提示体积。
- viewport 固定 `1080 × 1920`，`deviceScaleFactor: 1`，**强制 `--stage-scale: 1`**（否则会按窗口尺寸二次缩放，像素对不上）。
- 截图前等三件事：`document.fonts.ready`、两次 `requestAnimationFrame`、以及页面上的 `data-render-ready` 标记。
- 每张卡一张 PNG，命名 `recap-2024-01.png` …（序号补零，保证文件名排序等于卡片顺序）。
- 比例：**9:16 与 4:5 必须做**；1:1 在砍单顺序里排第一，不要为它花时间。
- 重编码以清除 `tEXt` / `zTXt` 块（截图会带上源路径）。
- 输出 `.recapkits/out/cards/`，打印文件数与总字节，不自动打开。

---

## 6c — 设计断言（约 8 小时，本期最有价值的部分）

三条自动化断言，全部进 CI。它们把「看起来还行」变成「机器能判定」。

### 1. 溢出（真实布局）

枚举页面里每个 `[data-fit]` 元素，在页面内执行：

```js
el.scrollWidth <= el.clientWidth + 1 && el.scrollHeight <= el.clientHeight + 1
```

不满足即失败，报错输出卡片 id、`data-fit` 槽位、实测值与预算值。这条替代 `text-fit.ts` 的 em 估算作为**最终判据**；估算仍保留，用于构建期早失败。

### 2. 安全区（像素级）

对每张 PNG 扫描四条边带：上 240 px、下 240 px、左右各 72 px。断言这些带内不存在与背景色 ΔE 超过 2 的像素。

背景基准不能取单一色值：`--skin-bg-image` 是渐变。做法是先用同主题、同尺寸渲染一张**无卡片内容**的空白舞台 PNG，再逐像素比较同坐标。这样渐变本身不会被误判，而任何文字/图形侵入边带都会被抓到。

ΔE 用 CIELAB 的 Cie76 即可；阈值 2 的含义是「肉眼几乎不可见」，足以把当前「墨迹底边 1671 px vs 安全区 1680 px，只剩 9 px」的脆弱状态变成 CI 可检测的事实。

### 3. 对比度（WCAG）

对每个文本节点取 `getComputedStyle().color` 与字号：

- 正文（< 48 px）对比度 < 4.5 即失败；
- 展示字（≥ 48 px）对比度 < 3.0 即失败。

背景色不要用祖先链上的 `background-color` 硬拼：舞台是渐变，拼出来的值会偏。做法是渲染两张同构 PNG —— 一张正常、一张把所有文本设为 `color: transparent` —— 在文本包围盒中心取「隐藏文本」那张的背景像素，再与计算出的文字颜色算 WCAG 比值。这样渐变、半透明与主题叠加都被真实像素覆盖。

### 顺带：把基线补偿提升为 token

见决定 3。`tokens.css` 定义 `--display-baseline-shift: 0.12em` 并写明「换字体后只重测这一个值，由安全区断言验证」；`base.css` 只引用变量。

---

## 6d — 收尾

- `docs/story-schema.md` 补四个类型、`series` 字段、`TYPE_EVIDENCE_MISMATCH`，删除 `big-number` 借用 `evidence` 的段落。
- `docs/decisions/0002-render-pipeline.md` 补 Node 快速失败、PNG 流程与三条断言。
- `docs/decisions/0001-contracts.md` 追加 `series` 变更记录（本轮 0.3 就要写）。
- README 增加「前置条件」一节（Python / uv / Node），位置在 quickstart 之前。
- 提交分三次：`feat(cards)` / `feat(render): png` / `test(design): safe-area and contrast gates`。

---

## 本次不做

- 随包字体与子集化、golden image 比对（阶段 7）
- `editorial` 主题
- MP4
- `--auto` 规划器、MMR 多样性选卡
- spotify / netflix 适配器

---

## 验收

```bash
./uv run pytest -q                       # 全绿；render 相关用例不得 skip
./uv run recap insights --md             # 同时产出 insights.json 与 insights.md
./uv run recap insights --payload-preview  # 报出含/不含 series 的字节差
./uv run recap render --format html
./uv run recap render --format png --aspect 9:16   # 6b 之后
./uv run recap render --format png --aspect 4:5    # 6b 之后
./uv run pytest -q -m design             # 6c 之后：三条设计断言全过
```

我会手工核对六件事：

1. `insights.md` 在无 node 环境下仍能产出（临时把 node 从 PATH 里移掉试一次）。
2. `recap <路径>` 在缺 node 时**立即**失败，不消耗解析时间，且没有创建数据库。
3. `doctor` 打印 node 的绝对路径与版本；版本低于 22 时明确报「不可用」。
4. PNG 用图片查看器打开，检查 4:5 与 9:16 的边距是否一致、数字底部是否压线。
5. 把 `heatmap` 的 `series` 全置 0，页面不崩、不画成误导图形。
6. `big-number` 带 3 个 `evidence` 时报错，而不是渲染。

做完停下汇报：四个类型的边界用例结果、PNG 张数与字节、三条断言的实测数值（安全区最小余量、最低对比度、最大溢出）。

---

## 关于进度的一个校准

按已完成的工作包估算，到 v0.1.0 还剩约 **170 小时**（≈ 6 周 @35h），与 T3 的 310 h 口径基本吻合——也就是说计划没有偏，只是「5 周」那个数字早就被 §6 的工时表取代了。剩下的主要块：MP4（20h）、两个真实适配器（38h）、agent skill（14h）、打包发布（8h）、演示素材（18h）。
