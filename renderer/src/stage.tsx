import type { ComponentType } from "preact";
import { BigNumber } from "./cards/big-number";
import { Clock } from "./cards/clock";
import { Cover } from "./cards/cover";
import { Heatmap } from "./cards/heatmap";
import { Ranking } from "./cards/ranking";
import { SummaryGrid } from "./cards/summary-grid";
import { RenderError } from "./errors";
import type { Aspect, BakedCard, BakedStory, CardType } from "./types";

/** 舞台尺寸表; 4:5 为 1080x1350, 其余同为 1080 宽, 只换高度。 */
export const ASPECTS: Record<Aspect, { width: number; height: number }> = {
  "9:16": { width: 1080, height: 1920 },
  "4:5": { width: 1080, height: 1350 },
};

/** 卡片组件拿到的上下文; year 给 heatmap 补全日历用。 */
export interface CardProps {
  card: BakedCard;
  year: number;
}

/** 已实现的卡片类型; 缺一个都会显式报错, 而不是画个空屏。 */
const CARD_COMPONENTS: Partial<Record<CardType, ComponentType<CardProps>>> = {
  cover: Cover,
  "big-number": BigNumber,
  ranking: Ranking,
  heatmap: Heatmap,
  clock: Clock,
  "summary-grid": SummaryGrid,
};

function Card({ card, year }: CardProps) {
  const Component = CARD_COMPONENTS[card.type];
  if (!Component) {
    throw new RenderError(`卡片 ${card.id} 的类型 ${card.type} 尚未实现`);
  }
  return <Component card={card} year={year} />;
}

/** 一张卡一屏: 外层负责滚动吸附, 内层是固定尺寸的舞台。 */
export function Stage({
  card,
  aspect,
  year,
}: {
  card: BakedCard;
  aspect: Aspect;
  year: number;
}) {
  const size = ASPECTS[aspect];
  return (
    <section class="slide">
      <div
        class="stage"
        style={`--stage-w:${size.width};--stage-h:${size.height}`}
        data-card={card.id}
        data-card-type={card.type}
        data-aspect={aspect}
      >
        <Card card={card} year={year} />
      </div>
    </section>
  );
}

export function Deck({ story, aspect }: { story: BakedStory; aspect: Aspect }) {
  return (
    <main class="deck">
      {story.cards.map((card) => (
        <Stage key={card.id} card={card} aspect={aspect} year={story.meta.year} />
      ))}
    </main>
  );
}
