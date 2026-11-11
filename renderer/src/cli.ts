import { readFileSync, writeFileSync } from "node:fs";
import { RenderError } from "./errors";
import { renderStory } from "./main";
import type { Aspect, BakedStory } from "./types";

const USAGE = "用法: node cli.mjs --story <baked.json> [--aspect 9:16|4:5] [--theme neon] [--out <file>]";

interface Args {
  story: string;
  aspect: Aspect;
  theme: string;
  out: string | null;
}

function parseArgs(argv: string[]): Args {
  const args: Args = { story: "", aspect: "9:16", theme: "neon", out: null };
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    const value = argv[index + 1];
    switch (flag) {
      case "--story":
        args.story = value ?? "";
        index += 1;
        break;
      case "--aspect":
        if (value !== "9:16" && value !== "4:5") {
          throw new RenderError(`--aspect 只支持 9:16 或 4:5, 收到 ${value ?? "(空)"}`);
        }
        args.aspect = value;
        index += 1;
        break;
      case "--theme":
        args.theme = value ?? "neon";
        index += 1;
        break;
      case "--out":
        args.out = value ?? null;
        index += 1;
        break;
      default:
        throw new RenderError(`未知参数 ${flag}\n${USAGE}`);
    }
  }
  if (!args.story) {
    throw new RenderError(USAGE);
  }
  return args;
}

function main(argv: string[]): number {
  const args = parseArgs(argv);
  const story = JSON.parse(readFileSync(args.story, "utf8")) as BakedStory;
  const html = renderStory(story, { aspect: args.aspect, theme: args.theme });
  if (args.out) {
    writeFileSync(args.out, html, "utf8");
  } else {
    process.stdout.write(html);
  }
  return 0;
}

try {
  process.exitCode = main(process.argv.slice(2));
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
}
