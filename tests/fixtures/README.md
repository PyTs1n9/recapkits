"""测试数据目录。

只放**合成**数据，永不提交真实导出。真实导出即使脱敏也不进 git：
一行人名、一条时间戳就足够反查到具体的人。

- git 适配器的语料由测试内联构造（`tests/golden/test_insights_git.py` 用
  `tmp_path` 现场建固定日期、固定提交信息的仓库），本目录没有它的静态文件。
- `spotify/` 由 `scripts/make-fixtures.py` 生成，固定 seed，逐字节可复现。
  `python scripts/make-fixtures.py --check` 证明文件没有被手改。
- `netflix/` 同样由脚本生成：两个档案、两份不同列序的 `ViewingActivity.csv`，
  外加续播重复、1–2 秒预览与 HOOK/RECAP/TRAILER 行。
- 真实导出的特征文件名（`*Streaming_History_Audio*`、`ViewingActivity.csv`、
  大于 1 MB 的 `export.xml`）只允许出现在本目录；CI 会拦住其他地方的同名文件。
"""
