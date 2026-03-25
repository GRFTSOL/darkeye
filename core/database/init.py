import sqlite3
from config import DATABASE, PRIVATE_DATABASE, SQLPATH
import logging
from pathlib import Path


def init_private_db():
    """
    初始化私有数据库，然后添加一些数据
    """
    db_path=PRIVATE_DATABASE
    db_path.parent.mkdir(parents=True, exist_ok=True)#上层目录一定要存在
    need_init = not db_path.exists()  # 判断数据库是否需要初始化
    with sqlite3.connect(db_path) as conn:
        if need_init:
            logging.info(f"数据库 {db_path} 不存在，正在初始化...")
            with open(Path(SQLPATH/"initPrivateTable.sql"), "r", encoding="utf-8") as f:
                sql_script = f.read()
            conn.executescript(sql_script)  # 一次性执行建库SQL
            conn.commit()
            logging.info("数据库初始化完成")
        else:
            logging.info(f"数据库 {db_path} 已存在，直接使用")


def init_public_db(db_path:str):
    """
    初始化公有数据库，然后添加一些数据

    """
    pass


def init_database(public_db_path: Path, private_db_path: Path) -> bool:
    """
    确保公有库和私有库均启用 WAL 模式。
    """
    def _enable_wal(db_path: Path) -> bool:
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                result = cursor.fetchone()
                mode = result[0].lower() if result and result[0] else ""
                if mode != "wal":
                    logging.error("数据库 %s 启用 WAL 失败，当前模式: %s", db_path, mode or "unknown")
                    return False
                conn.commit()
            logging.info("数据库 %s 已启用 WAL 模式", db_path)
            return True
        except Exception:
            logging.exception("设置数据库 %s 为 WAL 模式时发生错误", db_path)
            return False

    public_ok = _enable_wal(public_db_path)
    private_ok = _enable_wal(private_db_path)
    return public_ok and private_ok
