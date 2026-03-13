#这里是迁移数据库的，在软件启动的时候检测数据库与软件所需要的数据库版本是否一致，否则进行升级
import sqlite3
from sqlite3 import Connection
from .connection import get_connection
import logging
from pathlib import Path
import json

def get_db_version(conn:Connection):
    cur = conn.execute("SELECT version FROM db_version ORDER BY applied_at DESC LIMIT 1;")
    row = cur.fetchone()
    return row[0] if row else None

def set_db_version(conn:Connection, version:str, description:str=""):
    conn.execute(
        "INSERT INTO db_version (version, description) VALUES (?, ?)",
        (version, description)
    )
    conn.commit()


from config import REQUIRED_PRIVATE_DB_VERSION,REQUIRED_PUBLIC_DB_VERSION,DATABASE,PRIVATE_DATABASE

def upgrade_public_db(conn, current_version):
    """执行数据库升级逻辑"""
    logging.info(f"公共数据库版本从 {current_version or '无版本'} 升级到 {REQUIRED_PUBLIC_DB_VERSION}")
    #当版本库不一致时就一直不断的升级 
    # 示例升级脚本
    if current_version == "1.0":
        logging.info("→ 执行 1.0 → 1.1.升级...")
        # 举例：新增字段
        # 执行标准
        set_db_version(conn, "1.1", "")
    
    # 还可以继续往下扩展版本升级逻辑
    # elif current_version == "1.1.0":
    #     ...

def upgrade_private_db(conn, current_version):
    """执行数据库升级逻辑"""
    logging.info(f"私有数据库版本从 {current_version or '无版本'} 升级到 {REQUIRED_PRIVATE_DB_VERSION}")
    from config import SQLPATH
    # 示例升级脚本
    if current_version == "1.0":
        logging.info("→ 执行 1.0 → 1.1 升级...")

        sql_file = Path(SQLPATH / "v1.1" / "RBfavorite_actress.sql")
        with open(sql_file, "r", encoding="utf-8") as f:
            sql_script = f.read()
        conn.executescript(sql_script)  # 一次性执行建库SQL（使用传入的连接）


        sql_file = Path(SQLPATH / "v1.1" / "RBfavorite_work.sql")
        with open(sql_file, "r", encoding="utf-8") as f:
            sql_script = f.read()
        conn.executescript(sql_script)  # 一次性执行建库SQL（使用传入的连接）
        conn.commit()

        logging.info("数据库迁移完成")

        # 执行标准：在同一个连接上记录版本
        set_db_version(conn, "1.1", "重建表使得表不需要unique")
    
    # 还可以继续往下扩展版本升级逻辑
    # elif current_version == "1.1.0":
    #     ...

def check_and_upgrade_public_db():
    conn=get_connection(DATABASE)

    current_version = get_db_version(conn)
    logging.info(f"当前公共数据库版本：{current_version}")

    if current_version != REQUIRED_PUBLIC_DB_VERSION:
        upgrade_public_db(conn, current_version)
    else:
        logging.info("公共数据库版本匹配，无需升级。")
    conn.close()

def check_and_upgrade_private_db():
    conn=get_connection(PRIVATE_DATABASE)

    current_version = get_db_version(conn)
    logging.info(f"当前私有数据库版本：{current_version}" )

    if current_version != REQUIRED_PRIVATE_DB_VERSION:
        upgrade_private_db(conn, current_version)
    else:
        logging.info("私有数据库版本匹配，无需升级。")
    conn.close()



