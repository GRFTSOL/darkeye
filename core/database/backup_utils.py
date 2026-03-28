import os, logging
import sqlite3
from datetime import datetime
import shutil
from pathlib import Path
import json
from core.database.connection import get_connection

from config import (
    ACTORIMAGES_PATH,
    ACTRESSIMAGES_PATH,
    FANART_PATH,
    WORKCOVER_PATH,
    DATABASE,
    APP_VERSION,
)


def backup_database(database: Path, backup_dir: Path) -> str:
    # 这个也有未知情况下的问题
    # 将目标database文件复制到backup_dir备份的文件夹下并打上时间戳
    # 创建 backup 文件夹
    # backup_dir = os.path.join(os.path.dirname(db_path), "av_backup")
    os.makedirs(backup_dir, exist_ok=True)

    # 时间戳格式的文件名
    timestamp = datetime.now().strftime("backup-%Y-%m-%d-%H-%M-%S.db")
    backup_path = os.path.join(backup_dir, timestamp)

    src_conn = get_connection(database)
    backup_conn = get_connection(backup_path)
    try:
        src_conn.backup(backup_conn)
        logging.info(f"SQLite 原子备份成功: {backup_path}")
    finally:
        backup_conn.close()
        src_conn.close()
    """
    # 原子备份（安全）
    with sqlite3.connect(database) as src_conn:
        with sqlite3.connect(backup_path) as backup_conn:
            src_conn.backup(backup_conn)
            logging.info(f"已使用 sqlite3 原子备份方式成功备份到: {backup_path}")
    #这个有问题，就是bachup的文件会被程序占用，非常的奇怪
    """
    return backup_path


def restore_database(backup_path: Path, target_path: Path) -> bool:
    # 将备份的.db文件复制到目标.db目录下
    # 这个有风险需要后面更改
    if not backup_path.exists():
        return False
    try:
        shutil.copy(backup_path, target_path)
        logging.info("还原数据库成功")
        return True
    except Exception as e:
        logging.warning(f"[ERROR] Restore failed: {e}")
        return False


def restore_backup_safely(backup_db: Path, active_db: Path) -> bool:
    """
    安全恢复备份到正在被连接的 SQLite 数据库。
    不会直接覆盖文件，而是通过 SQL 将数据写入 active_db。

    :param active_db: 正在使用的数据库文件路径
    :param backup_db: 备份数据库文件路径
    """
    # 备份文件不存在时直接返回失败，避免生成空库并清空现有数据
    if not Path(backup_db).exists():
        logging.warning(f"[backup] 备份数据库不存在: {backup_db}")
        return False

    active_conn = sqlite3.connect(active_db)
    success = False
    try:
        # ATTACH 备份数据库
        active_conn.execute(f"ATTACH DATABASE '{backup_db}' AS backup_db;")
        active_conn.execute("PRAGMA foreign_keys=OFF;")  # 临时关闭外键约束

        # 获取备份数据库中所有表
        tables = active_conn.execute(
            "SELECT name FROM backup_db.sqlite_master WHERE type='table';"
        ).fetchall()
        # logging.debug(tables)
        with active_conn:
            for (table_name,) in tables:
                # 清空当前数据库中的表
                active_conn.execute(f"DELETE FROM {table_name};")
                # 从备份中插入数据
                active_conn.execute(
                    f"INSERT INTO {table_name} SELECT * FROM backup_db.{table_name};"
                )

        active_conn.execute("PRAGMA foreign_keys=ON;")  # 恢复外键约束
        active_conn.execute("DETACH DATABASE backup_db;")
        active_conn.execute("PRAGMA wal_checkpoint(FULL);")
        logging.info(f"已安全恢复备份 {backup_db} 到 {active_db}")
        success = True
    except Exception as e:
        logging.warning(f"[ERROR] Restore failed: {e}")
        success = False
    finally:
        active_conn.close()
    return success


def _copy_tree(src: Path, dst: Path, overwrite: bool = True) -> None:
    """递归拷贝目录 src 到 dst，支持覆盖控制。"""
    src = Path(src)
    dst = Path(dst)

    if not src.exists():
        logging.warning(f"[backup] 源目录不存在，跳过拷贝: {src}")
        return

    for root, dirs, files in os.walk(src):
        root_path = Path(root)
        rel = root_path.relative_to(src)
        target_root = dst / rel
        target_root.mkdir(parents=True, exist_ok=True)

        for name in files:
            src_file = root_path / name
            dst_file = target_root / name
            if dst_file.exists() and not overwrite:
                continue
            try:
                shutil.copy2(src_file, dst_file)
            except Exception as e:
                logging.warning(f"[backup] 拷贝文件失败 {src_file} -> {dst_file}: {e}")


