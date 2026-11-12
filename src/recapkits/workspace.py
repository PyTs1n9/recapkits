"""工作区布局: 所有产物只落在当前目录的 .recapkits/ 下, 没有全局缓存。

`load_workspace` 在未初始化时返回 None, 由调用方决定怎么提示, 这样本模块
不需要认识 CLI 的错误类型。
"""

import json
from dataclasses import dataclass
from pathlib import Path

WORKSPACE = ".recapkits"
GITIGNORE_ENTRY = ".recapkits/"
GITIGNORE_HEADER = "# recapkits 工作区, 含用户数据, 永不提交"


@dataclass(frozen=True)
class Workspace:
    """工作区根目录与配置。

    `local_only` 是工作区策略而不是一次性开关: 一次设置, 所有命令一致 ——
    做成每条命令的 flag 就一定会忘, 而这条策略守的是「数据不出本机」。
    """

    root: Path
    tz: str
    year: int
    local_only: bool = False

    @property
    def db_path(self) -> Path:
        return self.root / "recap.db"

    @property
    def out_path(self) -> Path:
        return self.root / "out" / "insights.json"

    @property
    def story_path(self) -> Path:
        return self.root / "story.json"


def load_workspace(root: Path | None = None) -> Workspace | None:
    """读工作区配置; 未初始化时返回 None。"""
    base = root if root is not None else Path.cwd() / WORKSPACE
    config_path = base / "config.json"
    if not config_path.is_file():
        return None
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return Workspace(
        root=base,
        tz=str(data["tz"]),
        year=int(data["year"]),
        local_only=bool(data.get("local_only", False)),
    )


def ensure_gitignore(root: Path | None = None) -> None:
    """把 .recapkits/ 写进 .gitignore, 避免用户把自己的数据提交上去。"""
    base = root if root is not None else Path.cwd()
    path = base / ".gitignore"
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        if GITIGNORE_ENTRY in text.splitlines():
            return
        suffix = "" if text.endswith("\n") else "\n"
        path.write_text(
            f"{text}{suffix}\n{GITIGNORE_HEADER}\n{GITIGNORE_ENTRY}\n", encoding="utf-8"
        )
        return
    path.write_text(f"{GITIGNORE_HEADER}\n{GITIGNORE_ENTRY}\n", encoding="utf-8")