def rebuild_privatelink():
    '''重建私有库与公有库的链接
    当公共库换了的时候，需要重建私有库的work_id
    包括三个表的更新，favourite_actress，favourite_work，masturbation,
    这三个表中更新其对应的work_id和actress_id,然后如果公共库中没有，就新建,返回需要添加的work_id列表和actress_id列表
    '''
    from core.database.db_utils import attach_private_db, detach_private_db

    added_work_ids: list[int] = []
    added_actress_ids: list[int] = []

    with get_connection(DATABASE, False) as conn:
        cursor = conn.cursor()
        attach_private_db(cursor)

        try:
            logging.info("开始重建私库链接：favorite_actress / favorite_work / masturbation")

            # 1. 更新 favorite_actress表中的actress_id：按 jp_name 在公库查找或新建，更新 priv.favorite_actress.actress_id
            cursor.execute("""
                SELECT favorite_actress_id, actress_id, jp_name
                FROM priv.favorite_actress
            """)
            actress_rows = cursor.fetchall()
            logging.info("需要检查 favorite_actress 行数: %d", len(actress_rows))

            for (fa_id, old_actress_id, jp_name) in actress_rows:
                if not jp_name:
                    logging.debug("favorite_actress_id=%s jp_name 为空，跳过", fa_id)
                    continue
                cursor.execute("""
                    SELECT actress_id FROM actress_name
                    WHERE jp = ?
                    LIMIT 1
                """, (jp_name,))
                row = cursor.fetchone()
                if row:
                    new_actress_id = row[0]
                    #logging.debug(
                    #    "favorite_actress_id=%s 根据 jp_name='%s' 找到已存在 actress_id=%s",
                    #    fa_id, jp_name, new_actress_id
                    #)
                else:
                    cursor.execute("INSERT INTO actress DEFAULT VALUES")
                    new_actress_id = cursor.lastrowid
                    cursor.execute(
                        "INSERT INTO actress_name (actress_id, name_type, cn, jp) VALUES (?, 1, ?, ?)",
                        (new_actress_id, jp_name or "", jp_name),
                    )
                    added_actress_ids.append(new_actress_id)
                    logging.info(
                        "favorite_actress_id=%s jp_name='%s' 在公库不存在，新建 actress_id=%s",
                        fa_id, jp_name, new_actress_id
                    )
                if new_actress_id != old_actress_id:
                    cursor.execute(
                        "UPDATE priv.favorite_actress SET actress_id = ? WHERE favorite_actress_id = ?",
                        (new_actress_id, fa_id),
                    )
                    logging.debug(
                        "更新 priv.favorite_actress favorite_actress_id=%s: %s -> %s",
                        fa_id, old_actress_id, new_actress_id
                    )

            # 2. 重建 favorite_work：按 serial_number 在公库中查找或新建 work，更新 priv.favorite_work.work_id
            cursor.execute("""
                SELECT favorite_work_id, work_id, serial_number
                FROM priv.favorite_work
            """)
            work_rows = cursor.fetchall()
            logging.info("需要检查 favorite_work 行数: %d", len(work_rows))

            for (fw_id, old_work_id, serial_number) in work_rows:
                if not serial_number:
                    logging.debug("favorite_work_id=%s serial_number 为空，跳过", fw_id)
                    continue
                cursor.execute("SELECT work_id FROM work WHERE serial_number = ?", (serial_number,))
                row = cursor.fetchone()
                if row:
                    new_work_id = row[0]
                    #logging.debug(
                    #    "favorite_work_id=%s 根据 serial_number='%s' 找到已存在 work_id=%s",
                    #    fw_id, serial_number, new_work_id
                    #)
                else:
                    cursor.execute("INSERT INTO work (serial_number) VALUES (?)", (serial_number,))
                    new_work_id = cursor.lastrowid
                    added_work_ids.append(new_work_id)
                    logging.info(
                        "favorite_work_id=%s serial_number='%s' 在公库不存在，新建 work_id=%s",
                        fw_id, serial_number, new_work_id
                    )
                if new_work_id != old_work_id:
                    cursor.execute(
                        "UPDATE priv.favorite_work SET work_id = ? WHERE favorite_work_id = ?",
                        (new_work_id, fw_id),
                    )
                    logging.debug(
                        "更新 priv.favorite_work favorite_work_id=%s: %s -> %s",
                        fw_id, old_work_id, new_work_id
                    )

            # 3. 重建 masturbation：按 serial_number 解析公库 work_id，不存在则新建 work，更新 priv.masturbation.work_id
            cursor.execute("""
                SELECT masturbation_id, work_id, serial_number
                FROM priv.masturbation
            """)
            mas_rows = cursor.fetchall()
            logging.info("需要检查 masturbation 行数: %d", len(mas_rows))

            for (m_id, old_work_id, serial_number) in mas_rows:
                if not serial_number:
                    #logging.debug("masturbation_id=%s serial_number 为空，跳过", m_id)
                    continue
                cursor.execute("SELECT work_id FROM work WHERE serial_number = ?", (serial_number,))
                row = cursor.fetchone()
                if row:
                    new_work_id = row[0]
                    #logging.debug(
                    #    "masturbation_id=%s 根据 serial_number='%s' 找到已存在 work_id=%s",
                    #    m_id, serial_number, new_work_id
                    #)
                else:
                    cursor.execute("INSERT INTO work (serial_number) VALUES (?)", (serial_number,))
                    new_work_id = cursor.lastrowid
                    added_work_ids.append(new_work_id)
                    logging.info(
                        "masturbation_id=%s serial_number='%s' 在公库不存在，新建 work_id=%s",
                        m_id, serial_number, new_work_id
                    )
                if new_work_id != old_work_id:
                    cursor.execute(
                        "UPDATE priv.masturbation SET work_id = ? WHERE masturbation_id = ?",
                        (new_work_id, m_id),
                    )
                    logging.debug(
                        "更新 priv.masturbation masturbation_id=%s: %s -> %s",
                        m_id, old_work_id, new_work_id
                    )

            conn.commit()
            logging.info(
                "重建私库链接完成：新增 work_id 数量=%d，新增 actress_id 数量=%d",
                len(added_work_ids), len(added_actress_ids)
            )
        except Exception as e:
            conn.rollback()
            logging.warning("rebuild_privatelink 失败: %s", e)
            raise
        finally:
            detach_private_db(cursor)

    return added_work_ids, added_actress_ids


def export_maker_prefix_json(json_path: str | Path) -> Path:
    """
    导出片商与前缀的公共知识为 JSON。
    JSON 结构示例（列表，每个元素是一个片商及其前缀列表）：
    [
      {
        "cn_name": "...",
        "jp_name": "...",
        "aliases": "...",
        "detail": "...",
        "logo_url": "...",
        "prefixes": ["ABP", "IPX"]
      },
      ...
    ]
    """
    path = Path(json_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection(DATABASE, readonly=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                m.maker_id,
                m.cn_name,
                m.jp_name,
                m.aliases,
                m.detail,
                m.logo_url,
                pmr.prefix
            FROM maker AS m
            LEFT JOIN prefix_maker_relation AS pmr
                ON m.maker_id = pmr.maker_id
            ORDER BY m.maker_id, pmr.prefix
            """
        )
        rows = cursor.fetchall()

    makers: dict[int, dict] = {}
    for (
        maker_id,
        cn_name,
        jp_name,
        aliases,
        detail,
        logo_url,
        prefix,
    ) in rows:
        maker = makers.get(maker_id)
        if maker is None:
            maker = {
                "cn_name": cn_name,
                "jp_name": jp_name,
                "aliases": aliases,
                "detail": detail,
                "logo_url": logo_url,
                "prefixes": [],
            }
            makers[maker_id] = maker
        if prefix and prefix not in maker["prefixes"]:
            maker["prefixes"].append(prefix)

    data = list(makers.values())
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logging.info("已导出 maker & prefix 映射到 %s", path)
    return path


def import_maker_prefix_json(json_path: str | Path) -> None:
    """
    从 JSON 文件导入片商与前缀数据，覆盖当前的 maker / prefix_maker_relation。
    期望的 JSON 结构与 export_maker_prefix_json 导出的格式一致（不包含 maker_id，由数据库自增生成）。
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"找不到 JSON 文件: {path}")

    raw = path.read_text(encoding="utf-8")
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"解析 JSON 失败: {e}") from e

    if not isinstance(items, list):
        raise ValueError("JSON 顶层结构必须是列表")

    with get_connection(DATABASE, readonly=False) as conn:
        cursor = conn.cursor()
        try:
            # 先清空关系表和片商表
            cursor.execute("DELETE FROM prefix_maker_relation")
            cursor.execute("DELETE FROM maker")

            for item in items:
                if not isinstance(item, dict):
                    continue

                cn_name = item.get("cn_name")
                jp_name = item.get("jp_name")
                aliases = item.get("aliases")
                detail = item.get("detail")
                logo_url = item.get("logo_url")
                prefixes = item.get("prefixes") or []

                # 始终由 SQLite 自增 maker_id，忽略 JSON 中可能存在的 maker_id
                cursor.execute(
                    """
                    INSERT INTO maker (cn_name, jp_name, aliases, detail, logo_url)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (cn_name, jp_name, aliases, detail, logo_url),
                )
                maker_id = cursor.lastrowid

                for prefix in prefixes:
                    if not prefix:
                        continue
                    cursor.execute(
                        """
                        INSERT INTO prefix_maker_relation (prefix, maker_id)
                        VALUES (?, ?)
                        """,
                        (prefix, maker_id),
                    )

            conn.commit()
            logging.info("已从 %s 导入 maker & prefix 映射", path)
        except Exception:
            conn.rollback()
            raise