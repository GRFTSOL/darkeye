'''作品域查询'''
import sqlite3
import logging
from datetime import datetime

from config import DATABASE
from ..connection import get_connection


def get_all_work_id() -> list[int]:
    '''获得所有的work_id'''
    query = '''
    SELECT
    work_id
    FROM
    work
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [row[0] for row in rows]


def get_work_ids_with_cover(limit: int = 30) -> list[int]:
    '''获得有封面的work_id列表，按更新时间逆序取前limit条'''
    query = '''
    SELECT
        work_id
    FROM
        work
    WHERE
        image_url IS NOT NULL AND image_url != ''
    ORDER BY
        update_time DESC
    LIMIT ?
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        return [row[0] for row in rows]


def get_all_work_addtime() -> list[datetime]:
    '''获得所有的work添加的时间,返回时间的list'''
    query = '''
    SELECT
    create_time
    FROM
    work
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S") for row in rows]


def query_studio(work_id: int) -> str | None:
    '''根据work_id返回发行商，如果为非标准发行商，就是私拍，或者没有封面的，就返回None'''
    query = '''
    SELECT
        (SELECT cn_name FROM maker WHERE maker_id =p.maker_id) AS studio_name
    FROM
        work w
    INNER JOIN
        prefix_maker_relation p ON p.prefix = SUBSTR(w.serial_number, 1, INSTR(w.serial_number, '-') - 1)
    WHERE
    work_id=?
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (work_id,))
        row = cursor.fetchone()
    if row is not None:
        return row[0]
    else:
        return None


def get_workinfo_by_workid(work_id: int) -> dict:
    '''根据work_id获得单部作品的基本数据'''
    query = '''
    SELECT
    serial_number,
    director,
    notes,
    runtime,
    release_date,
    image_url,
    cn_title,
    cn_story,
    jp_title,
    jp_story,
    work.maker_id AS maker_id,
    work.label_id AS label_id,
    work.series_id AS series_id,
    (SELECT cn_name FROM maker WHERE maker_id =p.maker_id) AS studio_name
    FROM work
    LEFT JOIN
        prefix_maker_relation p ON p.prefix = SUBSTR(work.serial_number, 1, INSTR(work.serial_number, '-') - 1)
    WHERE work_id = ?
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (work_id,))
        rows = cursor.fetchall()
        column_names = [description[0] for description in cursor.description]
    return [dict(zip(column_names, row)) for row in rows][0]


def get_workcardinfo_by_workid(work_id: int) -> dict:
    '''根据work_id获得单部作品的卡片数据'''
    query = '''
SELECT
    work.serial_number,
    cn_title,
    image_url,
    wtr.tag_id,
    work.work_id,
    CASE
        WHEN (SELECT cn_name FROM maker WHERE maker_id =p.maker_id) IS NULL
        THEN 0
        ELSE 1
    END AS standard
FROM work
LEFT JOIN work_tag_relation wtr ON work.work_id = wtr.work_id AND wtr.tag_id IN (1, 2, 3)
LEFT JOIN
    prefix_maker_relation p ON p.prefix = SUBSTR(work.serial_number, 1, INSTR(work.serial_number, '-') - 1)
WHERE work.work_id= ?
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (work_id,))
        rows = cursor.fetchall()
        column_names = [description[0] for description in cursor.description]
    return [dict(zip(column_names, row)) for row in rows][0]


def get_actressid_by_workid(work_id: int) -> list:
    '''根据work_id获得对应女优的id列表'''
    query = "SELECT actress_id FROM work_actress_relation WHERE work_id = ?"
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (work_id,))
        return [row[0] for row in cursor.fetchall()]


