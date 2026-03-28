"""男优域查询"""

import logging

from config import DATABASE
from ..connection import get_connection


def get_actor_info(actor_id: int) -> dict:
    """查询一个男演员的所有数据"""
    query = """
    SELECT
        n.cn,
        n.jp,
        n.en,
        n.kana,
        a.image_url,
        a.birthday,
        a.handsome,
        a.fat,
        a.notes
    FROM actor a
    LEFT JOIN actor_name n
        ON n.actor_id = a.actor_id
    WHERE a.actor_id = ?
    """

    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (actor_id,))
        row = cursor.fetchone()
        logging.debug(f"查询到男优的信息：\n{row}")
        column_names = [description[0] for description in cursor.description]
    return dict(zip(column_names, row))


def get_null_actor() -> list:
    """返回所有的没有作品的actor_id列表"""
    query = """
    SELECT a.actor_id
    FROM actor AS a
    LEFT JOIN work_actor_relation AS r
        ON a.actor_id = r.actor_id
    WHERE r.actor_id IS NULL;
    """
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [row[0] for row in rows]


def exist_actor(name) -> int | None:
    """根据name查询actor是否在库内"""
    query = """
        SELECT
        actor_id
        FROM
        actor_name
        WHERE
        actor_name.jp=? OR actor_name.cn=? OR actor_name.en=?
        """
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (name, name, name))
        id = cursor.fetchone()
        if id is None:
            return None
        else:
            return id[0]


def get_actor_allname(actor_id) -> list[dict]:
    """反回某个男优的所有名字，最前面的是最新的，其他的无所谓"""
    query = """
    SELECT
        actor_name_id,
        cn,
        jp,
        en,
        kana
    FROM
        actor_name
    WHERE
        actor_id = ?
    ORDER BY name_type
    """
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (actor_id,))
        rows = cursor.fetchall()
        column_names = [description[0] for description in cursor.description]
        results = [dict(zip(column_names, row)) for row in rows]
        return results


def get_actorname() -> list:
    """返回所有的男优的名字，包括曾用名"""
    query = """
    SELECT
    cn,
    jp
    FROM
    actor_name
    """
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [row[0] for row in rows]
