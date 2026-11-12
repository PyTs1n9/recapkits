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

/** 仅供渲染的序列; 它不是文案, 永远不出现在 copy 里。 */
export interface BakedSeries {
  axis: "hour" | "weekday" | "day";
  keys: string[];
  values: number[];
  unit: "share" | "count";
}

/** ranking 的一行; value 已是 display 字符串, unit 只用于决定是否加后缀。 */
export interface BakedRow {
  label: string;
  value: string;
  unit: string | null;
}

/** summary-grid 的一个 fact; 第一个占双列。 */
export interface BakedFact {
  label: string;
  value: string;
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
  /** heatmap / clock 的序列; 其余卡型没有这个键。 */
  series?: BakedSeries;
  /** ranking 的行; 只含 rank_* 事实, 最多 5 行。 */
  rows?: BakedRow[];
  /** summary-grid 的 fact; 最多 9 个。 */
  facts?: BakedFact[];
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