def get_works_for_dvd(work_ids: list[int]) -> list[dict]:
    '''批量查询 work_id、serial_number、image_url，供 DVD 场景使用，保持输入顺序'''
    if not work_ids:
        return []
    placeholders = ",".join("?" for _ in work_ids)
    query = f'''
    SELECT
        work_id,
        serial_number,
        image_url
    FROM work
    WHERE work_id IN ({placeholders})
    '''
    try:
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query, work_ids)
            rows = cursor.fetchall()
            by_id = {r[0]: {"work_id": r[0], "serial_number": r[1], "image_url": r[2]} for r in rows}
            return [by_id[w] for w in work_ids if w in by_id]
    except sqlite3.Error as e:
        logging.info(f"get_works_for_dvd 查询时数据库错误: {e}")
        return []


def get_cover_image_url(work_id: int) -> str | None:
    '''根据work_id查找对应的封面图片的地址'''
    query = '''
    SELECT
        image_url
    FROM work
    WHERE work_id = ?
    LIMIT 1
    '''
    try:
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (work_id,))
            image_rul = cursor.fetchone()
            if image_rul:
                return image_rul[0]
            else:
                return None
    except sqlite3.Error as e:
        logging.info(f"get_coverimageurl查询时数据库错误: {e}")
        return None


def get_cover_image_url_by_serial(serial_number: str) -> str | None:
    '''根据serial_number查找对应的封面图片的地址'''
    query = '''
    SELECT
        image_url
    FROM work
    WHERE serial_number = ?
    LIMIT 1
    '''
    try:
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (serial_number,))
            image_rul = cursor.fetchone()
            if image_rul:
                return image_rul[0]
            else:
                return None
    except sqlite3.Error as e:
        logging.info(f"get_coverimageurl查询时数据库错误: {e}")
        return None


def get_actorid_by_workid(work_id: int) -> list:
    '''根据work_id获得对应男优的id列表'''
    query = "SELECT actor_id FROM work_actor_relation WHERE work_id = ?"
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (work_id,))
        return [row[0] for row in cursor.fetchall()]


