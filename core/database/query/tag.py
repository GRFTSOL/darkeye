'''标签域查询'''
import logging

from config import DATABASE
from ..connection import get_connection


def get_tag_type() -> list[dict]:
    '''获得所有的tag_type'''
    query = '''
    SELECT
        tag_type_id,
        tag_type_name,
        tag_order
    FROM
        tag_type
    ORDER BY tag_order
            '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        column_names = [description[0] for description in cursor.description]
        results = [dict(zip(column_names, row)) for row in rows]
    return results


def get_alias_tag(tag_id: int) -> list[dict]:
    '''获得那些被重定向后的tag'''
    query = '''
    SELECT
        tag_id,
        tag_name,
        redirect_tag_id
    FROM tag
    WHERE redirect_tag_id=?
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (tag_id,))
        rows = cursor.fetchall()
        column_names = [description[0] for description in cursor.description]
        results = [dict(zip(column_names, row)) for row in rows]
    return results


def get_tags() -> list[tuple]:
    '''读取所有的tag库里的信息
    供加载tag_selector使用
    '''
    query = '''
    SELECT
        tag_id,
        tag_name,
        tag_type.tag_type_name AS tag_name,
        color,
        detail,
        group_id
    FROM tag
    JOIN tag_type ON tag_type.tag_type_id=tag.tag_type_id
    WHERE redirect_tag_id is NULL
    ORDER BY tag_type.tag_order,color
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
    return results


def get_taginfo_by_id(tag_id: int) -> dict:
    '''通过tag_id查询tag的所有的信息'''
    query = '''
SELECT
    tag_id,
    tag_name,
    tag_type_id,
    color,
    detail,
    redirect_tag_id
FROM tag
WHERE tag_id=?
'''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (tag_id,))
        row = cursor.fetchone()
        column_names = [description[0] for description in cursor.description]

    return dict(zip(column_names, row))


def get_tagid_by_keyword(keyword: str, match_hole_word=False) -> list | int | None:
    '''这个递归搜索到所有的没有重定向的tag'''
    query = """
    WITH RECURSIVE tag_chain AS (
    -- 初始搜索
    SELECT tag_id
    FROM tag
    WHERE tag_name LIKE ?

    UNION ALL

    -- 递归跟随 redirect_tag_id
    SELECT t.redirect_tag_id
    FROM tag t
    JOIN tag_chain tc ON t.tag_id = tc.tag_id
    WHERE t.redirect_tag_id IS NOT NULL
    )
    -- 最终只保留没有重定向的 tag_id
    SELECT DISTINCT tc.tag_id
    FROM tag_chain tc
    LEFT JOIN tag t2 ON tc.tag_id = t2.tag_id AND t2.redirect_tag_id IS NOT NULL
    WHERE t2.tag_id IS NULL;
    """
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        if match_hole_word:
            cursor.execute(query, (f"{keyword}",))
            id = cursor.fetchone()
            if id is None:
                return None
            else:
                return id[0]
        else:
            cursor.execute(query, (f"%{keyword}%",))
            ids = cursor.fetchall()
            if ids is None:
                return None
            else:
                return [id[0] for id in ids]


def get_tag_name() -> list:
    '''获得库中所有的tag_name'''
    query = "SELECT tag_name FROM tag"
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [row[0] for row in rows]


def get_tag_type_dict() -> dict:
    '''获得tag_type与tag_type_id中的映射关系,这是一个一一映射关系'''
    query = '''
    SELECT
        tag_type_id,
        tag_type_name
    FROM tag_type
    ORDER BY tag_order
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        logging.debug(rows)
        return dict(rows)


def get_unique_tag_type() -> list:
    '''获得tag_type'''
    query = '''
    SELECT
    DISTINCT tag_type_name
    FROM tag_type
    ORDER BY tag_order
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [row[0] for row in rows]


# Deprecated alias
getTags = get_tags
