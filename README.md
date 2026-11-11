# recapkits

本地优先、插件化的「任意数据的年度回顾」引擎。把数据导出丢进来，在本机生成可分享的竖向故事卡片。不上传、不遥测、不需要账号。

## quickstart

```bash
uvx recapkits init --tz Asia/Shanghai
uvx recapkits import ~/code --source git
uvx recapkits insights --top 10
uvx recapkits render --format html --aspect 9:16
```

`render` 需要环境里有 **Node 22+**：HTML 由 `renderer/` 构建出的单文件渲染器产出
（Preact SSR），这样版式只有一份实现，后面出 PNG/MP4 截的是同一个页面。
产物写到 `.recapkits/out/recap-<年份>.html`，单文件、无外部请求，手机可直接打开。

想在改文案时实时看效果，用 `recap preview`（全项目唯一占用端口的命令）：

```bash
uvx recapkits preview          # 只绑 127.0.0.1，端口随机，按 Ctrl+C 停止
```

## 改渲染器

```bash
pnpm --dir renderer install
pnpm --dir renderer build
python scripts/sync-renderer.py    # 把 dist/ 同步到 src/recapkits/render/assets/
```

`--check` 模式只比较两侧的文件清单与 sha256，CI 用它守住"改了前端忘了重建"。

## 本地工具链

uv 跟着项目走，不依赖全局安装：

```bash
./uv sync                 # Git Bash / WSL：仓库根的 uv 入口
uv sync                   # cmd：在仓库根目录会命中 uv.cmd
. .\scripts\env.ps1       # PowerShell：把 .tools\uv 与 .venv 前置到本次会话 PATH
```

`.tools/` 不入库（uv 二进制约 31 MB）。换机后执行一次 `powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1` 即可就位并同步依赖。

## 隐私

全程在本机完成：不上传、不遥测、不登录，核心代码不发起任何网络请求。所有中间产物只落在当前目录的 `.recapkits/`，可随时删除。

## 非目标（v1）

不做托管服务与接收数据的网页；不做账号登录与抓取，只用官方导出与本地文件；不做移动端 App；不做 dashboard；不推断健康状况、精神状态或亲密关系——数据只描述行为，不解释人。

## 许可证

MIT，见 [LICENSE](LICENSE)。
