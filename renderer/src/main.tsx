import { renderToString } from "preact-render-to-string";
import baseCss from "./base.css?raw";
import cardsCss from "./cards.css?raw";
import { RenderError } from "./errors";
import { ASPECTS, Deck } from "./stage";
import tokensCss from "./tokens.css?raw";
import type { BakedStory, RenderOptions } from "./types";

/**
 * 渲染器只接收**已烘焙**的字符串。占位符解析是 Python 侧 `story/bake.py` 的职责,
 * 这里再出现 `{{` 只可能是调用方漏跑了 bake。与其把字面量画到页面上, 不如直接失败:
 * 校验通过却显示 `{{...}}` 这种事, 只有在两门语言各写一遍占位符逻辑时才会发生。
 */
export function assertBaked(story: BakedStory): void {
  const seen: string[] = [];
  for (const card of story.cards) {
    const values: Array<string | null | undefined> = [
      card.copy.headline,
      card.copy.sub,
      card.copy.kicker,
      card.number,
      ...(card.rows ?? []).flatMap((row) => [row.label, row.value]),
      ...(card.facts ?? []).flatMap((fact) => [fact.label, fact.value]),
    ];
    for (const value of values) {
      if (typeof value === "string" && (value.includes("{{") || value.includes("}}"))) {
        seen.push(`卡片 ${card.id}: ${value}`);
      }
    }
  }
  if (seen.length > 0) {
    throw new RenderError(
      `收到未烘焙的占位符, 渲染器不做占位符解析; 先跑 story/bake.py。\n  ${seen.join("\n  ")}`,
    );
  }
}

/**
 * 缩放脚本。布局本身全部是绝对像素, 只有这里读视口: 舞台固定 1080 宽,
 * 按 min(视口宽/舞台宽, 视口高/舞台高) 整体缩放, 保证任何比例下都不裁切。
 *
 * 放在 `<head>` 里执行, 而不是 body 末尾: 它只写一个 CSS 变量, 不需要 DOM,
 * 提前跑掉才能避免首帧闪一下未缩放的大图。
 * 这是产物里唯一的 JS, 不到十行, 且不参与内容渲染。
 */
function scaleScript(width: number, height: number): string {
  return `<script>(function(){var W=${width},H=${height};function fit(){var s=Math.min(window.innerWidth/W,window.innerHeight/H);document.documentElement.style.setProperty("--stage-scale",String(s));}fit();window.addEventListener("resize",fit);})();</script>`;
}

/**
 * 就绪标记。PNG 截图必须在字体与首帧布局都稳定之后, 否则会拍到回退字体或半成品。
 * 两帧 rAF 之后再打标记: 第一帧完成布局, 第二帧确认绘制没有触发新的回流。
 * 截图侧等 `html[data-render-ready="1"]`, 而不是猜一个 sleep。
 *
 * 写成多行, 且不让两个 `}` 相邻: 产物的测试会断言全文没有 `}}` (那是占位符残留的
 * 形状), 压缩成一行的脚本很容易撞上这条断言。
 */
function readyScript(): string {
  return [
    "<script>(function () {",
    'function mark() { document.documentElement.setAttribute("data-render-ready", "1"); }',
    "function tick() { requestAnimationFrame(function () { requestAnimationFrame(mark); }); }",
    'if (document.readyState === "complete") { tick(); }',
    'else { window.addEventListener("load", tick, { once: true }); }',
    " } )();</script>",
  ].join("");
}

/** 把已烘焙的故事渲染成一份自包含的 HTML 文档 (无外部请求, 无内容 JS)。 */
export function renderStory(story: BakedStory, options: RenderOptions): string {
  assertBaked(story);
  const size = ASPECTS[options.aspect];
  const body = renderToString(<Deck story={story} aspect={options.aspect} />);
  const title = `${story.meta.year} 年度回顾`;

  return [
    "<!DOCTYPE html>",
    `<html lang="zh-CN" data-theme="${escapeAttribute(options.theme)}">`,
    "<head>",
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
    `<title>${escapeText(title)}</title>`,
    scaleScript(size.width, size.height),
    readyScript(),
    `<style>${tokensCss}\n${baseCss}\n${cardsCss}</style>`,
    "</head>",
    "<body>",
    body,
    "</body>",
    "</html>",
    "",
  ].join("\n");
}

function escapeText(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function escapeAttribute(value: string): string {
  return escapeText(value).replace(/"/g, "&quot;");
}
