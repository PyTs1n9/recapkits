import { RenderError } from "../errors";
import { countLines, measure } from "../text-fit";
import type { BakedCard, BakedRow } from "../types";

const CONTENT_WIDTH = 1080 - 2 * 72;
const INDEX_WIDTH = 64;
const VALUE_WIDTH = 220;
const GAP = 24;
const LABEL_WIDTH = CONTENT_WIDTH - INDEX_WIDTH - VALUE_WIDTH - GAP * 2;
const LABEL_SIZE = 56;
const VALUE_SIZE = 72;
const UNIT_SIZE = 36;
const MAX_ROWS = 5;

/** count 是唯一需要补口语单位的类型; 其余 display 已经自带单位。 */
function unitSuffix(unit: string | null): string {
  return unit === "count" ? "次" : "";
}

function checkRow(cardId: string, index: number, row: BakedRow): void {
  const labelLines = countLines(row.label, LABEL_WIDTH, LABEL_SIZE);
  if (labelLines > 2) {
    throw new RenderError(
      `卡片 ${cardId} 的 ranking 第 ${index + 1} 行名称在 ${LABEL_SIZE}px 下占 ${labelLines} 行, ` +
        "最多 2 行; 缩短名称, 或换一个粒度更粗的实体",
    );
  }
  const suffix = unitSuffix(row.unit);
  const valueWidth = measure(row.value, VALUE_SIZE) + (suffix ? measure(suffix, UNIT_SIZE) + 8 : 0);
  if (valueWidth > VALUE_WIDTH) {
    throw new RenderError(
      `卡片 ${cardId} 的 ranking 第 ${index + 1} 行数值宽 ${Math.round(valueWidth)}px, ` +
        `超过 ${VALUE_WIDTH}px; 缩短数字, 或把单位挪进名称`,
    );
  }
}

/**
 * `ranking`: 3–5 行, 序号 + 名称 + 数值。
 *
 * 只有 1 行时也照常渲染, 不拉伸、不补空行: 单值是一个合法事实, 不是缺数据。
 * 名称按字符断行(继承 .copy), 最多两行; 超过就报错, 不截断。
 */
export function Ranking({ card }: { card: BakedCard }) {
  const rows = (card.rows ?? []).slice(0, MAX_ROWS);
  if (rows.length === 0) {
    throw new RenderError(
      `卡片 ${card.id} 的 ranking 没有 rows; 需要一个带 rank_* 事实的 conc.* 洞察`,
    );
  }
  rows.forEach((row, index) => checkRow(card.id, index, row));

  const headline = card.copy.headline ?? "";
  if (headline && countLines(headline, CONTENT_WIDTH, 96) > 1) {
    throw new RenderError(`卡片 ${card.id} 的 ranking.headline 在 96px 下超过 1 行`);
  }
  const sub = card.copy.sub ?? "";
  if (sub && countLines(sub, CONTENT_WIDTH, 40) > 2) {
    throw new RenderError(`卡片 ${card.id} 的 ranking.sub 在 40px 下超过 2 行`);
  }

  return (
    <div class="card ranking">
      {card.copy.kicker ? (
        <p class="copy ranking__kicker" data-fit="kicker">
          {card.copy.kicker}
        </p>
      ) : null}
      {headline ? (
        <h2 class="copy ranking__title" data-fit="headline">
          {headline}
        </h2>
      ) : null}
      {sub ? (
        <p class="copy ranking__sub" data-fit="sub">
          {sub}
        </p>
      ) : null}
      <ol class="ranking__list">
        {rows.map((row, index) => (
          <li class="ranking__row" key={`${card.id}-${index}`}>
            <span class="ranking__index tnum" data-fit={`row${index}.index`}>
              {String(index + 1).padStart(2, "0")}
            </span>
            <span class="copy ranking__label" data-fit={`row${index}.label`}>
              {row.label}
            </span>
            <span class="ranking__value tnum" data-fit={`row${index}.value`}>
              {row.value}
              {unitSuffix(row.unit) ? (
                <span class="ranking__unit">{unitSuffix(row.unit)}</span>
              ) : null}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
