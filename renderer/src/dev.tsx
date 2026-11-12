/**
 * 开发用入口: `pnpm dev` 后改组件即时看到效果。
 *
 * 数据取自 `data/story.json` —— 一份**已烘焙**的故事, 由
 * `recap render --dump-baked` 或 Python 侧 `bake` 生成后覆盖。开发态与产物的差别
 * 只有"谁来渲染": 这里用浏览器端的 Preact, 产物用构建期的 renderToString。
 */
import { render } from "preact";
import { Deck } from "./stage";
import { STYLES } from "./styles";
import type { Aspect, BakedStory } from "./types";
import story from "../data/story.json";

const requested = new URLSearchParams(window.location.search).get("aspect");
const aspect: Aspect = requested === "4:5" ? "4:5" : "9:16";
const stageHeight = aspect === "4:5" ? 1350 : 1920;

const style = document.createElement("style");
style.textContent = STYLES;
document.head.appendChild(style);

function fit(): void {
  const scale = Math.min(window.innerWidth / 1080, window.innerHeight / stageHeight);
  document.documentElement.style.setProperty("--stage-scale", String(scale));
}

fit();
window.addEventListener("resize", fit);

const root = document.getElementById("app");
if (root) {
  render(<Deck story={story as BakedStory} aspect={aspect} />, root);
}
