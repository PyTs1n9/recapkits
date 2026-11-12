import { RenderError } from "../errors";
import { countLines, measure } from "../text-fit";
import type { BakedCard } from "../types";

/** 内容区宽度: 1080 - 左右各 72, 与 tokens.css 的 --margin 保持一致。 */
export const CONTENT_WIDTH = 1080 - 2 * 72;
const YEAR_SIZE = 320;
const SUB_SIZE = 88;

/**
 * `cover`: 年份巨型字号占满上半屏, kicker 在安全区顶部, 无装饰图形。
 *
 * 年份按单行校验: 4 位数字在 320px 下约 704px, 放得下; 换成一段长文案则明确报错,
 * 而不是让它悄悄换行把上半屏挤满。
 */
export function Cover({ card }: { card: BakedCard }) {
  const year = card.copy.headline ?? "";
  const width = measure(year, YEAR_SIZE);
  if (year && width > CONTENT_WIDTH) {
    throw new RenderError(
      `卡片 ${card.id} 的 cover.headline 在 ${YEAR_SIZE}px 下宽 ${Math.round(width)}px, ` +
        `超过 ${CONTENT_WIDTH}px; 缩短文案, 或换用 big-number`,
    );
  }
  const sub = card.copy.sub ?? "";
  if (sub && countLines(sub, CONTENT_WIDTH, SUB_SIZE) > 2) {
    throw new RenderError(
      `卡片 ${card.id} 的 cover.sub 在 ${SUB_SIZE}px 下超过 2 行; 缩短文案, 或挪进另一张卡`,
    );
  }

  return (
    <div class="card cover">
      {card.copy.kicker ? (
        <p class="copy cover__kicker" data-fit="kicker">
          {card.copy.kicker}
        </p>
      ) : null}
      <h1 class="copy cover__year tnum" data-fit="headline">
        {year}
      </h1>
      {sub ? (
        <p class="copy cover__sub" data-fit="sub">
          {sub}
        </p>
      ) : null}
      <div class="cover__rule" aria-hidden="true" />
    </div>
  );
}