def create_resource_snapshot(snapshot_root: Path) -> Path | None:
    """
    创建一次资源快照：
    - 在 snapshot_root 下创建带时间戳的子目录
    - 备份当前 DATABASE 到该目录
    - 复制三类资源目录到该目录
    - 写入 meta.json
    """
    try:
        snapshot_root = Path(snapshot_root)
        snapshot_root.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("snapshot-%Y-%m-%d-%H-%M-%S")
        snapshot_dir = snapshot_root / ts
        snapshot_dir.mkdir(parents=True, exist_ok=False)

        # 数据库备份复用现有逻辑
        backup_db_path_str = backup_database(DATABASE, snapshot_dir)
        backup_db_path = Path(backup_db_path_str)
        db_rel_name = backup_db_path.name

        # 复制三类资源目录
        actor_dir = snapshot_dir / "actorimages"
        actress_dir = snapshot_dir / "actressimages"
        workcovers_dir = snapshot_dir / "workcovers"
        fanart_dir = snapshot_dir / "fanart"

        _copy_tree(ACTORIMAGES_PATH, actor_dir, overwrite=True)
        _copy_tree(ACTRESSIMAGES_PATH, actress_dir, overwrite=True)
        _copy_tree(WORKCOVER_PATH, workcovers_dir, overwrite=True)
        _copy_tree(FANART_PATH, fanart_dir, overwrite=True)

        def _dir_info(d: Path, name: str) -> dict:
            d = Path(d)
            total_size = 0
            file_count = 0
            if d.exists():
                for root, _, files in os.walk(d):
                    for fname in files:
                        fp = Path(root) / fname
                        try:
                            total_size += fp.stat().st_size
                            file_count += 1
                        except OSError:
                            continue
            return {
                "name": name,
                "path": name,  # 相对 snapshot_dir 的路径
                "file_count": file_count,
                "total_size": total_size,
            }

        meta = {
            "version": 1,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "app_version": APP_VERSION,
            "db": {
                "file": db_rel_name,
                "type": "sqlite",
                "size": backup_db_path.stat().st_size if backup_db_path.exists() else 0,
            },
            "resources": [
                _dir_info(actor_dir, "actorimages"),
                _dir_info(actress_dir, "actressimages"),
                _dir_info(workcovers_dir, "workcovers"),
                _dir_info(fanart_dir, "fanart"),
            ],
        }

        meta_path = snapshot_dir / "meta.json"
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        logging.info(f"[backup] 创建资源快照成功: {snapshot_dir}")
        return snapshot_dir
    except Exception as e:
        logging.warning(f"[backup] 创建资源快照失败: {e}")
        return None


def restore_snapshot(
    meta_path: Path,
    restore_db: bool = True,
    restore_actor: bool = True,
    restore_actress: bool = True,
    restore_workcovers: bool = True,
    restore_fanart: bool = True,
) -> bool:
    """
    从指定快照恢复：
    - 参数必须传入 meta.json 文件路径。
    - 可选择恢复数据库和三类资源目录。
    """
    meta_path = Path(meta_path)
    if not meta_path.is_file():
        logging.warning(f"[backup] 指定的 meta.json 不存在: {meta_path}")
        return False

    snapshot_dir = meta_path.parent

    try:
        with meta_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as e:
        logging.warning(f"[backup] 读取快照 meta.json 失败 {meta_path}: {e}")
        return False

    if meta.get("version") != 1:
        logging.warning(f"[backup] 不支持的快照版本: {meta.get('version')}")
        return False

    ok = True

    # 恢复数据库
    if restore_db:
        db_info = meta.get("db", {})
        db_file_name = db_info.get("file")
        if db_file_name:
            backup_db_path = snapshot_dir / db_file_name
            if backup_db_path.exists():
                if not restore_backup_safely(backup_db_path, DATABASE):
                    ok = False
            else:
                logging.warning(f"[backup] 快照中的数据库文件不存在: {backup_db_path}")
                ok = False
        else:
            logging.warning("[backup] 快照 meta 中缺少 db.file 信息")
            ok = False

    # 恢复资源目录
    if restore_actor:
        _copy_tree(snapshot_dir / "actorimages", ACTORIMAGES_PATH, overwrite=True)

    if restore_actress:
        _copy_tree(snapshot_dir / "actressimages", ACTRESSIMAGES_PATH, overwrite=True)

    if restore_workcovers:
        _copy_tree(snapshot_dir / "workcovers", WORKCOVER_PATH, overwrite=True)

    if restore_fanart:
        fanart_snap = snapshot_dir / "fanart"
        if fanart_snap.exists():
            _copy_tree(fanart_snap, FANART_PATH, overwrite=True)

    logging.info(f"[backup] 从快照恢复完成: {snapshot_dir}, result={ok}")
    return ok
