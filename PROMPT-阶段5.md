# 阶段 5：打分二期 + 渲染器核心（HTML 首次出片）

阶段 4 已验收：77 测试绿、ruff/pyright 干净、确定性（3 次 sha256 一致）、`allow_sensitive` 确证被无视、薄数据闸门生效、7 个 kind 全部出现。四条偏差我全部认可（占位符字符集、insights 查找顺序、RUF001 行级 noqa、story 模块拆分），都是必要的判断而非越权。

本次两个任务，**先做 5a**，因为 5b 需要一个排名正确的语料才能判断渲染是否值得。

---

## 5a — 打分二期（约 6 小时）

### 现状：分数不携带信息

新语料（220 事件 / 46 活跃日）的实测输出：

| 排名 | kind | 分数 | 这个分数是怎么来的 |
|---|---|---|---|
| 1 | `vol.busiest_day` | +0.522 | `novelty=record` 给 0.5，加 `6/220×0.8` |
| 2 | `disc.longest_gap` | +0.500 | 只有 `novelty=absence` 的 0.5 |
| 3 | `disc.longest_streak` | +0.500 | 只有 `novelty=record` 的 0.5 |
| 4 | `time.hour_rhythm` | **+0.000** | 六个分量全部为 0 |
| 5 | `time.weekday_rhythm` | **+0.000** | 同上 |
| 6 | `conc.top_entity` | **−0.050** | 集中度 0.40 − 老套惩罚 0.45 |
| 7 | `vol.total` | −0.450 | 只有老套惩罚 |

三个结构性后果：

1. **`time.*` 恒为 0。** 它们没有 `top1_share`（concentration=0）、`novelty=constant`（discontinuity=0）、无上一期（deviation=rarity=0）。于是"38% 发生在深夜"这个全组最有意思的事实，排在一个恒为 0 的位置。
2. **`disc.*` 与 `vol.busiest_day` 恒为 0.5 左右，与量级无关。** 连续 21 天和连续 200 天的分数完全一样——因为 `record` 这个标签是二值的，而"每年都有一个最忙的日子"是恒真的。
3. **`conc.top_entity` 结构性封顶为负。** 集中度最多 +0.40，老套惩罚固定 −0.45，所以它永远 ≤ −0.05。62% 的集中度是真的强信号，却被自己的惩罚项压死。

根因一句话：**公式是按"六个通用分量"设计的，但每个检测器能被激活的分量不同；结果只有 `novelty` 这一项真正在工作，而它恰好是二值的。**

### 新公式

```
score = 1.00*signal + 0.40*deviation + 0.30*discontinuity − 1.00*sensitivity
```

| 分量 | 取值 | 何时为 0 |
|---|---|---|
| `signal` | 每个检测器**自己报告**的 0..1 强度，必填 | 从不（最低 0.0） |
| `deviation` | `clamp(|稳健 z| / 3)`，与上一期比 | **无上一期数据时 0.0**，并记入 `gated` |
| `discontinuity` | 有上一期且与上期不同：record/absence=1.0、shift=0.5 | **无上一期数据时 0.0**，并记入 `gated` |
| `sensitivity` | high → 1.0 | 非高敏 |

**`score_parts` 仍存"已加权"的分量，`score == sum(score_parts)` 这个不变量必须保留**，并加一条测试断言它。

### signal 表（每个都有语义锚点，写进 `docs/insights.md`）

| kind | signal 公式 | 锚点含义 |
|---|---|---|
| `vol.total` | `0.05` 常数 | 只作开场卡锚点，不参与竞争 |
| `vol.busiest_day` | `clamp((峰值日事件数 / 日均事件数 − 1.5) / 8.5)` | 1.5× 日均 = 无信号；10× = 满格 |
| `conc.top_entity` | `clamp((top1_share − 0.20) / 0.60)` | 20% = 没有集中；80% = 极端集中 |
| `time.hour_rhythm` | `clamp((深夜占比 − 0.10) / 0.40)` | 10% ≈ 均匀分布；50% = 极端夜行 |
| `time.weekday_rhythm` | `clamp((最大星期占比 − 1/7) / (0.40 − 1/7))` | 1/7 = 完全均匀；40% = 极端偏向某天 |
| `disc.longest_streak` | `clamp(连续天数 / 60)` | 60 天 = 满格 |
| `disc.longest_gap` | `clamp(空档天数 / 21)` | 21 天 = 满格 |

阈值常量集中在 `scoring.py` 顶部，命名清晰（`SIGNAL_BUSIEST_DAY_FLOOR` 之类），便于以后调。

### 删除三个分量，并说明为什么

