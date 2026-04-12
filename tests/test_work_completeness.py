"""read_work_completeness_flags：库内 15 维完整度（独立 SQLite 文件）。"""

from __future__ import annotations

import json
import sqlite3

import pytest

from core.database.query.work_completeness import (
    WORK_COMPLETENESS_KEYS,
    read_work_completeness_flags,
)


def _schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE work (
            work_id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_number TEXT NOT NULL UNIQUE,
            director TEXT,
            release_date TEXT,
            runtime INTEGER,
            cn_title TEXT,
            jp_title TEXT,
            cn_story TEXT,
            jp_story TEXT,
            maker_id INTEGER,
            label_id INTEGER,
            series_id INTEGER,
            image_url TEXT,
            fanart TEXT
        );
        CREATE TABLE work_tag_relation (
            work_id INTEGER,
            tag_id INTEGER
        );
        CREATE TABLE work_actress_relation (
            work_id INTEGER,
            actress_id INTEGER
        );
        CREATE TABLE work_actor_relation (
            work_id INTEGER,
            actor_id INTEGER
        );
        """
    )


@pytest.fixture
def completeness_db(tmp_path):
    db_path = tmp_path / "completeness.db"
    conn = sqlite3.connect(str(db_path))
    _schema(conn)
    conn.commit()
    conn.close()
    return db_path


def test_invalid_work_id_returns_all_false(completeness_db):
    assert read_work_completeness_flags(None) == {
        k: False for k in WORK_COMPLETENESS_KEYS
    }
    assert read_work_completeness_flags(0) == {k: False for k in WORK_COMPLETENESS_KEYS}
    assert read_work_completeness_flags(-1) == {
        k: False for k in WORK_COMPLETENESS_KEYS
    }


def test_missing_row_all_false(completeness_db):
    assert read_work_completeness_flags(99, database=str(completeness_db)) == {
        k: False for k in WORK_COMPLETENESS_KEYS
    }


def test_minimal_row_mostly_false(completeness_db):
    conn = sqlite3.connect(str(completeness_db))
    conn.execute(
        "INSERT INTO work (serial_number) VALUES (?)",
        ("ABC-001",),
    )
    wid = conn.execute("SELECT work_id FROM work").fetchone()[0]
    conn.commit()
    conn.close()

    f = read_work_completeness_flags(wid, database=str(completeness_db))
    assert f["cover"] is False
    assert f["actress"] is False
    assert f["runtime"] is False
    assert f["fanart"] is False


def test_runtime_zero_is_false(completeness_db):
    conn = sqlite3.connect(str(completeness_db))
    conn.execute(
        """
        INSERT INTO work (
            serial_number, runtime, jp_title
        ) VALUES (?, ?, ?)
        """,
        ("RUN-0", 0, "t"),
    )
    wid = conn.execute("SELECT work_id FROM work").fetchone()[0]
    conn.commit()
    conn.close()
    f = read_work_completeness_flags(wid, database=str(completeness_db))
    assert f["runtime"] is False
    assert f["jp_title"] is True


def test_fanart_json_edge_cases(completeness_db):
    conn = sqlite3.connect(str(completeness_db))
    for sn, fanart, expect in [
        ("F1", "", False),
        ("F2", "[]", False),
        ("F3", "not json", False),
        ("F4", json.dumps([{"url": "https://x.example/a.jpg"}]), True),
    ]:
        conn.execute(
            "INSERT INTO work (serial_number, fanart) VALUES (?, ?)",
            (sn, fanart),
        )
    conn.commit()
    rows = conn.execute(
        "SELECT work_id, serial_number FROM work ORDER BY serial_number"
    ).fetchall()
    conn.close()
    by_sn = {r[1]: r[0] for r in rows}
    db = str(completeness_db)
    assert read_work_completeness_flags(by_sn["F1"], database=db)["fanart"] is False
    assert read_work_completeness_flags(by_sn["F2"], database=db)["fanart"] is False
    assert read_work_completeness_flags(by_sn["F3"], database=db)["fanart"] is False
    assert read_work_completeness_flags(by_sn["F4"], database=db)["fanart"] is True


def test_full_row_all_true(completeness_db):
    conn = sqlite3.connect(str(completeness_db))
    conn.execute(
        """
        INSERT INTO work (
            serial_number, director, release_date, runtime,
            cn_title, jp_title, cn_story, jp_story,
            maker_id, label_id, series_id,
            image_url, fanart
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "FULL-1",
            "D",
            "2020-01-01",
            120,
            "中",
            "日",
            "中剧",
            "日剧",
            1,
            2,
            3,
            "cover.jpg",
            json.dumps([{"url": "https://x.example/f.jpg"}]),
        ),
    )
    wid = conn.execute("SELECT work_id FROM work").fetchone()[0]
    conn.execute(
        "INSERT INTO work_tag_relation (work_id, tag_id) VALUES (?, ?)",
        (wid, 10),
    )
    conn.execute(
        "INSERT INTO work_actress_relation (work_id, actress_id) VALUES (?, ?)",
        (wid, 20),
    )
    conn.execute(
        "INSERT INTO work_actor_relation (work_id, actor_id) VALUES (?, ?)",
        (wid, 30),
    )
    conn.commit()
    conn.close()

    f = read_work_completeness_flags(wid, database=str(completeness_db))
    for k in WORK_COMPLETENESS_KEYS:
        assert f[k] is True, k
