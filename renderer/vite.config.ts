import { defineConfig } from "vite";

/**
 * 只产出一个 Node 可执行的单文件 ESM: `dist/cli.mjs`。
 *
 * `build.ssr` 让 Vite 把 Preact 与 preact-render-to-string 一起打进来, 所以
 * 运行时只需要 Node, 不需要 node_modules。CSS 通过 `?raw` 作为字符串进入产物,
 * 因此构建结束时 dist 里没有独立的 .css 文件 —— 单文件 HTML 的前提。
 */
export default defineConfig({
  // SSR 构建默认把依赖外置, 但产物要单独拷进 wheel, 运行时不能有 node_modules,
  // 所以这里强制把 preact 与 preact-render-to-string 打进单文件。
  ssr: { noExternal: true },
  build: {
    ssr: "src/cli.ts",
    outDir: "dist",
    emptyOutDir: true,
    target: "node20",
    minify: false,
    sourcemap: false,
    rollupOptions: {
      output: { format: "es", entryFileNames: "cli.mjs" },
      external: ["node:fs", "node:path", "node:process"],
    },
  },
  esbuild: { jsx: "automatic", jsxImportSource: "preact" },
});
