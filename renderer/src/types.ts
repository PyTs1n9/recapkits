/**
 * 渲染器的输入类型。这些结构由 Python 侧的 `story/bake.py` 产出,
 * 里面的字符串**已经烘焙完毕** —— 渲染器不做任何占位符解析。
 */

export type Aspect = "9:16" | "4:5";

export type CardType =
  | "cover"
  | "big-number"
  | "ranking"
  | "heatmap"
  | "clock"
  | "summary-grid";

/** 已烘焙的文案槽位; 值里不允许再出现 `{{`, 入口会显式检查。 */
export interface BakedCopy {
  headline?: string;
  sub?: string;
  kicker?: string;
}

export interface BakedCard {
  id: string;
  type: CardType;
  copy: BakedCopy;
  /**
   * `big-number` 的巨型数字, 取自被引洞察的 `headline_fact.display`。
   * 已烘焙, 不是模板; 没有引洞察时为 null。
   */
  number?: string | null;
  insight?: string | null;
}

export interface BakedMeta {
  year: number;
  locale: string;
  theme: string;
  tone: string;
  buildId: string;
}

export interface BakedStory {
  version: 1;
  meta: BakedMeta;
  cards: BakedCard[];
}

export interface RenderOptions {
  aspect: Aspect;
  theme: string;
}