def get_worktaginfo_by_workid(work_id: int) -> list[dict]:
    '''根据work_id获得单部作品的标签数据'''
    query = '''
    SELECT
        t.tag_id,
        t.tag_name,
        tt.tag_type_name,
        t.color,
        t.detail,
        tt.tag_order
    FROM work_tag_relation wtr
    JOIN tag t ON t.tag_id=wtr.tag_id
    JOIN tag_type tt ON tt.tag_type_id=t.tag_type_id
    WHERE wtr.work_id = ?
    ORDER BY tt.tag_order,color
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (work_id,))
        rows = cursor.fetchall()
        column_names = [description[0] for description in cursor.description]
        return [dict(zip(column_names, row)) for row in rows]


def get_work_tags(work_id: int) -> list:
    """获取作品已有的标签ID列表"""
    query = "SELECT tag_id FROM work_tag_relation WHERE work_id = ?"
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (work_id,))
        return [row[0] for row in cursor.fetchall()]


def get_actress_from_work_id(work_id: int) -> list[dict]:
    '''
    根据输入的work_id在数据库中找到对应的女优的id和女优名字

    Args:
        work_id:作品id

    Returns:
        返回字典列表，形式为[{actress_id:xxx,actress_name:xxx},{actress_id:xxx,actress_name:xxx}]
    '''
    query = """
    SELECT
        a.actress_id,
    (SELECT cn FROM actress_name WHERE actress_id = a.actress_id AND(name_type=1))AS actress_name

    FROM
        work w
    JOIN
        work_actress_relation war ON w.work_id = war.work_id
    JOIN
        actress a ON war.actress_id = a.actress_id
    WHERE w.work_id=?
    """
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (work_id,))
        rows = cursor.fetchall()
        column_names = [description[0] for description in cursor.description]

    if not rows:
        return None
    result = [dict(zip(column_names, row)) for row in rows]
    return result


def get_actor_from_work_id(work_id: int) -> list[dict]:
    '''
    根据输入的work_id在数据库中找到对应的男优的id和男优名字

    Args:
        work_id:作品id

    Returns:
        返回字典列表，形式为[{actor_id:xxx,actor_name:xxx},{actor_id:xxx,actor_name:xxx}]返回的男优的名字只有一个
    '''
    query = """
    SELECT
        a.actor_id,
        (SELECT cn FROM actor_name WHERE actor_id=a.actor_id)AS actor_name
    FROM
        work w
    JOIN
        work_actor_relation war ON w.work_id = war.work_id
    JOIN
        actor a ON war.actor_id = a.actor_id
    WHERE w.work_id=?
    """
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (work_id,))
        rows = cursor.fetchall()
        column_names = [description[0] for description in cursor.description]
    if not rows:
        return None
    result = [dict(zip(column_names, row)) for row in rows]
    return result


def get_work_notes_rows() -> list[tuple]:
    query = """
    SELECT work_id, serial_number, notes
    FROM work
    WHERE notes IS NOT NULL AND notes != ''
    """
    try:
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()
    except Exception as e:
        logging.error(f"get_work_story_rows查询时数据库错误: {e}")
        return []


def get_recent_work_notes_rows(limit: int) -> list[tuple]:
    query = """
    SELECT work_id, serial_number, notes
    FROM work
    ORDER BY update_time DESC
    LIMIT ?
    """
    try:
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (limit,))
            return cursor.fetchall()
    except Exception as e:
        logging.error(f"get_recent_work_story_rows查询时数据库错误: {e}")
        return []


def get_serial_number_map() -> dict:
    query = "SELECT serial_number, work_id FROM work"
    try:
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
        return {row[0]: row[1] for row in rows}
    except Exception as e:
        logging.error(f"get_serial_number_map查询时数据库错误: {e}")
        return {}


def get_works_for_bulk_crawl_fields() -> list[dict]:
    """批量爬虫筛选所需字段快照（含关联计数）。"""
    query = """
    SELECT
        w.work_id,
        w.serial_number,
        w.release_date,
        w.director,
        w.runtime,
        w.cn_title,
        w.jp_title,
        w.cn_story,
        w.jp_story,
        w.image_url,
        w.maker_id,
        w.label_id,
        w.series_id,
        (SELECT COUNT(1) FROM work_actress_relation war WHERE war.work_id = w.work_id) AS actress_count,
        (SELECT COUNT(1) FROM work_actor_relation wor WHERE wor.work_id = w.work_id) AS actor_count,
        (SELECT COUNT(1) FROM work_tag_relation wtr WHERE wtr.work_id = w.work_id) AS tag_count
    FROM work w
    WHERE w.is_deleted = 0
    """
    try:
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            column_names = [description[0] for description in cursor.description]
            return [dict(zip(column_names, row)) for row in rows]
    except sqlite3.Error as e:
        logging.error(f"get_works_for_bulk_crawl_fields 查询时数据库错误: {e}")
        return []


def get_workid_by_serialnumber(serial_number) -> int | None:
    '''通过番号返回work_id'''
    query = '''
        SELECT work_id
        FROM work
        WHERE serial_number=?
        '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (serial_number,))
        id = cursor.fetchone()
        if id is None:
            return None
        else:
            return id[0]


def get_javtxt_id_by_serialnumber(serial_number) -> int | None:
    '''通过番号获取javtxt的缓存'''
    query = '''
        SELECT javtxt_id
        FROM work
        WHERE serial_number=?
        '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (serial_number,))
        id = cursor.fetchone()
        if id is None:
            return None
        else:
            return id[0]


def get_serial_number() -> list:
    '''返回所有的番号'''
    query = '''
    SELECT
    serial_number
    FROM
    work
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [row[0] for row in rows]


def get_unique_director() -> list:
    '''读取独一无二的导演信息'''
    query = '''
    SELECT
        director ,
        count (*)AS num
    FROM work
    GROUP BY director
    ORDER BY num DESC
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
    return [row[0] for row in rows]


def get_unique_short_story() -> list:
    '''获得库中所有的简短的剧情'''
    query = '''
    SELECT
    notes,
    COUNT(*) AS num
    FROM work
    GROUP BY notes
    ORDER BY num DESC
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [row[0] for row in rows]


