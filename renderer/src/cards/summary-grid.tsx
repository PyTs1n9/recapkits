import { RenderError } from "../errors";
import { countLines, measure } from "../text-fit";
import type { BakedCard } from "../types";

const CONTENT_WIDTH = 1080 - 2 * 72;
const GAP = 20;
const CELL_WIDTH = (CONTENT_WIDTH - GAP) / 2;
const CELL_PAD = 24;
const HERO_PAD = 32;
const CELL_VALUE_SIZE = 72;
const HERO_VALUE_SIZE = 150;
const CELL_LABEL_SIZE = 30;
const HERO_LABEL_SIZE = 38;
const MAX_FACTS = 9;

/**
 * `summary-grid`: 两列网格, 第一个 fact 占双列。
 *
 * 3 个 fact 也照常渲染(一主两副), 不补空位; 9 个是上限, 由 bake 截断,
 * 这里只负责版式。任何一个数字或标签放不下都报错, 不缩小字号。
 */
export function SummaryGrid({ card }: { card: BakedCard }) {
  const facts = (card.facts ?? []).slice(0, MAX_FACTS);
  if (facts.length === 0) {
    throw new RenderError(
      `卡片 ${card.id} 的 summary-grid 没有 facts; 至少需要 3 条被引洞察`,
    );
  }

  facts.forEach((fact, index) => {
    const hero = index === 0;
    const valueSize = hero ? HERO_VALUE_SIZE : CELL_VALUE_SIZE;
    const valueWidth = hero ? CONTENT_WIDTH - HERO_PAD * 2 : CELL_WIDTH - CELL_PAD * 2;
    if (measure(fact.value, valueSize) > valueWidth) {
      throw new RenderError(
        `卡片 ${card.id} 的 summary-grid 第 ${index + 1} 个数值宽 ` +
          `${Math.round(measure(fact.value, valueSize))}px, 超过 ${valueWidth}px`,
      );
    }
    const labelSize = hero ? HERO_LABEL_SIZE : CELL_LABEL_SIZE;
    if (countLines(fact.label, valueWidth, labelSize) > 2) {
      throw new RenderError(
        `卡片 ${card.id} 的 summary-grid 第 ${index + 1} 个标签在 ${labelSize}px 下超过 2 行`,
      );
    }
  });

  const title = card.copy.headline ?? "";
  if (title && countLines(title, CONTENT_WIDTH, 88) > 1) {
    throw new RenderError(`卡片 ${card.id} 的 summary-grid.headline 在 88px 下超过 1 行`);
  }

  return (
    <div class="card summary-grid">
      {card.copy.kicker ? (
        <p class="copy summary-grid__kicker" data-fit="kicker">
          {card.copy.kicker}
        </p>
      ) : null}
      {title ? (
        <h2 class="copy summary-grid__title" data-fit="headline">
          {title}
        </h2>
      ) : null}
      <div class="summary-grid__grid">
        {facts.map((fact, index) => (
          <div
            class={
              index === 0
                ? "summary-grid__cell summary-grid__cell--hero"
                : "summary-grid__cell"
            }
            key={`${card.id}-${index}`}
          >
            <span class="summary-grid__value tnum" data-fit={`fact${index}.value`}>
              {fact.value}
            </span>
            <span class="copy summary-grid__label" data-fit={`fact${index}.label`}>
              {fact.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
