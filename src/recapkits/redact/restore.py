"""读 `restore.json`, 把假名 story 还原成真名。

**还原只做两件事**: 卡片的 `insight` / `evidence` / 占位符 id 映射回真 id;
copy 里占位符之外的假名按长度降序换回原名。其余一个字不动。

**为什么不在渲染层还原**: 渲染层拿到的是烘焙后的字符串, 哪一段是假名已经丢了;
PNG / MP4 又共用同一条截图链路, 漏一层就是原名泄漏到画面里。还原必须发生在
数据层、`validate` 之前 —— 先用真 id 校验, 再烘焙。

**PII 与抑制词不在表里**: 移除标记是终态。用户点名要消失的词、邮箱、路径,
不该因为 render 又回到片子里; 还原把它们带回来等于背叛 redact 的承诺。
"""

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from recapkits.errors import RecapError
from recapkits.redact.pseudonym import valid_salt
from recapkits.redact.text import replace_entities
from recapkits.story.rules import PLACEHOLDER

VERSION = 1


@dataclass(frozen=True)
class Restore:
    """一次还原所需的全部映射; 两个 map 都是"假 -> 真"。"""

    salt: str
    ids: dict[str, str]
    names: dict[str, str]


def _string_map(value: object, field: str, path: Path) -> dict[str, str]:
    if not isinstance(value, dict) or any(
        not isinstance(key, str) or not isinstance(item, str) for key, item in value.items()
    ):
        raise RecapError(f"{path} 的 {field} 必须是字符串到字符串的对象")
    return dict(value)


def build(*, salt: str, ids: dict[str, str], names: dict[str, str]) -> dict[str, Any]:
    """还原表的落盘结构; 两个 map 按键排序, 同一份载荷两次运行逐字节一致。"""
    return {
        "version": VERSION,
        "salt": salt,
        "ids": dict(sorted(ids.items())),
        "names": dict(sorted(names.items())),
    }


def save(path: Path, payload: dict[str, Any]) -> Path:
    """写字节而不是 write_text: 行尾由我们决定, 不由平台决定。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_bytes(text.encode("utf-8"))
    return path


def load(path: Path) -> Restore:
    """版本、salt、两个 map 的类型都要校验; 坏了直接报错, 不猜。"""
    if not path.is_file():
        raise RecapError(f"还原表不存在: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RecapError(f"{path} 不是合法 JSON: {exc.msg} (第 {exc.lineno} 行)") from exc
    if not isinstance(data, dict):
        raise RecapError(f"{path} 顶层必须是对象")
    version = data.get("version")
    if version != VERSION:
        raise RecapError(f"{path} 的 version 只支持 {VERSION}, 收到 {version!r}")
    salt = data.get("salt")
    if not isinstance(salt, str) or not valid_salt(salt):
        raise RecapError(f"{path} 的 salt 必须是 32 位十六进制")
    return Restore(
        salt=salt.lower(),
        ids=_string_map(data.get("ids"), "ids", path),
        names=_string_map(data.get("names"), "names", path),
    )


def _restore_text(text: str, table: Restore) -> str:
    """先换占位符里的 id, 再只处理占位符之外的文字。

    顺序不能反: 占位符里的 id 是数据坐标, 不是文案; 对它做文本替换会把 id 改成
    一个非法片段, 校验器会报一个看起来毫不相关的错。
    """

    def swap(match: re.Match[str]) -> str:
        insight_id, dot, fact_key = match.group(1).rpartition(".")
        new_id = table.ids.get(insight_id) if dot else None
        return match.group(0) if new_id is None else "{{" + new_id + "." + fact_key + "}}"

    rewritten = PLACEHOLDER.sub(swap, text)
    pieces: list[str] = []
    cursor = 0
    for match in PLACEHOLDER.finditer(rewritten):
        prose = rewritten[cursor : match.start()]
        pieces.append(replace_entities(prose, table.names))
        pieces.append(match.group(0))
        cursor = match.end()
    pieces.append(replace_entities(rewritten[cursor:], table.names))
    return "".join(pieces)


def apply(payload: dict[str, Any], table: Restore) -> dict[str, Any]:
    """返回还原后的新 dict; 未在表里的 id 与假名原样保留。

    原样保留是有意的: 让校验器报出 `NAME_NOT_IN_EVIDENCE` 并指出那个词, 比悄悄
    删掉它有用 —— agent 编的拉丁词会走到这条路径上。
    """
    result = deepcopy(payload)
    cards = result.get("cards")
    for card in cards if isinstance(cards, list) else []:
        if not isinstance(card, dict):
            continue
        insight = card.get("insight")
        if isinstance(insight, str):
            card["insight"] = table.ids.get(insight, insight)
        evidence = card.get("evidence")
        if isinstance(evidence, list):
            card["evidence"] = [
                table.ids.get(item, item) if isinstance(item, str) else item for item in evidence
            ]
        copy = card.get("copy")
        if not isinstance(copy, dict):
            continue
        for slot, text in copy.items():
            if isinstance(text, str):
                copy[slot] = _restore_text(text, table)
    return result
