"""适配器契约: 检测、导入、导入报告。

适配器是**内置**的: 每个一等源都随包发布, 由 `commands.ADAPTERS` 这张有序表注册。
entry point 发现留给第三方插件阶段 —— 它会让 `detect()` 的顺序依赖安装顺序,
破坏确定性, 而本阶段没有第三方插件要接。

`IngestReport.files` 是逐文件账目: 除整份损坏的文件外, 每个文件都满足
`rows + skipped == 源文件行数`, 且 `skipped` 等于各条原因的计数之和。
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class FileLedger:
    """一个文件的账: 解析多少行、跳过多少行、每个原因各多少条。

    `problem` 非空表示整份文件读不出来 (坏 JSON、编码不对、顶层不是数组)。
    这时行数本身不可知, 恒等式对它不适用, 报告里必须显式写「整份跳过」。
    """

    name: str
    rows: int = 0
    skipped: int = 0
    reasons: dict[str, int] = field(default_factory=dict)
    problem: str | None = None

    @property
    def total(self) -> int:
        """源文件里我们认得的行数; 整份损坏的文件为 0。"""
        return self.rows + self.skipped


@dataclass
class IngestReport:
    """一次导入的账目; 只有计数与时间, 不含任何路径。"""

    source: str
    units: int
    rows: int
    skipped: int
    first_ts: str | None
    last_ts: str | None
    src_hash: str
    coverage: float | None = None
    warnings: list[str] = field(default_factory=list)
    files: list[FileLedger] = field(default_factory=list)


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
        tz: str = "UTC",
    ) -> IngestReport:
        """解析并写入; 单个单元失败只记警告, 不中断整次导入。

        `tz` 只给「源自带 UTC 但无本地偏移」的源用 (spotify / netflix):
        它们要用工作区时区才能算出 `--since/--until` 该比哪一天。
        git 这类自带偏移的源忽略它。
        """
        ...
