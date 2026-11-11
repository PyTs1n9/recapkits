"""测试共享夹具。"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from recapkits.db import connect, init_schema


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """空的、已按契约建表的数据库连接。"""
    connection = connect(tmp_path / "recap.db")
    init_schema(connection)
    yield connection
    connection.close()
