import { RenderError } from "../errors";
import { countLines } from "../text-fit";
import type { BakedCard } from "../types";
import { CONTENT_WIDTH } from "./cover";

const SUB_SIZE = 56;
const HEADLINE_SIZE = 140;

/**
 * `big-number`: 数字用 --fs-display, 左对齐、底对齐到安全区下沿。
 *
 * 版式是自下而上的一层递进: 数字 (320) -> headline (140) -> sub (56) -> kicker。
 * 越靠下越大, 视线落点就是数字本身。
 *
 * `number` 来自被引洞察的 `headline_fact.display`, 由 Python 侧烘焙时带进来,
 * 所以这个卡片自身不需要认识任何占位符。没有引洞察时退回把 headline 当数字。
 *
 * `sub` 最多两行、`headline` 只能一行, 超出**报错**而不是静默截断 —— 截断过的文案
 * 会以"看起来对"的方式把错误数据发出去, 那比构建失败危险得多。
 */
export function BigNumber({ card }: { card: BakedCard }) {
  const headline = card.copy.headline ?? "";
  const sub = card.copy.sub ?? "";
  const number = card.number ?? "";
  const hasNumber = number.length > 0;

  if (headline) {
    const lines = countLines(headline, CONTENT_WIDTH, HEADLINE_SIZE);
    if (lines > 1) {
      throw new RenderError(
        `卡片 ${card.id} 的 big-number.headline 在 ${HEADLINE_SIZE}px 下占 ${lines} 行, ` +
          `只允许 1 行; 缩短到 ${Math.floor(CONTENT_WIDTH / HEADLINE_SIZE)} 个汉字以内, 或移进 sub`,
      );
    }
  }
  if (sub) {
    const lines = countLines(sub, CONTENT_WIDTH, SUB_SIZE);
    if (lines > 2) {
      throw new RenderError(
        `卡片 ${card.id} 的 big-number.sub 在 ${SUB_SIZE}px 下占 ${lines} 行, 最多 2 行; ` +
          "缩短文案, 或把细节挪到另一张卡",
      );
    }
  }
  if (!hasNumber && !headline) {
    throw new RenderError(`卡片 ${card.id} 的 big-number 既没有 number 也没有 headline, 无法出图`);
  }

  return (
    <div class="card big-number">
      {card.copy.kicker ? (
        <p class="copy big-number__kicker" data-fit="kicker">
          {card.copy.kicker}
        </p>
      ) : null}
      {sub ? (
        <p class="copy big-number__sub" data-fit="sub">
          {sub}
        </p>
      ) : null}
      {hasNumber && headline ? (
        <p class="copy big-number__headline" data-fit="headline">
          {headline}
        </p>
      ) : null}
      <p class="copy big-number__value tnum" data-fit="number">
        {hasNumber ? number : headline}
      </p>
    </div>
  );
}
