import { RenderError } from "../errors";
import { countLines } from "../text-fit";
import type { BakedCard } from "../types";

const CONTENT_WIDTH = 1080 - 2 * 72;
const SIZE = 900;
const CENTER = SIZE / 2;
const OUTER = 400;
const INNER = 170;
const GAP_DEG = 0.35;
const TITLE_SIZE = 88;
const CAPTION_SIZE = 36;

function polar(radius: number, degrees: number): [number, number] {
  const radians = ((degrees - 90) * Math.PI) / 180;
  return [CENTER + radius * Math.cos(radians), CENTER + radius * Math.sin(radians)];
}

function wedgePath(start: number, end: number): string {
  const [x1, y1] = polar(OUTER, start);
  const [x2, y2] = polar(OUTER, end);
  const [x3, y3] = polar(INNER, end);
  const [x4, y4] = polar(INNER, start);
  return [
    `M ${x1.toFixed(2)} ${y1.toFixed(2)}`,
    `A ${OUTER} ${OUTER} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`,
    `L ${x3.toFixed(2)} ${y3.toFixed(2)}`,
    `A ${INNER} ${INNER} 0 0 0 ${x4.toFixed(2)} ${y4.toFixed(2)}`,
    "Z",
  ].join(" ");
}

function formatValue(value: number, unit: string): string {
  return unit === "share" ? `${Math.round(value * 100)}%` : String(Math.round(value));
}

/**
 * `clock`: 24 段楔形, 午夜在顶端, 顺时针, 每段 15°。
 *
 * 某个小时为 0 时楔形退化为一条线 —— 这是"确实没有事件", 不是缺数据。
 * 整条序列全为 0 时画一个均匀细环并附 caveat: 空圆比 24 条线更容易被误读成
 * "分布均匀"。
 */
export function Clock({ card }: { card: BakedCard }) {
  const series = card.series;
  if (!series || series.axis !== "hour") {
    throw new RenderError(
      `卡片 ${card.id} 的 clock 需要 axis=hour 的 series; 当前 ${
        series ? `axis=${series.axis}` : "没有 series"
      }`,
    );
  }

  const title = card.copy.headline ?? "";
  if (title && countLines(title, CONTENT_WIDTH, TITLE_SIZE) > 1) {
    throw new RenderError(`卡片 ${card.id} 的 clock.headline 在 ${TITLE_SIZE}px 下超过 1 行`);
  }
  const caption = card.copy.sub ?? "";
  if (caption && countLines(caption, CONTENT_WIDTH, CAPTION_SIZE) > 2) {
    throw new RenderError(`卡片 ${card.id} 的 clock.sub 在 ${CAPTION_SIZE}px 下超过 2 行`);
  }

  const values = series.values;
  const total = values.reduce((sum, value) => sum + value, 0);
  const max = Math.max(0, ...values);
  const peak = values.indexOf(max);
  const empty = total <= 0;

  return (
    <div class="card clock">
      {card.copy.kicker ? (
        <p class="copy clock__kicker" data-fit="kicker">
          {card.copy.kicker}
        </p>
      ) : null}
      {title ? (
        <h2 class="copy clock__title" data-fit="headline">
          {title}
        </h2>
      ) : null}

      <div class="clock__dial">
        <svg class="clock__svg" viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label="24 小时分布">
          {empty ? (
            <circle class="clock__ring" cx={CENTER} cy={CENTER} r={(OUTER + INNER) / 2} />
          ) : (
            values.map((value, hour) => {
              const start = hour * 15;
              const end = (hour + 1) * 15;
              if (value <= 0) {
                const mid = start + 7.5;
                const [x1, y1] = polar(INNER, mid);
                const [x2, y2] = polar(OUTER, mid);
                return (
                  <line
                    key={`${card.id}-h${hour}`}
                    class="clock__zero"
                    x1={x1.toFixed(2)}
                    y1={y1.toFixed(2)}
                    x2={x2.toFixed(2)}
                    y2={y2.toFixed(2)}
                  />
                );
              }
              const opacity = 0.2 + 0.8 * (value / max);
              return (
                <path
                  key={`${card.id}-h${hour}`}
                  class="clock__wedge"
                  d={wedgePath(start + GAP_DEG, end - GAP_DEG)}
                  fill-opacity={opacity.toFixed(3)}
                />
              );
            })
          )}
          {empty ? (
            <>
              <text class="clock__peak-label" x={CENTER} y={400}>
                没有可用分布
              </text>
              <text class="clock__peak" x={CENTER} y={530}>
                —
              </text>
            </>
          ) : (
            <>
              <text class="clock__peak-label" x={CENTER} y={400}>
                最活跃小时
              </text>
              {/* 不给 SVG 文本挂 data-fit: SVG 元素没有 client/scroll 度量,
                  标记了也测不出溢出, 只会让人以为覆盖到了。这里的位置由几何固定。 */}
              <text class="clock__peak tnum" x={CENTER} y={530}>
                {String(peak).padStart(2, "0")}:00
              </text>
              <text class="clock__peak-label" x={CENTER} y={590}>
                {series.unit === "share"
                  ? `占 ${formatValue(values[peak], series.unit)}`
                  : `${formatValue(values[peak], series.unit)} 次`}
              </text>
            </>
          )}
        </svg>
      </div>

      {caption ? (
        <p class="copy clock__caption" data-fit="sub">
          {caption}
        </p>
      ) : null}
      {empty ? (
        <p class="copy clock__caption" data-fit="caveat">
          窗口内没有可用的时间分布; 细环表示全零, 不是均匀分布。
        </p>
      ) : null}
    </div>
  );
}
