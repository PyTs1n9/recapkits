import type { ComponentType } from "preact";
import { BigNumber } from "./cards/big-number";
import { Cover } from "./cards/cover";
import { RenderError } from "./errors";
import type { Aspect, BakedCard, BakedStory } from "./types";

/** 舞台尺寸表; 4:5 为 1080x1350, 其余同为 1080 宽, 只换高度。 */
export const ASPECTS: Record<Aspect, { width: number; height: number }> = {
  "9:16": { width: 1080, height: 1920 },
  "4:5": { width: 1080, height: 1350 },
};

/** 已实现的卡片类型; 其余四个是阶段 6 的事, 遇到就明确报错而不是画个空屏。 */
const CARD_COMPONENTS: Partial<Record<BakedCard["type"], ComponentType<{ card: BakedCard }>>> = {
  cover: Cover,
  "big-number": BigNumber,
};

function Card({ card }: { card: BakedCard }) {
  const Component = CARD_COMPONENTS[card.type];
  if (!Component) {
    throw new RenderError(
      `卡片 ${card.id} 的类型 ${card.type} 尚未实现; 阶段 5 只支持 cover 与 big-number`,
    );
  }
  return <Component card={card} />;
}

/** 一张卡一屏: 外层负责滚动吸附, 内层是固定尺寸的舞台。 */
export function Stage({ card, aspect }: { card: BakedCard; aspect: Aspect }) {
  const size = ASPECTS[aspect];
  return (
    <section class="slide">
      <div
        class="stage"
        style={`--stage-w:${size.width};--stage-h:${size.height}`}
        data-card={card.id}
      >
        <Card card={card} />
      </div>
    </section>
  );
}

export function Deck({ story, aspect }: { story: BakedStory; aspect: Aspect }) {
  return (
    <main class="deck">
      {story.cards.map((card) => (
        <Stage key={card.id} card={card} aspect={aspect} />
      ))}
    </main>
  );
}
