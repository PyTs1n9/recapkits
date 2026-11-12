import { RenderError } from "../errors";
import { countLines } from "../text-fit";
import type { BakedCard } from "../types";
import { CONTENT_WIDTH } from "./cover";

const DAY_MS = 86_400_000;
const TITLE_SIZE = 96;
const SUB_SIZE = 40;

interface Cell {
  column: number;
  row: number;
  level: number;
  empty: boolean;
}

/** 0 = 没有事件; 1..4 = 相对全年峰值的强度。 */
function levelOf(value: number, max: number): number {
  if (max <= 0 || value <= 0) {
    return 0;
  }
  return Math.min(4, Math.max(1, Math.ceil((value / max) * 4)));
}

function buildCells(keys: string[], values: number[], year: number): { cells: Cell[]; cols: number } {
  const start = Date.UTC(year, 0, 1);
  const end = Date.UTC(year, 11, 31);
  const totalDays = Math.round((end - start) / DAY_MS) + 1;
  // 周一为第 0 行; 1 月 1 日所在周就是第 0 列。
  const startDow = (new Date(start).getUTCDay() + 6) % 7;
  const cols = Math.ceil((startDow + totalDays) / 7);

  const byDay = new Map<number, number>();
  keys.forEach((key, index) => {
    const [y, m, d] = key.split("-").map(Number);
    const offset = Math.round((Date.UTC(y, m - 1, d) - start) / DAY_MS);
    if (offset >= 0 && offset < totalDays) {
      byDay.set(offset, values[index] ?? 0);
    }
  });
  const max = Math.max(0, ...byDay.values());

  const cells: Cell[] = [];
  for (let offset = 0; offset < totalDays; offset += 1) {
    const row = (startDow + offset) % 7;
    const column = Math.floor((startDow + offset) / 7);
    const value = byDay.get(offset);
    cells.push({
      column,
      row,
      level: value === undefined ? 0 : levelOf(value, max),
      empty: value === undefined,
    });
  }
  return { cells, cols };
}

/**
 * `heatmap`: 53 列 × 7 行（闰年且 1 月 1 日为周日时 54 列）, 装在面板里。
 *
 * 序列只覆盖审查窗口; 窗口之外的日期**不画格子**, 而不是画成 0。这两件事必须
 * 在视觉上可区分, 否则"还没发生"会被读成"什么都没做"。
 *
 * 面板宽 = 格阵 900 + 两侧各 16 = 932, 居中后左右各 74px, 仍在 72px 安全区内。
 */
export function Heatmap({ card, year }: { card: BakedCard; year: number }) {
  const series = card.series;
  if (!series || series.axis !== "day") {
    throw new RenderError(
      `卡片 ${card.id} 的 heatmap 需要 axis=day 的 series; 当前 ${
        series ? `axis=${series.axis}` : "没有 series"
      }`,
    );
  }

  const headline = card.copy.headline ?? "";
  if (headline && countLines(headline, CONTENT_WIDTH, TITLE_SIZE) > 1) {
    throw new RenderError(`卡片 ${card.id} 的 heatmap.headline 在 ${TITLE_SIZE}px 下超过 1 行`);
  }
  const sub = card.copy.sub ?? "";
  if (sub && countLines(sub, CONTENT_WIDTH, SUB_SIZE) > 2) {
    throw new RenderError(`卡片 ${card.id} 的 heatmap.sub 在 ${SUB_SIZE}px 下超过 2 行`);
  }

  const { cells, cols } = buildCells(series.keys, series.values, year);
  const active = cells.filter((cell) => !cell.empty);
  const emptyYear = active.every((cell) => cell.level === 0);

  return (
    <div class="card heatmap">
      <header class="card__head">
        {card.copy.kicker ? (
          <p class="copy card__kicker" data-fit="kicker">
            {card.copy.kicker}
          </p>
        ) : null}
        <span class="card__rule" aria-hidden="true" />
        {headline ? (
          <h2 class="copy card__title" data-fit="headline">
            {headline}
          </h2>
        ) : null}
        {sub ? (
          <p class="copy card__sub" data-fit="sub">
            {sub}
          </p>
        ) : null}
      </header>

      <div class="card__body heatmap__body">
        <div class="heatmap__panel">
          <div class="heatmap__grid" style={`--cols:${cols}`} data-cols={cols}>
            {cells.map((cell, index) => (
              <span
                key={`${card.id}-${index}`}
                class={
                  cell.empty
                    ? "heatmap__cell heatmap__cell--empty"
                    : cell.level === 0
                      ? "heatmap__cell heatmap__cell--zero"
                      : `heatmap__cell heatmap__cell--l${cell.level}`
                }
                style={`grid-column:${cell.column + 1};grid-row:${cell.row + 1}`}
                data-empty={cell.empty ? "true" : undefined}
              />
            ))}
          </div>
          <div class="heatmap__foot">
            <span>逐日事件数</span>
            <span class="heatmap__scale">
              <span>少</span>
              <span class="heatmap__swatch heatmap__cell--zero" />
              <span class="heatmap__swatch heatmap__cell--l2" />
              <span class="heatmap__swatch heatmap__cell--l4" />
              <span>多</span>
            </span>
          </div>
        </div>
        {emptyYear ? (
          <p class="copy heatmap__caveat" data-fit="caveat">
            审查窗口内没有事件；空格外形表示「尚未发生」，不代表零值。
          </p>
        ) : null}
      </div>

      <span class="card__foot" aria-hidden="true" />
    </div>
  );
}
