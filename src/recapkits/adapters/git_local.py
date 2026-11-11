"""git 适配器: 读本地仓库的提交历史, 不联网、不登录。

一个 commit 一条 event。`ts_utc` 由作者时间 `%aI` 转 UTC, `tz_offset_min` 取
`%aI` 自带的偏移(比用户配置的时区更可信), `subtitle` 是仓库目录名。

单个仓库失败(不是仓库、权限不足、git 不存在)只记警告, 继续下一个。
"""

import hashlib
import os
import shutil
import sqlite3
import subprocess
from datetime import date
from pathlib import Path

from recapkits.adapters.base import IngestReport
from recapkits.db import Event, insert_events
from recapkits.tz import local_datetime, split_utc_and_offset

SOURCE = "git"
KIND = "commit"
SKIP_DIRS = frozenset({"node_modules", ".venv", "venv", "dist", "build", ".recapkits"})
MAX_DEPTH = 3
FIELD_SEP = "\x1f"
LOG_FORMAT = f"%H{FIELD_SEP}%aI{FIELD_SEP}%cI{FIELD_SEP}%s"
TIMEOUT_S = 120


def find_repos(root: Path, max_depth: int = MAX_DEPTH) -> list[Path]:
    """向下最多 max_depth 层找仓库根; 命中仓库后不再深入, 避免子模块重复计数。"""
    root = root.resolve()
    if not root.is_dir():
        return []
    if (root / ".git").exists():
        return [root]

    repos: list[Path] = []
    base_depth = len(root.parts)
    for current, dirs, _files in os.walk(root):
        here = Path(current)
        if (here / ".git").exists():
            repos.append(here)
            dirs[:] = []
            continue
        if len(here.parts) - base_depth >= max_depth:
            dirs[:] = []
            continue
        dirs[:] = sorted(name for name in dirs if name not in SKIP_DIRS)
    return sorted(repos)


def _git_log(repo: Path) -> str:
    """返回 `git log` 的原始文本; 空仓库返回空串, 其他失败抛 RuntimeError。"""
    completed = subprocess.run(
        ["git", "-C", str(repo), "log", "--no-merges", f"--pretty=format:{LOG_FORMAT}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_S,
        check=False,
    )
    if completed.returncode == 0:
        return completed.stdout
    stderr = completed.stderr.strip()
    if "does not have any commits" in stderr or "ambiguous argument" in stderr:
        return ""
    raise RuntimeError(stderr or f"git log 退出码 {completed.returncode}")


def _count_merges(repo: Path) -> int:
    """合并提交数; `--no-merges` 把它们挡在输出之外, 但报告里要如实计数。"""
    completed = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "--merges", "--count", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_S,
        check=False,
    )
    if completed.returncode != 0:
        return 0
    try:
        return int(completed.stdout.strip() or 0)
    except ValueError:
        return 0


def _one_line(text: str, limit: int = 200) -> str:
    """把 git 的多行 stderr 压成一行, 保证报告里一条警告一行。"""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


def _parse_line(line: str, repo: Path) -> tuple[Event, str] | None:
    """把一行 `%H\\x1f%aI\\x1f%cI\\x1f%s` 变成 (event, 本地日期); 畸形行返回 None。"""
    parts = line.split(FIELD_SEP)
    if len(parts) != 4:
        return None
    commit_hash, author_iso, _committer_iso, subject = parts
    try:
        ts_utc, offset_min = split_utc_and_offset(author_iso)
    except ValueError:
        return None

    local_day = local_datetime(ts_utc, offset_min, "UTC").date().isoformat()
    row_hash = hashlib.sha256(f"{SOURCE}|{ts_utc}|{commit_hash}".encode()).hexdigest()[:16]
    event = Event(
        source=SOURCE,
        kind=KIND,
        ts_utc=ts_utc,
        tz_offset_min=offset_min,
        title=subject.strip() or "(无提交信息)",
        subtitle=repo.name,
        value=1.0,
        row_hash=row_hash,
    )
    return event, local_day


class GitAdapter:
    """本地 git 仓库适配器。"""

    id = SOURCE
    description = "本地 git 仓库的提交历史"

    def detect(self, path: Path) -> float:
        """目录本身是仓库为 1.0, 仅在子目录里发现仓库为 0.8, 否则 0.0。"""
        if not path.is_dir():
            return 0.0
        if (path / ".git").exists():
            return 1.0
        return 0.8 if find_repos(path) else 0.0

    def ingest(
        self,
        path: Path,
        conn: sqlite3.Connection,
        *,
        since: date | None = None,
        until: date | None = None,
    ) -> IngestReport:
        """扫描目录下的仓库并写入 events; 逐仓库容错。"""
        if shutil.which("git") is None:
            raise RuntimeError("未找到 git: 请先安装 git, 或等待 csv 适配器")

        repos = find_repos(path)
        if not repos:
            raise FileNotFoundError(f"{path} 的下 3 层内没有 git 仓库")

        events: list[Event] = []
        warnings: list[str] = []
        skipped = 0

        for repo in repos:
            try:
                output = _git_log(repo)
            except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
                warnings.append(f"{repo.name}: {_one_line(str(exc))}")
                continue

            skipped += _count_merges(repo)
            bad_lines = 0
            for line in output.splitlines():
                parsed = _parse_line(line, repo)
                if parsed is None:
                    bad_lines += 1
                    continue
                event, local_day = parsed
                if (since is not None and local_day < since.isoformat()) or (
                    until is not None and local_day > until.isoformat()
                ):
                    skipped += 1
                    continue
                events.append(event)
            if bad_lines:
                skipped += bad_lines
                warnings.append(f"{repo.name}: 跳过 {bad_lines} 行无法解析的提交")

        insert_events(conn, events)
        stamps = [event.ts_utc for event in events]
        return IngestReport(
            source=SOURCE,
            units=len(repos),
            rows=len(events),
            skipped=skipped,
            first_ts=min(stamps) if stamps else None,
            last_ts=max(stamps) if stamps else None,
            src_hash=hashlib.sha256(
                "\n".join(sorted(event.row_hash for event in events)).encode()
            ).hexdigest()[:16],
            warnings=warnings,
        )
