"""去名载荷与还原: 真 insights 不变、零原名、还原性质、渲染前还原。

性质测试比手写一份"agent 故事"更强: 任何 copy 写法都能被 `restore(redact(x)) == x`
覆盖, 而手写样例只覆盖我们想到的那几种。
"""

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

from recapkits.cli import main
from recapkits.db import Event, connect, init_schema, insert_events
from recapkits.redact import restore
from recapkits.redact.apply import redact_pair, write_pair
from recapkits.redact.pseudonym import Book
from recapkits.render.pipeline import load_input
from recapkits.story.bake import bake
from recapkits.tz import rebuild_local, to_utc_iso

FIXTURES = Path(__file__).parent.parent / "fixtures"
TZ = "Asia/Shanghai"
SALT = "0123456789abcdef" * 2
BASE = datetime(2024, 1, 1, tzinfo=UTC)


def _pair() -> tuple[dict, dict]:
    """fixture 里 `alpha` 同时出现在 id、rank 标题与 copy 里, 适合测还原。"""
    insights = json.loads((FIXTURES / "insights.json").read_text(encoding="utf-8"))
    story = json.loads((FIXTURES / "story-render.json").read_text(encoding="utf-8"))
    return insights, story


def _table(result, book: Book) -> restore.Restore:
    return restore.Restore(
        salt=book.salt,
        ids={
            fake: real for real, fake in result.id_map.items() if real not in result.suppressed_ids
        },
        names={pseudo: real for real, pseudo in book.map.items()},
    )


def test_restore_undoes_redact_on_a_clean_fixture() -> None:
    insights, story = _pair()
    original = deepcopy(story)
    book = Book(salt=SALT)

    result = redact_pair(insights, story, book=book, words=[])

    assert result.story["cards"] != original["cards"]
    assert restore.apply(result.story, _table(result, book))["cards"] == original["cards"]


def test_pii_never_comes_back() -> None:
    insights, story = _pair()
    story["cards"][0]["copy"]["kicker"] = "联系 me@example.com"
    book = Book(salt=SALT)

    result = redact_pair(insights, story, book=book, words=[])

    text = json.dumps(restore.apply(result.story, _table(result, book)), ensure_ascii=False)
    assert "me@example.com" not in text
    assert "example.com" not in text


def test_a_suppressed_name_never_comes_back() -> None:
    """抑制词不进 names, 它的 id 也不进 ids: 顺着 id 还原等于绕过抑制表。"""
    insights, story = _pair()
    book = Book(salt=SALT)

    result = redact_pair(insights, story, book=book, words=["alpha"])

    table = _table(result, book)
    assert "alpha" not in table.names.values()
    assert all("alpha" not in real for real in table.ids.values())
    text = json.dumps(restore.apply(result.story, table), ensure_ascii=False)
    assert "alpha" not in text


def test_render_input_restores_before_validation(tmp_path: Path) -> None:
    """还原发生在 validate 之前: 页面里原名回来, 假名消失。"""
    insights, story = _pair()
    book = Book(salt=SALT)
    result = redact_pair(deepcopy(insights), deepcopy(story), book=book, words=[])
    _, story_path = write_pair(tmp_path / "redacted", result.insights, result.story)
    table = _table(result, book)
    restore_path = restore.save(
        tmp_path / "agent" / "restore.json",
        restore.build(salt=table.salt, ids=table.ids, names=table.names),
    )
    full = tmp_path / "full.json"
    full.write_text(json.dumps(insights, ensure_ascii=False), encoding="utf-8")

    source = load_input(story_path, str(full), restore=restore_path)
    text = json.dumps(bake(source.story, source.refs), ensure_ascii=False)

    assert "alpha" in text
    assert "项目甲" not in text


def _seed_workspace(tmp_path: Path) -> Path:
    """三个仓库、40 个活跃日: 足以产出 conc.* 与 time.*。"""
    root = tmp_path / ".recapkits"
    root.mkdir()
    (root / "config.json").write_text(
        json.dumps({"tz": TZ, "year": 2024, "created_at": "2024-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    events = [
        Event(
            source="git",
            kind="commit",
            ts_utc=to_utc_iso(BASE + timedelta(days=day, hours=(slot * 7) % 24)),
            tz_offset_min=480,
            title=f"c{day}-{slot}",
            subtitle=f"repo-{slot}",
            value=1.0,
            row_hash=f"{day:04d}{slot:04d}00000000",
        )
        for day in range(40)
        for slot in range(2)
    ]
    conn = connect(root / "recap.db")
    try:
        init_schema(conn)
        insert_events(conn, events)
        rebuild_local(conn, TZ)
    finally:
        conn.close()
    return root


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_full_payload_is_untouched(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    root = _seed_workspace(tmp_path)
    assert main(["insights", "--top", "10"]) == 0
    before = _sha(root / "out" / "insights.json")
    capsys.readouterr()

    assert main(["insights", "--top", "10", "--entities=placeholder"]) == 0

    assert _sha(root / "out" / "insights.json") == before
    text = (root / "agent" / "insights.json").read_text(encoding="utf-8")
    assert "repo-0" not in text
    assert "repo-1" not in text
    assert "项目" in text
    assert (root / "agent" / "restore.json").is_file()
    assert (root / "redactions.json").is_file()
    assert "restore.json" in capsys.readouterr().out


def test_the_placeholder_payload_still_passes_story_check(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    root = _seed_workspace(tmp_path)
    assert main(["insights", "--top", "10", "--entities=placeholder"]) == 0
    assert main(["story", "--auto"]) == 0
    assert main(["redact"]) == 0
    capsys.readouterr()

    code = main(
        [
            "story",
            "--check",
            str(root / "redacted" / "story.json"),
            "--insights",
            str(root / "agent" / "insights.json"),
        ]
    )

    assert code == 0
    assert "通过" in capsys.readouterr().out


def test_the_restore_table_is_deterministic(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    root = _seed_workspace(tmp_path)
    assert main(["insights", "--top", "10", "--entities=placeholder"]) == 0
    first = _sha(root / "agent" / "restore.json")
    capsys.readouterr()

    assert main(["insights", "--top", "10", "--entities=placeholder"]) == 0

    assert _sha(root / "agent" / "restore.json") == first


def test_preview_watches_the_restore_table(tmp_path: Path) -> None:
    """改还原表要能触发刷新; 只盯着 story 会让预览停在旧名字上。"""
    from recapkits.render.preview import PreviewState

    table = tmp_path / "restore.json"
    state = PreviewState(
        story_path=tmp_path / "story.json",
        insights_path=None,
        restore=table,
        aspect="9:16",
        allow_sensitive=False,
        allow_unknown_names=False,
    )

    assert table in state._watched()
