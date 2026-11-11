"""HTML 渲染: 由 `renderer/` 的 TypeScript 侧产出, Python 只做数据准备与调度。

`assets/cli.mjs` 是 Vite 构建的 SSR 单文件产物 (Preact 已打进来), 由
`scripts/sync-renderer.py` 从 `renderer/dist/` 同步。改成 Node 侧渲染而不是
Python 拼字符串, 是为了让版式只有一份实现: PNG/MP4 阶段截的就是同一个页面。
"""