def get_maker_name() -> list[dict]:
    """获取所有片商信息（含 maker_id/cn_name/jp_name/aliases）"""
    query = """
    SELECT maker_id, cn_name, jp_name, aliases
    FROM maker
    """
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [
            {
                "maker_id": row[0],
                "cn_name": row[1],
                "jp_name": row[2],
                "aliases": row[3],
            }
            for row in rows
        ]


def get_label_name() -> list[dict]:
    """获取所有厂牌信息（含 label_id/cn_name/jp_name/aliases）"""
    query = """
    SELECT label_id, cn_name, jp_name, aliases
    FROM label
    """
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [
            {
                "label_id": row[0],
                "cn_name": row[1],
                "jp_name": row[2],
                "aliases": row[3],
            }
            for row in rows
        ]


def get_series_name() -> list[dict]:
    """获取所有系列信息（含 series_id/cn_name/jp_name/aliases）"""
    query = """
    SELECT series_id, cn_name, jp_name, aliases
    FROM series
    """
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [
            {
                "series_id": row[0],
                "cn_name": row[1],
                "jp_name": row[2],
                "aliases": row[3],
            }
            for row in rows
        ]

def get_maker_id_by_name(name: str) -> int | None:
    '''通过片商名字返回片商id,要求name为片商的cn_name或jp_name或aliases中的一个，绝对匹配,不区分大小写，
    但是aliases是逗号分割的，所以需要分割后进行匹配'''
    target = (name or "").strip().lower()
    if not target:
        return None

    query = """
    SELECT maker_id, cn_name, jp_name, aliases
    FROM maker
    """
    try:
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            for maker_id, cn_name, jp_name, aliases in rows:
                if str(cn_name or "").strip().lower() == target:
                    return maker_id
                if str(jp_name or "").strip().lower() == target:
                    return maker_id
                alias_parts = [a.strip().lower() for a in str(aliases or "").split(",") if a and a.strip()]
                if target in alias_parts:
                    return maker_id
    except sqlite3.Error as e:
        logging.info(f"get_maker_id_by_name 查询时数据库错误: {e}")
    return None


def get_label_id_by_name(name: str) -> int | None:
    """通过厂牌名字返回厂牌 id，支持 cn/jp/aliases 绝对匹配（忽略大小写）"""
    target = (name or "").strip().lower()
    if not target:
        return None

    query = """
    SELECT label_id, cn_name, jp_name, aliases
    FROM label
    """
    try:
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            for label_id, cn_name, jp_name, aliases in rows:
                if str(cn_name or "").strip().lower() == target:
                    return label_id
                if str(jp_name or "").strip().lower() == target:
                    return label_id
                alias_parts = [a.strip().lower() for a in str(aliases or "").split(",") if a and a.strip()]
                if target in alias_parts:
                    return label_id
    except sqlite3.Error as e:
        logging.info(f"get_label_id_by_name 查询时数据库错误: {e}")
    return None


def get_series_id_by_name(name: str) -> int | None:
    """通过系列名字返回系列 id，支持 cn/jp/aliases 绝对匹配（忽略大小写）"""
    target = (name or "").strip().lower()
    if not target:
        return None

    query = """
    SELECT series_id, cn_name, jp_name, aliases
    FROM series
    """
    try:
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            for series_id, cn_name, jp_name, aliases in rows:
                if str(cn_name or "").strip().lower() == target:
                    return series_id
                if str(jp_name or "").strip().lower() == target:
                    return series_id
                alias_parts = [a.strip().lower() for a in str(aliases or "").split(",") if a and a.strip()]
                if target in alias_parts:
                    return series_id
    except sqlite3.Error as e:
        logging.info(f"get_series_id_by_name 查询时数据库错误: {e}")
    return None






# Deprecated aliases (use new names above)
findActressFromWorkID = get_actress_from_work_id
findActorFromWorkID = get_actor_from_work_id
get_coveriamgeurl = get_cover_image_url
get_coverimageurl_ = get_cover_image_url_by_serial
getUniqueDirector = get_unique_director