| 删除 | 理由 |
|---|---|
| `rarity` | 静态先验表尚未存在，恒为 0；"稀有"这件事已由各类 signal 的锚点承担 |
| `concentration` | 被 signal 取代。它只是 `conc.top_entity` 的强度指标，不该是所有 kind 的通用分量 |
| `obviousness` | **职责错位**：它想解决"每个用户都有第一"的问题，但那是**选卡的冗余问题**，不是分数的惊喜度问题。选卡已有"同一 kind 最多取 1 个"的规则，惩罚项属于重复治理 |

`novelty` 字段**保留**（文案要用，且要显示给用户看），但**不再进入打分**。

### 契约变更（本次唯一授权）

- `score_parts` 的键集合改为 `{signal, deviation, discontinuity, sensitivity}`，仍存加权值。
- `gated` 现在只可能含 `deviation` 与 `discontinuity`（都是"缺上一期"）。
- `data_sufficiency` 与 4a 的判定**保持不变**——4a 没有白做，它管的是"该不该出卡"，二期管的是"出了卡怎么排序"。
- 同步更新 `docs/decisions/0001-contracts.md`（加变更记录行）与新建 `docs/insights.md`。

### 必须有的测试

1. **回归锁**：`time.hour_rhythm` 与 `time.weekday_rhythm` 的分数不再恒为 0（这是本期最重要的一条）。
2. `score == sum(score_parts.values())`，对全部候选逐条断言。
3. 在 220 事件语料上，`conc.top_entity` 与 `time.hour_rhythm` **占据前两名**，且都 ≥ 0.65。
4. `vol.busiest_day` 在"峰值 = 1.26× 日均"时 signal == 0.0。
5. 单调性（参数化构造）：连续天数 10 → 30 → 60，`disc.longest_streak` 的 signal 必须严格递增。
6. 无上一期时 `gated == ["deviation", "discontinuity"]`。
7. 所有 kind 的 signal 落在 `[0, 1]`（遍历全部检测器）。

更新黄金快照。快照里的分数会整体变化，这是预期的。

---

## 5b — 渲染器核心（约 22 小时）

目标：`recap render --format html` 产出一个单文件 HTML，能在手机上打开、看起来像成品。**这是项目第一次有可见成果。**

### 技术栈

```
renderer/
├── package.json          # preact + vite + typescript，仅 devDependencies
├── tsconfig.json
├── vite.config.ts        # build.lib 或 build.rollupOptions，产出单文件
├── index.html            # 开发用入口
└── src/
    ├── main.ts           # 读取注入的 story 数据并渲染
    ├── stage.tsx         # 固定舞台 + 缩放
    ├── tokens.css        # 设计 token
    ├── base.css          # 重置与排版基线
    └── cards/
        ├── cover.tsx
        └── big-number.tsx
```

Node 22 / pnpm 11 已确认可用。**不要引入任何运行时 JS 到产物里**——HTML 输出是静态的，`main.ts` 只在构建期把 story 渲染成字符串。

### 关键决定：渲染器不认识占位符

在 Python 侧新增 `story/bake.py`：把每个槽位的 `{{...}}` 解析成最终字符串，产出"已烘焙"的结构。

```
recap render 内部顺序：load → validate(V1–V7) → bake → render
```

渲染器只接收已烘焙的字符串。**理由：占位符逻辑若在两种语言里各写一遍，一定会漂移，而漂移的表现是"校验通过但页面显示 `{{...}}`"。** 这也让渲染器变成纯展示层，任何输入都是安全字符串。

烘焙后的结构通过 `renderer/data/story.json`（构建期注入）或 `window.__STORY__` 传入，二选一，简单即可。

### 舞台与缩放

```css
.stage {
  width: 1080px; height: 1920px;      /* 9:16；4:5 为 1080×1350 */
  transform-origin: top left;
  /* JS 按视口宽度设置 scale，布局计算永远用绝对 px */
}
```

**布局一律用绝对像素算，不用 vw/vh/rem。** 这样 PNG/MP4 阶段的截图与浏览器里看到的是同一套几何，不需要为两个目标各调一遍。

### 设计 token（`tokens.css`，照此写）

```css
:root {
  --col: 56px; --gutter: 24px; --margin: 72px;
  --safe-top: 240px; --safe-bottom: 240px;
  --fs-display: 320px; --fs-h1: 220px; --fs-h2: 140px;
  --fs-lead: 88px; --fs-body: 56px; --fs-caption: 40px; --fs-micro: 28px;
  --track-tight: -0.025em;
  --dur-fast: 160ms; --dur-mid: 400ms; --dur-slow: 700ms;
  --ease-out: cubic-bezier(0.2, 0.7, 0.1, 1);
}
```

