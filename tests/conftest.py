"""测试共享夹具。"""

import os
import sqlite3
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from recapkits.db import connect, init_schema

GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "Test Author",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test Author",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}

#: 固定日期 + 固定消息; 配合 `--allow-empty` 得到跨平台一致的提交哈希。
COMMITS = (
    ("2024-03-11T23:41:07+08:00", "feat: 第一个提交"),
    ("2024-03-12T09:05:00+08:00", "fix: 第二个提交"),
    ("2024-05-02T08:00:00+08:00", "docs: 第三个提交"),
)


def run_git(repo: Path, *args: str, extra_env: dict[str, str] | None = None) -> str:
    """在指定仓库里执行 git, 身份与时间由环境变量固定。"""
    env = dict(os.environ)
    env.update(GIT_IDENTITY)
    if extra_env:
        env.update(extra_env)
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        env=env,
    )
    return completed.stdout


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """空的、已按契约建表的数据库连接。"""
    connection = connect(tmp_path / "recap.db")
    init_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """三次提交、日期与消息都固定的仓库。"""
    path = tmp_path / "demo-repo"
    path.mkdir()
    run_git(path, "init", "-q")
    for when, message in COMMITS:
        run_git(
            path,
            "commit",
            "--allow-empty",
            "-q",
            "-m",
            message,
            extra_env={"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when},
        )
    return path
