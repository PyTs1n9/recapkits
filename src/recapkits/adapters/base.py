"""适配器契约: 检测、导入、导入报告。

只有一个适配器, 所以这里没有工厂、没有注册表、没有插件加载器。
等到第三个适配器出现, 再谈 entry point 注册。
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Protocol


@dataclass
class IngestReport:
    """一次导入的账目; 只有计数与时间, 不含任何路径。"""

    source: str
    units: int
    rows: int
    skipped: int
    coverage: float
    first_ts: str | None
    last_ts: str | None
    src_hash: str
    warnings: list[str] = field(default_factory=list)


class Adapter(Protocol):
    """把一个目录里的导出解析成 events。"""

    id: str
    description: str

    def detect(self, path: Path) -> float:
        """返回 0..1 的置信度; 0 表示这个目录完全不像本适配器的输入。"""
        ...

    def ingest(
        self,
        path: Path,
        conn: sqlite3.Connection,
        *,
        since: date | None = None,
        until: date | None = None,
    ) -> IngestReport:
        """解析并写入; 单个单元失败只记警告, 不中断整次导入。"""
        ...