主题 `neon`：暗底（`#0B0B0F`）、饱和渐变、白色文字、单一强调色。数字用 `font-variant-numeric: tabular-nums`，字距 `-2.5%`。文字不加投影。

### 字体（本期不解决确定性）

HTML 输出用系统字体栈：

```css
font-family: "Inter Tight", -apple-system, "Segoe UI", "PingFang SC",
             "Microsoft YaHei", "Noto Sans SC", sans-serif;
```

**确定性只在 PNG/MP4 时才要求**（阶段 6/7 再引入随包字体与子集化）。这是刻意的分期：在 HTML 阶段为字体确定性付出成本没有回报，而 CJK 字体子集化是件正经工作。在 `tokens.css` 里留一行注释说明这一点，避免以后有人以为漏了。

### 两个卡片类型

| 类型 | 版式 |
|---|---|
| `cover` | 年份做巨型字号（`--fs-display`）占满上半屏；`kicker` 小字在安全区顶部；无装饰图形 |
| `big-number` | 数字用 `--fs-display`，左对齐、底对齐到安全区下沿；`headline` 在数字上方一行；`sub` 用 `--fs-body`，最多两行，超出报错（不要静默截断） |

两个类型都要处理中文：**长标题按字符断行，不要按空格断行**（`word-break: break-word` + `line-break: strict`）。用 20 字以上的中文标题测一遍。

### HTML 输出

- 单文件，CSS 内联，无外部请求，无 JS（`<script>` 可有可无，但内容必须是静态渲染好的）。
- 竖向滚动 + `scroll-snap-type: y mandatory`，每卡一屏。
- `--aspect 9:16|4:5` 决定舞台高度。
- 输出路径 `.recapkits/out/recap-2026.html`，打印绝对路径，**不要自动打开浏览器**（无副作用原则）。

### `recap preview`

`http://127.0.0.1:<随机端口>`，监听 `story.json` 与 `insights.json` 变化后热更新。**只绑 127.0.0.1，不绑 0.0.0.0**，启动时打印 URL 与"按 Ctrl+C 停止"。这是全项目唯一会占用端口的命令，在 `doctor` 里不要提及它，在 README 里单独一句说明。

### wheel 资产同步

渲染产物 `renderer/dist/` 在打包时拷到 `src/recapkits/render/assets/`。加一个 CI 步骤：比较两侧的文件清单与 sha256，不一致就失败。这条检查的作用是防止"改了前端忘了重建"，而它一旦失效，用户拿到的 wheel 里会是旧界面。

---

## 环境前置（先做，5 分钟）

你的 GitHub HTTPS 被代理挡死（CONNECT tunnel failed, 502），这提示 npm registry 也可能不通。开工前先验：

```bash
npm ping
```

不通就切镜像，并记录下来：

```bash
npm config set registry https://registry.npmmirror.com
pnpm config set registry https://registry.npmmirror.com
```

如果两个都不可用，**停下来告诉我**——渲染器无法构建这件事会改变阶段 5 的方案（退路是用 Python 手写 HTML 模板，但那样就失去了 TS 渲染这条架构主张）。

---

## 本次不做

- 其余 4 个卡片类型（`ranking` / `heatmap` / `clock` / `summary-grid`）
- `editorial` 主题
- PNG / MP4 输出
- 字体子集化与确定性像素
- MMR 多样性选卡、同比、`--auto`
- spotify / netflix 适配器

---

## 验收

```bash
./uv run pytest -q                       # 全绿，含 5a 的 7 条新测试
./uv run ruff check . && ./uv run pyright
./uv run recap insights --top 10 --explain
#   期望：conc.top_entity 与 time.hour_rhythm 占据前二，分数 ≥ 0.65
#   期望：score_parts 只剩 4 个键，gated 含 deviation 与 discontinuity
./uv run recap render --format html --aspect 9:16
#   期望：.recapkits/out/recap-2026.html 单文件，浏览器打开无外部请求
./uv run recap preview
#   期望：127.0.0.1 上可访问，改 story.json 后自动刷新
```

我会手工核对四件事：

1. 把 HTML 用浏览器打开，**切到 375px 宽的手机视口**看一遍，确认数字不溢出、中文不乱断行。
2. 查看网页源码，确认没有任何 `http://` 或 `https://` 引用，也没有 `{{` 残留。
3. 故意传一个未烘焙的 `{{...}}` 给渲染器，应显式报错而不是把字面量画出来。
4. 把 `conc.top_entity` 的 `top1_share` 从 0.62 改成 0.25，重跑，它的排名应明显下降（证明 signal 真的在驱动排序）。

做完停下汇报：新排名表、signal 实测值、HTML 文件大小、手机视口截图或描述、遗留问题。
