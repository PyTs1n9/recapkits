"""`recap redact`: 数据层脱敏 + 审计, 可选接着出片。

路径规则只有一条: 默认读工作区, 显式参数优先。映射文件始终落在工作区根
(`.recapkits/redactions.json`), 不在 `--out` 目录里 —— 换一个输出目录不该让盐
跟着换, 那会把"两次产物可比"这件事悄悄破坏掉。
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from recapkits.errors import RecapError
from recapkits.redact import report as audit_report
from recapkits.redact.apply import redact_pair, write_pair
from recapkits.redact.pseudonym import Book, PseudonymError, load, new_salt, save
from recapkits.redact.text import read_words
from recapkits.render.cli import cmd_render
from recapkits.story.load import load_json
from recapkits.workspace import load_workspace

SUPPRESSION_FILE = "redact.txt"


@dataclass(frozen=True)
class Paths:
    """一次 redact 的四个落点。"""

    insights: Path
    story: Path
    out: Path
    book: Path


def _require(path: Path, label: str, hint: str) -> Path:
    if not path.is_file():
        raise RecapError(f"{label} 不存在: {path}\n{hint}")
    return path


def _resolve(args: argparse.Namespace) -> Paths:
    workspace = load_workspace()
    if workspace is not None:
        out = Path(args.out).expanduser() if args.out else workspace.root / "redacted"
        book = workspace.root / "redactions.json"
        insights = Path(args.insights).expanduser() if args.insights else workspace.out_path
        story = Path(args.story).expanduser() if args.story else workspace.story_path
    else:
        if not args.out:
            raise RecapError("未找到工作区: 先 recap init, 或用 --out 指定输出目录")
        out = Path(args.out).expanduser()
        book = out.parent / "redactions.json"
        if not args.insights or not args.story:
            raise RecapError("没有工作区时, --insights 与 --story 都必须显式给出")
        insights = Path(args.insights).expanduser()
        story = Path(args.story).expanduser()
    return Paths(
        insights=_require(insights, "insights.json", "先运行 recap insights"),
        story=_require(story, "story.json", "先运行 recap story --auto, 或手写一份"),
        out=out,
        book=book,
    )


def _year(payload: dict[str, object]) -> int:
    meta = payload.get("meta")
    if isinstance(meta, dict):
        year = meta.get("year")
        if isinstance(year, int):
            return year
    return 0


def _render(args: argparse.Namespace, paths: Paths, year: int) -> int:
    """脱敏产物出片; 文件名带 `-redacted`, 绝不覆盖原工作区的正常产物。"""
    name = f"recap-{year}-redacted"
    common = {
        "story": str(paths.out / "story.json"),
        "insights": str(paths.out / "insights.json"),
        "aspect": "9:16",
        "fps": 30,
        "allow_sensitive": bool(args.allow_sensitive),
        "allow_unknown_names": bool(args.allow_unknown_names),
    }
    code = cmd_render(
        argparse.Namespace(format="html", out=str(paths.out / f"{name}.html"), **common)
    )
    if code != 0:
        return code
    return cmd_render(
        argparse.Namespace(format="mp4", out=str(paths.out / f"{name}.mp4"), **common)
    )


def cmd_redact(args: argparse.Namespace) -> int:
    """读两份 JSON, 脱敏, 写两份 JSON; `--report` 只审计。"""
    if args.report and args.render:
        raise RecapError("--report 与 --render 互斥: 审计不落盘, 没有产物可出片")
    paths = _resolve(args)
    insights = load_json(paths.insights, "insights.json")
    story = load_json(paths.story, "story.json")

    try:
        book = load(paths.book)
    except PseudonymError as exc:
        raise RecapError(str(exc)) from exc
    created = book is None
    if book is None:
        book = Book(salt=new_salt())

    try:
        result = redact_pair(
            insights,
            story,
            book=book,
            words=read_words(Path.cwd() / SUPPRESSION_FILE),
        )
    except PseudonymError as exc:
        raise RecapError(str(exc)) from exc

    if args.report:
        note = "未找到 redactions.json, 本次审计使用临时盐, 未落盘" if created else None
        audit_report.render(result.audit, salt_note=note)
        print("--report 只审计, 未写入任何文件", file=sys.stderr)
        return 0

    try:
        save(paths.book, book)
        out_insights, out_story = write_pair(paths.out, result.insights, result.story)
    except OSError as exc:
        raise RecapError(f"写不了脱敏产物: {exc}") from exc

    print(f"已写入 {out_insights.resolve()}")
    print(f"已写入 {out_story.resolve()}")
    note = "首次生成盐, 已写入 redactions.json" if created else None
    audit_report.render(result.audit, salt_note=note)
    if args.render:
        return _render(args, paths, _year(result.story))
    return 0
