"""完整 `insights.json` → 给 agent 的最小版。

**为什么另存一个文件, 而不是裁掉完整版**: heatmap / clock 要 `series`,
`--explain` 要 `score_parts`, 证据链审计要 `evidence_sql`。把完整版裁掉再让
渲染去别处找数据, 是把一个文件契约拆成两个。

**为什么最小版保留 `series`**: V3 要求被引洞察带正确轴的序列。去掉它, 这份
「给 agent 的载荷」就校验不了它自己催生的故事 —— 一个必须先还原才能校验的
载荷是陷阱。skill 里明确写了: `series` 是渲染数据, 不要读、不要引用。

最小化省下的不是字节, 是注意力: 20 KB → 17 KB 只是副产品, 真正删掉的是
agent 不该看到的决策过程 (`score_parts`) 与内部审计串 (`evidence_sql`)。
"""

import json
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

__all__ = ["DROPPED", "KEPT", "TOP_LEVEL", "Measurement", "measure", "minimize"]

#: 完整版顶层只有四项; 少一项也不补 —— 外部 payload 可能没有 generated_from。
TOP_LEVEL = ("version", "build_id", "generated_from")

#: 每条洞察保留的键, 顺序即输出顺序。`series` 在最后, 与 emit 的写法一致。
KEPT = (
    "id",
    "kind",
    "source",
    "period",
    "headline_fact",
    "facts",
    "score",
    "novelty",
    "sensitivity",
    "data_sufficiency",
    "gated",
    "caveats",
    "series",
)

#: 三个只对本地工具有意义的键; 值本身要计入「删除了多少字节」。
DROPPED = ("evidence_sql", "score_parts", "evidence_rows")


@dataclass(frozen=True)
class Measurement:
    """一次最小化的体积账; 字段名与 CLI 的三行输出一一对应。"""

    full_bytes: int
    agent_bytes: int
    count: int
    dropped: tuple[tuple[str, int], ...]

    @property
    def saved_bytes(self) -> int:
        return self.full_bytes - self.agent_bytes

    @property
    def saved_share(self) -> float:
        return self.saved_bytes / self.full_bytes if self.full_bytes else 0.0


def _size(value: object) -> int:
    """紧凑序列化后的 UTF-8 字节数; 与「贴给 agent」的那份同口径。"""
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def _key_cost(item: dict[str, Any], key: str) -> int:
    """删掉一个键能省下的字节, 含键名、引号与逗号。

    只报「值的字节」会低估: 任务书要的是三行明细之和等于总差值, 否则用户
    拿 3,164 的差额去对 2,732 的明细, 会以为我们算错了。
    """
    if key not in item:
        return 0
    return _size(item) - _size({name: value for name, value in item.items() if name != key})


def minimize(payload: dict[str, Any]) -> dict[str, Any]:
    """返回只含决策字段的新 payload; 输入不被修改。

    未知键一律丢弃: 外部 payload 可能有我们没见过的字段, 最小版不替它做决定。
    """
    result: dict[str, Any] = {key: deepcopy(payload[key]) for key in TOP_LEVEL if key in payload}
    raw = payload.get("insights")
    items = raw if isinstance(raw, list) else []
    result["insights"] = [
        {key: deepcopy(item[key]) for key in KEPT if key in item}
        for item in items
        if isinstance(item, dict)
    ]
    return result


def measure(payload: dict[str, Any]) -> Measurement:
    """算完整版与最小版的体积, 以及每个被删字段贡献的字节 (按降序)。"""
    raw = payload.get("insights")
    items = [item for item in (raw if isinstance(raw, list) else []) if isinstance(item, dict)]
    counted: Counter[str] = Counter()
    for item in items:
        for key in DROPPED:
            cost = _key_cost(item, key)
            if cost:
                counted[key] += cost
    agent = minimize(payload)
    return Measurement(
        full_bytes=_size(payload),
        agent_bytes=_size(agent),
        count=len(agent["insights"]),
        dropped=tuple(sorted(counted.items(), key=lambda pair: (-pair[1], pair[0]))),
    )
