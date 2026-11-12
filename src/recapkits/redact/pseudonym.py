"""一致化假名: 盐 + HMAC 排序键 + 天干序号。

**为什么不用 `hash(name) % N`。** Python 的字符串哈希每个进程都不同, 同一次运行
里也不保证不同名字落在不同序号上。碰撞之后同一个实体在两份文件里叫两个名字,
比不脱敏更难解释。

**为什么不按原名排序。** 甲乙丙丁的先后会泄露原名的字典序 —— 拿到脱敏故事的人
能推断"你有一个 A 开头的项目"。用 `HMAC-SHA256(salt, name)` 的字节序当排序键:
稳定、不可预测、不碰撞。盐落盘, 所以删掉 `.recapkits/` 之外重跑仍然一致;
盐丢了就重新分配, 报告里会提示。

序号用天干而不是阿拉伯数字: 假名会作为 `label` 进文案, 而 V2 会拦手写数字。
超过十个实体时按两位天干拼接 (`甲甲`, `甲乙`, ...), 仍然唯一、无数字。
"""

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

SALT_BYTES = 16
STEMS = "甲乙丙丁戊己庚辛壬癸"
KIND_PREFIX = {"repo": "项目", "artist": "艺人", "show": "剧集"}
DEFAULT_PREFIX = "实体"


class PseudonymError(ValueError):
    """盐或映射文件不合法, 或实体数量超出天干组合。"""


def new_salt() -> str:
    """隐私参数不是可复现实验, 用 `secrets` 而不是 `random`。"""
    return secrets.token_hex(SALT_BYTES)


def valid_salt(text: str) -> bool:
    return len(text) == SALT_BYTES * 2 and all(char in "0123456789abcdef" for char in text)


def stem(index: int) -> str:
    """0 -> 甲, 9 -> 癸, 10 -> 甲甲, 19 -> 甲癸, 20 -> 乙甲。"""
    if index < 0:
        raise PseudonymError(f"假名序号不能为负: {index}")
    if index < len(STEMS):
        return STEMS[index]
    high, low = divmod(index, len(STEMS))
    if high > len(STEMS):
        raise PseudonymError("实体超过 100 个: 两位天干不够用, 请先缩小数据范围")
    return STEMS[high - 1] + STEMS[low]


@dataclass
class Book:
    """一次脱敏使用的盐与映射; `map` 是"原名 -> 假名", 也是唯一的状态。"""

    salt: str
    map: dict[str, str] = field(default_factory=dict)

    def sort_key(self, name: str) -> bytes:
        """HMAC 字节序; 盐是十六进制, 名字按 UTF-8 编码。"""
        return hmac.new(bytes.fromhex(self.salt), name.encode("utf-8"), hashlib.sha256).digest()

    def assign(self, kinds: dict[str, str]) -> list[str]:
        """为尚无假名的实体分配名字; 返回本次新分配的原文, 顺序即分配顺序。

        已有的映射一个都不动 —— 那是"重跑两次产物逐字节一致"的全部依据。
        新名字从 `len(map)` 继续编号, 所以先来后到也不会重排。
        """
        fresh = sorted((name for name in kinds if name not in self.map), key=self.sort_key)
        start = len(self.map)
        for offset, name in enumerate(fresh):
            prefix = KIND_PREFIX.get(kinds[name], DEFAULT_PREFIX)
            self.map[name] = prefix + stem(start + offset)
        return fresh


def load(path: Path) -> Book | None:
    """读映射文件; 不存在返回 None, 存在但不合法直接报错 (不猜)。"""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PseudonymError(f"{path} 不是合法 JSON: {exc.msg} (第 {exc.lineno} 行)") from exc
    if not isinstance(data, dict):
        raise PseudonymError(f"{path} 顶层必须是对象")
    salt = data.get("salt")
    mapping = data.get("map")
    if not isinstance(salt, str) or not valid_salt(salt):
        raise PseudonymError(f"{path} 的 salt 必须是 {SALT_BYTES * 2} 位十六进制")
    if not isinstance(mapping, dict) or any(
        not isinstance(key, str) or not isinstance(value, str) for key, value in mapping.items()
    ):
        raise PseudonymError(f"{path} 的 map 必须是字符串到字符串的对象")
    return Book(salt=salt.lower(), map=dict(mapping))


def save(path: Path, book: Book) -> None:
    """原子写入: 中途失败不能留下半个映射, 否则下一次会重新分配已用过的序号。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"salt": book.salt, "map": dict(sorted(book.map.items()))}
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    temp = path.with_name(path.name + ".tmp")
    temp.write_bytes(text.encode("utf-8"))
    os.replace(temp, path)
