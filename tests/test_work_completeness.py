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


def test_sql_bits_match_python_flags(completeness_db):
    conn = sqlite3.connect(str(completeness_db))
    conn.execute(
        """
        INSERT INTO work (
            serial_number, director, release_date, runtime,
            cn_title, jp_title, cn_story, jp_story,
            maker_id, label_id, series_id, image_url, fanart
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "BITS-1",
            "D",
            "2022-02-02",
            95,
            "中题",
            "日题",
            "",
            "日简",
            1,
            0,
            3,
            "cover.jpg",
            json.dumps([{"url": "https://x.example/f1.jpg"}]),
        ),
    )
    wid = conn.execute(
        "SELECT work_id FROM work WHERE serial_number = ?",
        ("BITS-1",),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO work_actress_relation (work_id, actress_id) VALUES (?, ?)",
        (wid, 200),
    )
    conn.execute(
        "INSERT INTO work_tag_relation (work_id, tag_id) VALUES (?, ?)",
        (wid, 300),
    )
    conn.commit()

    sql = """
    WITH work_completeness_flags AS (
    SELECT
        w.work_id,
        CASE WHEN TRIM(COALESCE(w.image_url, '')) <> '' THEN 1 ELSE 0 END AS f_cover,
        CASE WHEN COALESCE(wa.actress_cnt, 0) > 0 THEN 1 ELSE 0 END AS f_actress,
        CASE WHEN COALESCE(wo.actor_cnt, 0) > 0 THEN 1 ELSE 0 END AS f_actor,
        CASE WHEN TRIM(COALESCE(w.director, '')) <> '' THEN 1 ELSE 0 END AS f_director,
        CASE WHEN TRIM(COALESCE(w.release_date, '')) <> '' THEN 1 ELSE 0 END AS f_release_date,
        CASE
            WHEN CAST(COALESCE(NULLIF(TRIM(COALESCE(w.runtime, '')), ''), '0') AS INTEGER) > 0
                THEN 1
            ELSE 0
        END AS f_runtime,
        CASE WHEN COALESCE(wt.tag_cnt, 0) > 0 THEN 1 ELSE 0 END AS f_tag,
        CASE WHEN TRIM(COALESCE(w.cn_title, '')) <> '' THEN 1 ELSE 0 END AS f_cn_title,
        CASE WHEN TRIM(COALESCE(w.jp_title, '')) <> '' THEN 1 ELSE 0 END AS f_jp_title,
        CASE WHEN TRIM(COALESCE(w.cn_story, '')) <> '' THEN 1 ELSE 0 END AS f_cn_story,
        CASE WHEN TRIM(COALESCE(w.jp_story, '')) <> '' THEN 1 ELSE 0 END AS f_jp_story,
        CASE WHEN COALESCE(w.maker_id, 0) > 0 THEN 1 ELSE 0 END AS f_maker,
        CASE WHEN COALESCE(w.label_id, 0) > 0 THEN 1 ELSE 0 END AS f_label,
        CASE WHEN COALESCE(w.series_id, 0) > 0 THEN 1 ELSE 0 END AS f_series,
        CASE
            WHEN json_valid(COALESCE(w.fanart, ''))
                 AND json_type(w.fanart) = 'array'
                 AND json_array_length(w.fanart) > 0
                THEN 1
            ELSE 0
        END AS f_fanart
    FROM work w
    LEFT JOIN (
        SELECT work_id, COUNT(1) AS actress_cnt
        FROM work_actress_relation
        GROUP BY work_id
    ) wa ON wa.work_id = w.work_id
    LEFT JOIN (
        SELECT work_id, COUNT(1) AS actor_cnt
        FROM work_actor_relation
        GROUP BY work_id
    ) wo ON wo.work_id = w.work_id
    LEFT JOIN (
        SELECT work_id, COUNT(1) AS tag_cnt
        FROM work_tag_relation
        GROUP BY work_id
    ) wt ON wt.work_id = w.work_id
    )
    SELECT
        CAST(f_cover AS TEXT)
        || CAST(f_actress AS TEXT)
        || CAST(f_actor AS TEXT)
        || CAST(f_director AS TEXT)
        || CAST(f_release_date AS TEXT)
        || CAST(f_runtime AS TEXT)
        || CAST(f_tag AS TEXT)
        || CAST(f_cn_title AS TEXT)
        || CAST(f_jp_title AS TEXT)
        || CAST(f_cn_story AS TEXT)
        || CAST(f_jp_story AS TEXT)
        || CAST(f_maker AS TEXT)
        || CAST(f_label AS TEXT)
        || CAST(f_series AS TEXT)
        || CAST(f_fanart AS TEXT) AS bits
    FROM work_completeness_flags
    WHERE work_id = ?
    """
    sql_bits = conn.execute(sql, (wid,)).fetchone()[0]
    conn.close()

    flags = read_work_completeness_flags(wid, database=str(completeness_db))
    py_bits = "".join("1" if flags[k] else "0" for k in WORK_COMPLETENESS_KEYS)
    assert sql_bits == py_bits
