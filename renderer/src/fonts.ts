/**
 * 随包字体: 两份 WOFF2 以 base64 文本入库, 构建时拼成 @font-face。
 *
 * 为什么是 `.b64` + `?raw` 而不是二进制 `.woff2` + `?inline`:
 * - `?raw` 是这个项目每天都在用的机制; 二进制资产要么依赖 vite 的 `?inline`
 *   行为 (版本相关, 不是既有路径), 要么引入一个自定义插件;
 * - `.b64` 是纯 ASCII, normalize() 的 LF 处理顺手覆盖;
 * - 产物仍然只有 `dist/cli.mjs` 一个文件, `sync-renderer --check` 的文件清单
 *   比较逻辑一行都不用改。
 *
 * 字体由 `scripts/build-fonts.py` 按固定 URL + sha256 子集化: GB/T 2312 一级字
 * (3755 个) + ASCII + 常用标点。一级字覆盖现代中文日常文本 99% 以上, 二级字与
 * 生僻字回退系统字体 —— 这条限制同时写在 README 的「已知限制」里。
 */
import interTight from "./assets/inter-tight.woff2.b64?raw";
import notoSansSc from "./assets/noto-sans-sc.woff2.b64?raw";

/** data: URL 里不允许空白; 编辑器折行或 checkout 的换行都在这里被抹掉。 */
const compact = (data: string) => data.replace(/\s+/g, "");

function face(family: string, data: string): string {
  return [
    "@font-face{",
    `font-family:"${family}";`,
    `src:url(data:font/woff2;base64,${compact(data)}) format("woff2");`,
    // 变量字体保留 wght 轴, 400/600/700 都从同一份文件里取, 不需要三份静态字重。
    "font-weight:100 900;",
    "font-style:normal;",
    // block: 字体就绪前先不画字, 而不是先用回退字体画一遍再替换 ——
    // 后者正是"同一份 HTML 在两个平台截图不同"的来源。
    "font-display:block;",
    "}",
  ].join("");
}

/** 两段 @font-face; 必须排在 tokens.css 之前。 */
export const FONT_FACE_CSS = [
  face("Inter Tight", interTight),
  face("Noto Sans SC", notoSansSc),
].join("\n");
