# 数据库连接管理

import sqlite3
from sqlite3 import Connection, Cursor


def get_connection(database, readonly=False) -> Connection:
    """
    获取一个SQLite连接，并开启 WAL 与 外键约束
    readonly: True -> 只读模式
    """
    mode = "ro" if readonly else "rwc"  # ro=只读, rwc=可读写，不存在则创建
    conn = sqlite3.connect(f"file:{database}?mode={mode}", uri=True)
    cursor: Cursor = conn.cursor()

    # 开启 WAL 模式
    #cursor.execute("PRAGMA journal_mode=WAL;")#这个只需要设置一次就可以了，这个数文件属性
    #conn.execute("PRAGMA synchronous=NORMAL")  # 性能更好，我不需要那么高的性能
    # 开启外键约束
    cursor.execute("PRAGMA foreign_keys=ON;")
    # 设置繁忙超时
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn
