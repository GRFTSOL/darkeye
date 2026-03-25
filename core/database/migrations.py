#这里是迁移数据库的，在软件启动的时候检测数据库与软件所需要的数据库版本是否一致，否则进行升级
import sqlite3
from sqlite3 import Connection
from .connection import get_connection
import logging
from pathlib import Path
import json
from config import SQLPATH

def get_db_version(conn:Connection):
    cur = conn.cursor()
    cur.execute("PRAGMA user_version")
    version = cur.fetchone()[0]

    if version != 0:#为了兼容性，版本号为0说明是上个版本的的库
        return str(version)

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
        logging.info("→ 执行 1.0 → 2升级...")
        sql_file = Path(SQLPATH / "public" / "v1.0-v2" / "migration.sql")
        with open(sql_file, "r", encoding="utf-8") as f:
            sql_script = f.read()
        conn.executescript(sql_script)  # 一次性执行建库SQL（使用传入的连接）
        conn.commit()
        logging.info("公共数据库迁移完成1.0 → 2升级")


    # 还可以继续往下扩展版本升级逻辑
    # elif current_version == "1.1.0":
    #     ...

def upgrade_private_db(conn, current_version):
    """执行数据库升级逻辑"""
    logging.info(f"私有数据库版本从 {current_version or '无版本'} 升级到 {REQUIRED_PRIVATE_DB_VERSION}")

    # 示例升级脚本
    if current_version == "1.0":
        logging.info("→ 执行 1.0 → 1.1 升级...")

        sql_file = Path(SQLPATH / "private" / "v1.0-v1.1" / "RBfavorite_actress.sql")
        with open(sql_file, "r", encoding="utf-8") as f:
            sql_script = f.read()
        conn.executescript(sql_script)  # 一次性执行建库SQL（使用传入的连接）


        sql_file = Path(SQLPATH / "private" / "v1.0-v1.1" / "RBfavorite_work.sql")
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
    current_version_str = str(current_version).strip() if current_version is not None else None
    required_public_version_str = str(REQUIRED_PUBLIC_DB_VERSION).strip()
    logging.info(f"当前公共数据库版本：{current_version_str}")

    if current_version_str != required_public_version_str:
        upgrade_public_db(conn, current_version_str)
    else:
        logging.info("公共数据库版本匹配，无需升级。")
    conn.close()

def check_and_upgrade_private_db():
    conn=get_connection(PRIVATE_DATABASE)

    current_version = get_db_version(conn)
    current_version_str = str(current_version).strip() if current_version is not None else None
    required_private_version_str = str(REQUIRED_PRIVATE_DB_VERSION).strip()
    logging.info(f"当前私有数据库版本：{current_version_str}" )

    if current_version_str != required_private_version_str:
        upgrade_private_db(conn, current_version_str)
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
            
            cursor.execute("PRAGMA foreign_keys = OFF;")
            # 先新建maker_old
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS maker_new(--制作商，一部片子只有一个制作商，一部制作商可以有多个作品。一部作品可以没有制作商
                    maker_id INTEGER PRIMARY KEY AUTOINCREMENT,--不重复主键
                    cn_name TEXT,										--中文名
                    jp_name TEXT,										--日文名
                    aliases TEXT,										--别名,中间用,分开,用于重定向用。
                    detail TEXT,                                       --其他信息
                    logo_url TEXT										--logo地址
                );
                """
            )
            # 清空关系表与 maker 表，准备按 JSON 重建
            cursor.execute("DELETE FROM prefix_maker_relation")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='prefix_maker_relation'")

            #先删除视图
            cursor.execute("DROP VIEW IF EXISTS v_work_all_info")

            #插入数据
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
                    INSERT INTO maker_new (cn_name, jp_name, aliases, detail, logo_url)
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

            # 把被 work 引用但在 maker_new 中匹配不到的旧 maker 追加到 maker_new 末尾
            cursor.execute(
                """
                INSERT INTO maker_new (cn_name, jp_name, aliases, detail, logo_url)
                SELECT
                    m_old.cn_name,
                    m_old.jp_name,
                    m_old.aliases,
                    m_old.detail,
                    m_old.logo_url
                FROM maker AS m_old
                WHERE EXISTS (
                    SELECT 1
                    FROM work
                    WHERE work.maker_id = m_old.maker_id
                )
                AND NOT EXISTS (
                    SELECT 1
                    FROM maker_new AS m
                    WHERE m.cn_name = m_old.cn_name
                        OR INSTR(
                            ',' || REPLACE(REPLACE(REPLACE(COALESCE(m.aliases, ''), '，', ','), ', ', ','), ' ,', ',') || ',',
                            ',' || m_old.cn_name || ','
                        ) > 0
                )
                """
            )

            # 用旧 maker 的数据去匹配 maker_new，重建 work.maker_id 指向
            cursor.execute(
                """
                UPDATE work
                SET maker_id = (
                    SELECT m.maker_id
                    FROM maker AS m_old
                    JOIN maker_new AS m
                        ON m.cn_name = m_old.cn_name
                        OR INSTR(
                            ',' || REPLACE(REPLACE(REPLACE(COALESCE(m.aliases, ''), '，', ','), ', ', ','), ' ,', ',') || ',',
                            ',' || m_old.cn_name || ','
                        ) > 0
                    WHERE m_old.maker_id = work.maker_id
                    LIMIT 1
                )
                WHERE maker_id IS NOT NULL
                """
            )
            cursor.execute("DROP TABLE maker")#把旧表删除了
            cursor.execute("ALTER TABLE maker_new RENAME TO maker")#把新表改名


            #重建视图,这个是要随着版本更新的。
            cursor.execute("""
            CREATE VIEW v_work_all_info AS--查询作品的基本数据的视图，这个非常的长
WITH actress_age_at_release AS (--计算每个女优发布作品的年龄
  SELECT
    w.work_id,
    a.actress_id,
    w.serial_number,
    w.release_date,
    a.birthday,
    -- 使用 julianday 计算日期差（以天为单位），然后除以 365.25 得到年龄
    (julianday(w.release_date) - julianday(a.birthday)) / 365.25 AS age_at_release
  FROM work w
  JOIN work_actress_relation war ON w.work_id = war.work_id
  JOIN actress a ON war.actress_id = a.actress_id
  WHERE w.release_date IS NOT NULL AND a.birthday IS NOT NULL
),
average_age_per_work AS (--辅助计算年龄的表
  SELECT
    work_id,
    serial_number,
    ROUND(AVG(age_at_release), 1)-0.45 AS avg_age_at_release--假设拍摄后5个多月发布
  FROM actress_age_at_release
  GROUP BY work_id
),
actress_list AS(--计算女优出演的名单
SELECT
	w.work_id,
    GROUP_CONCAT(
        (SELECT cn FROM actress_name WHERE actress_id = a.actress_id AND(name_type=1)),
        ','
    ) AS actress_list,
	GROUP_CONCAT(war.job,',') AS job,
	GROUP_CONCAT(war.state,',') AS state
FROM
    work w
LEFT JOIN 
    work_actress_relation war ON w.work_id = war.work_id
LEFT JOIN 
    actress a ON war.actress_id = a.actress_id
GROUP BY w.work_id
),
actor_list AS(--男优名单
SELECT
	w.work_id,
    GROUP_CONCAT(
        (SELECT cn FROM actor_name WHERE actor_id=war1.actor_id),
        ','
    ) AS actor_list
FROM
    work w
LEFT JOIN 
    work_actor_relation war1 ON w.work_id = war1.work_id
LEFT JOIN 
    actor a ON war1.actor_id = a.actor_id
GROUP BY w.work_id
),
studio_list AS(--片商表
SELECT 
	w.work_id,
	(SELECT cn_name FROM maker WHERE maker_id =p.maker_id) AS studio_name
FROM 
    work w
INNER JOIN 
    prefix_maker_relation p ON p.prefix = SUBSTR(w.serial_number, 1, INSTR(w.serial_number, '-') - 1)
WHERE 
    w.serial_number LIKE '%-%'
)
SELECT --水平计算表，然后统一合并
	w.work_id,
    w.serial_number AS serial_number,
    w.director AS director,
	w.release_date AS release_date,
	(SELECT actress_list FROM actress_list WHERE work_id=w.work_id)AS actress,
	(SELECT avg_age_at_release FROM average_age_per_work WHERE work_id=w.work_id)AS avg_age,
	(SELECT state FROM actress_list WHERE work_id=w.work_id)AS state,
	(SELECT actor_list FROM actor_list WHERE work_id=w.work_id)AS actor,
	w.notes AS notes,
	w.cn_title,
	w.cn_story,
	w.jp_title,
	w.jp_story,
	(SELECT studio_name FROM studio_list WHERE work_id=w.work_id)AS studio
FROM 
    work w;
            """)

            cursor.execute("PRAGMA foreign_keys = ON;")#把外键开起来




            conn.commit()
            logging.info("已从 %s 导入 maker & prefix 映射", path)
        except Exception:
            conn.rollback()
            raise