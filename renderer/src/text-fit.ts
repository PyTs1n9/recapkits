/**
 * 版面适配的度量估算。
 *
 * 这里刻意不用真实字体度量: 构建期没有字体引擎, 而 HTML 阶段的字体本身就由系统
 * 决定 (见 tokens.css 的说明)。所以按"宽字符 1em、拉丁 0.55em"估算, 与 Python 侧
 * `story/measure.py` 同一套启发式 —— 两边算出来的行数一致, 校验与渲染的判断才不会打架。
 *
 * 估算偏保守 (宁可报错早一点), 因为另一条路是静默截断, 那不可接受。
 */

/** 全角/宽字符区间; 大致对应 East_Asian_Width 的 W 与 F。 */
const WIDE_RANGES: ReadonlyArray<readonly [number, number]> = [
  [0x1100, 0x115f],
  [0x2e80, 0x303e],
  [0x3041, 0x33ff],
  [0x3400, 0x4dbf],
  [0x4e00, 0x9fff],
  [0xa000, 0xa4cf],
  [0xac00, 0xd7a3],
  [0xf900, 0xfaff],
  [0xfe30, 0xfe6f],
  [0xff00, 0xff60],
  [0xffe0, 0xffe6],
  [0x1f300, 0x1f64f],
  [0x20000, 0x3fffd],
];

const LATIN_RATIO = 0.55;
const SPACE_RATIO = 0.28;

export function isWide(codePoint: number): boolean {
  return WIDE_RANGES.some(([lo, hi]) => codePoint >= lo && codePoint <= hi);
}

export function charWidth(char: string, size: number): number {
  const codePoint = char.codePointAt(0) ?? 0;
  if (char === " " || char === "\u00a0") {
    return size * SPACE_RATIO;
  }
  return isWide(codePoint) ? size : size * LATIN_RATIO;
}

export function measure(text: string, size: number): number {
  let width = 0;
  for (const char of text) {
    width += charWidth(char, size);
  }
  return width;
}

/**
 * 按 CSS 的断行规则估算行数: 中文逐字可断, 拉丁词整块不可断。
 * `word-break: break-word` 允许超长拉丁词在必要时硬断, 这里用同一近似。
 */
export function countLines(text: string, maxWidth: number, size: number): number {
  let lines = 1;
  let used = 0;
  for (const token of tokenize(text)) {
    if (token === "\n") {
      lines += 1;
      used = 0;
      continue;
    }
    const width = measure(token, size);
    if (/^\s+$/.test(token)) {
      used = width + used > maxWidth ? used : used + width;
      continue;
    }
    if (used > 0 && used + width > maxWidth) {
      lines += 1;
      used = width;
      continue;
    }
    used += width;
  }
  return lines;
}

/** 把文本切成"不可断的块": 拉丁词/数字整块, 其余逐字, 换行符单独一块。 */
function tokenize(text: string): string[] {
  const tokens: string[] = [];
  let buffer = "";
  for (const char of text) {
    if (/[0-9A-Za-z]/u.test(char)) {
      buffer += char;
      continue;
    }
    if (buffer) {
      tokens.push(buffer);
      buffer = "";
    }
    tokens.push(char);
  }
  if (buffer) {
    tokens.push(buffer);
  }
  return tokens;
}
