# recapkits

本地优先、插件化的「任意数据的年度回顾」引擎。把数据导出丢进来，在本机生成可分享的竖向故事卡片。不上传、不遥测、不需要账号。

## quickstart

```bash
uvx recapkits init --tz Asia/Shanghai
uvx recapkits import ~/code --source git
uvx recapkits insights --top 10
```

## 隐私

全程在本机完成：不上传、不遥测、不登录，核心代码不发起任何网络请求。所有中间产物只落在当前目录的 `.recapkits/`，可随时删除。

## 非目标（v1）

不做托管服务与接收数据的网页；不做账号登录与抓取，只用官方导出与本地文件；不做移动端 App；不做 dashboard；不推断健康状况、精神状态或亲密关系——数据只描述行为，不解释人。

## 许可证

MIT，见 [LICENSE](LICENSE)。
