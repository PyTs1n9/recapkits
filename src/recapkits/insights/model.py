"""洞察的数据结构: Fact / Period / Insight。

目录表里没有单独列这个文件; 它独立出来是为了让 engine 与 detectors 都能导入
而互不依赖(否则两者循环导入)。这里只有 dataclass, 没有任何逻辑。

字段与 docs/decisions/0001-contracts.md 的 `insights.json` 一一对应。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Fact:
    """一个可被文案引用的事实; `display` 是唯一允许进入文案的形态。"""

    key: str
    label: str
    value: float | str
    unit: str | None
    display: str


@dataclass(frozen=True)
class Period:
    """统计窗口: 本地日期的闭区间, 加上覆盖率 0..1。"""

    start: str
    end: str
    tz: str
    coverage: float


@dataclass(frozen=True)
class Insight:
    """一条候选洞察; 分数与分项由 scoring 填充, 检测器只负责事实与自报强度。

    `signal` 是检测器自报的 0..1 强度, 与 `score_parts["signal"]` 数值相同
    (权重为 1.00), 但语义不同: 前者是未加权的原始强度, 后者是已加权分量。
    """

    id: str
    kind: str
    source: str
    period: Period
    headline_fact: Fact
    facts: list[Fact]
    evidence_sql: str
    evidence_rows: int
    signal: float
    score: float
    score_parts: dict[str, float]
    novelty: str
    sensitivity: str
    data_sufficiency: str
    gated: list[str]
    caveats: list[str]
