/**
 * 样式装配。产物与开发态共用这一份顺序, 免得"预览里对、导出后不对"。
 *
 * 顺序是有意义的: token 先于所有规则 (变量要先定义), 基础重置与舞台先于卡片骨架,
 * 卡片骨架先于各卡型。后面的文件按同权重覆盖前面的, 所以不要随意调换。
 */
import baseCss from "./base.css?raw";
import cardCss from "./card.css?raw";
import bigNumberCss from "./cards/big-number.css?raw";
import clockCss from "./cards/clock.css?raw";
import coverCss from "./cards/cover.css?raw";
import heatmapCss from "./cards/heatmap.css?raw";
import rankingCss from "./cards/ranking.css?raw";
import summaryGridCss from "./cards/summary-grid.css?raw";
import tokensCss from "./tokens.css?raw";

// ?raw 把文件字节原样带进 bundle。Windows 的 core.autocrlf 会把 checkout 变成 CRLF,
// 于是同一份源码在 Windows 与 Linux 构建出的 cli.mjs 哈希不同, CI 的
// sync-renderer --check 必然红。装配前统一成 LF, 构建就与平台无关。
const normalize = (css: string) => css.replace(/\r\n/g, "\n");

export const STYLES = [
  tokensCss,
  baseCss,
  cardCss,
  coverCss,
  bigNumberCss,
  rankingCss,
  heatmapCss,
  clockCss,
  summaryGridCss,
].map(normalize).join("\n");
