import os
from pathlib import Path

import pytest
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.database.backup_utils import _copy_tree
from core.database.backup_utils import _copy_tree, restore_backup_safely


def test_copy_tree_src_not_exists(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"

    assert not src.exists()
    _copy_tree(src, dst, overwrite=True)

    # 不会抛异常，也不会创建 dst
    assert not dst.exists()


def test_copy_tree_basic_copy(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"

    # 准备源目录结构
    (src / "sub").mkdir(parents=True)
    (src / "file1.txt").write_text("hello", encoding="utf-8")
    (src / "sub" / "file2.txt").write_text("world", encoding="utf-8")

    _copy_tree(src, dst, overwrite=True)

    assert (dst / "file1.txt").read_text(encoding="utf-8") == "hello"
    assert (dst / "sub" / "file2.txt").read_text(encoding="utf-8") == "world"


def test_copy_tree_no_overwrite(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"

    src.mkdir()
    dst.mkdir()

    (src / "file.txt").write_text("from_src", encoding="utf-8")
    (dst / "file.txt").write_text("from_dst", encoding="utf-8")

    _copy_tree(src, dst, overwrite=False)

    # 目标文件不应被覆盖
    assert (dst / "file.txt").read_text(encoding="utf-8") == "from_dst"


def test_copy_tree_overwrite(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"

    src.mkdir()
    dst.mkdir()

    (src / "file.txt").write_text("from_src", encoding="utf-8")
    (dst / "file.txt").write_text("from_dst", encoding="utf-8")

    _copy_tree(src, dst, overwrite=True)

    # 目标文件应被覆盖
    assert (dst / "file.txt").read_text(encoding="utf-8") == "from_src"


import sqlite3


def _init_db(path: Path, rows: list[tuple[str]]):
    """在给定路径创建一个简单表 test_table，并插入若干行"""
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE test_table (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)"
        )
        conn.executemany(
            "INSERT INTO test_table (name) VALUES (?)", [(r,) for r in rows]
        )
        conn.commit()
    finally:
        conn.close()


def _fetch_all_names(path: Path) -> list[str]:
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute("SELECT name FROM test_table ORDER BY id")
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def test_restore_backup_safely_success(tmp_path):
    backup_db = tmp_path / "backup.db"
    active_db = tmp_path / "active.db"

    # 备份库：我们期望恢复成的内容
    _init_db(backup_db, ["alice", "bob"])

    # 活动库：当前已有的内容（会被覆盖）
    _init_db(active_db, ["old1", "old2", "old3"])

    ok = restore_backup_safely(backup_db, active_db)
    assert ok is True

    # 恢复后，active 应该和 backup 一致
    names = _fetch_all_names(active_db)
    assert names == ["alice", "bob"]


def test_restore_backup_safely_backup_not_exists(tmp_path):
    backup_db = tmp_path / "not_exists.db"
    active_db = tmp_path / "active.db"

    # 先创建一个合法的 active 库
    _init_db(active_db, ["keep"])

    ok = restore_backup_safely(backup_db, active_db)
    # 调用不应抛异常，但应返回 False
    assert ok is False

    # active 库内容不应被修改
    names = _fetch_all_names(active_db)
    assert names == ["keep"]
