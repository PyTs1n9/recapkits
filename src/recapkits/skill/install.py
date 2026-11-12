"""把 SKILL.md 装到当前项目: 四个 target、标记块、幂等、`--force`。

只写当前目录, 不碰用户家目录: skill 讲的是「这个工作区」的 `.recapkits/`,
装到 `~/.claude` 会跨项目误导, 也会在用户家目录留下我们无法测试的文件。

**先算完再写。** 多个 target 一起装时, 冲突要在落盘之前发现: 否则前一个已经
写了、后一个报错, 用户面对的是半成品加一句「加 --force」。
"""

from dataclasses import dataclass
from pathlib import Path

from recapkits.errors import RecapError
from recapkits.skill import read_text

__all__ = ["BLOCK_END", "BLOCK_START", "TARGETS", "Plan", "install", "merge_block", "render_for"]

BLOCK_START = "<!-- recapkits:skill:start -->"
BLOCK_END = "<!-- recapkits:skill:end -->"

TARGETS = ("claude", "cursor", "agents", "print")

#: 落点相对当前目录; `print` 不写文件, 因此没有条目。
DESTINATIONS: dict[str, Path] = {
    "claude": Path(".claude") / "skills" / "recapkits" / "SKILL.md",
    "cursor": Path(".cursor") / "rules" / "recapkits.mdc",
    "agents": Path("AGENTS.md"),
}

UNCHANGED = "unchanged"
WRITE = "write"
CONFLICT = "conflict"

CURSOR_HEADER = "---\ndescription: {description}\nglobs:\nalwaysApply: false\n---\n"


@dataclass(frozen=True)
class Plan:
    """一份待落盘的内容; status 决定 CLI 说「已写入」还是「未改动」。"""

    target: str
    path: Path
    payload: bytes
    status: str


def _split_frontmatter(text: str) -> tuple[str, str]:
    """拆成 (frontmatter 内容, 正文); 没有 frontmatter 时前者为空。"""
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 3)
    if end == -1:
        return "", text
    return text[4:end], text[end + len("\n---\n") :]


def _description(front: str) -> str:
    """从 SKILL.md 的 frontmatter 取 description; 缺失时用一句兜底。"""
    for line in front.splitlines():
        if line.startswith("description:"):
            return line[len("description:") :].strip()
    return "recapkits 工作区的年度回顾 skill"


def render_for(target: str, text: str) -> str:
    """按 target 决定 frontmatter: claude 原样, cursor 换头, agents 去头。"""
    if target in {"claude", "print"}:
        return text
    front, body = _split_frontmatter(text)
    if target == "agents":
        return body
    return CURSOR_HEADER.format(description=_description(front)) + body


def merge_block(existing: str, body: str, *, newline: str = "\n") -> str:
    """把正文放进标记块; 块外逐字不动, 没有标记就追加到末尾。

    `newline` 由调用方从原文探测: `AGENTS.md` 是用户的文件, 块外内容不能因为
    我们写入而改变行尾。
    """
    lines = [line.replace("\r", "") for line in body.strip("\n").split("\n")]
    block = newline.join([BLOCK_START, *lines, BLOCK_END])
    start = existing.find(BLOCK_START)
    end = existing.find(BLOCK_END, start + 1) if start != -1 else -1
    if start != -1 and end != -1:
        return existing[:start] + block + existing[end + len(BLOCK_END) :]
    if not existing:
        return block + newline
    prefix = existing if existing.endswith(newline) else existing + newline
    return prefix + newline + block + newline


def _plan_file(target: str, text: str, root: Path, force: bool) -> Plan:
    """整文件 target: 内容相同算未改动, 不同且没 --force 算冲突。"""
    path = root / DESTINATIONS[target]
    payload = text.encode("utf-8")
    if not path.is_file():
        return Plan(target, path, payload, WRITE)
    if path.read_bytes() == payload:
        return Plan(target, path, payload, UNCHANGED)
    return Plan(target, path, payload, WRITE if force else CONFLICT)


def _plan_block(text: str, root: Path) -> Plan:
    """AGENTS.md: 标记块是我们管理的区域, 块内直接替换, 不需要 --force。"""
    path = root / DESTINATIONS["agents"]
    if path.is_file():
        raw = path.read_bytes()
        try:
            existing = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RecapError(f"{path} 不是 UTF-8, 不敢改它: {exc}") from exc
        newline = "\r\n" if b"\r\n" in raw else "\n"
    else:
        existing, newline = "", "\n"
    payload = merge_block(existing, text, newline=newline).encode("utf-8")
    status = UNCHANGED if path.is_file() and payload == path.read_bytes() else WRITE
    return Plan("agents", path, payload, status)


def install(targets: list[str], *, root: Path, force: bool = False) -> list[Plan]:
    """规划全部 target, 有冲突就整体放弃, 否则按顺序落盘。"""
    text = read_text()
    plans: list[Plan] = []
    for target in targets:
        if target == "agents":
            plans.append(_plan_block(render_for("agents", text), root))
        else:
            plans.append(_plan_file(target, render_for(target, text), root, force))
    conflicts = [plan for plan in plans if plan.status == CONFLICT]
    if conflicts:
        detail = "\n".join(f"已存在不同的文件 {plan.path}; 加 --force 覆盖" for plan in conflicts)
        raise RecapError(detail)
    for plan in plans:
        if plan.status == UNCHANGED:
            continue
        plan.path.parent.mkdir(parents=True, exist_ok=True)
        # 写字节: 行尾由我们决定, 不由平台的 write_text 决定。
        plan.path.write_bytes(plan.payload)
    return plans
