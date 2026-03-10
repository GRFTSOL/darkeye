'''女优域查询'''
import logging

from config import DATABASE
from ..connection import get_connection


def get_actress_info(actress_id: int) -> dict:
    '''查询一个女优的所有的信息'''
    query = '''
    SELECT
        n.cn,
        n.jp,
        n.en,
        n.kana,
        ROUND((julianday('now') - julianday(a.birthday)) / 365.25, 1) AS age,
        a.image_urlA,
        a.birthday,
        a.height,
        a.bust,
        a.waist,
        a.hip,
        a.cup,
        a.debut_date,
        a.need_update
    FROM actress a
    LEFT JOIN actress_name n
        ON n.actress_id = a.actress_id
    AND n.redirect_actress_name_id IS NULL
    WHERE a.actress_id = ?
    '''

    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (actress_id,))
        row = cursor.fetchone()
        logging.debug(f"查询到女优的信息：\n{row}")
        column_names = [description[0] for description in cursor.description]
    return dict(zip(column_names, row))


def get_all_actress_data() -> list[dict]:
    '''公共库内女优的身材数据'''
    query = '''
            SELECT
                height,
                bust,
                waist,
                hip,
                cup
            FROM
                actress a
            WHERE
                height is NOT NULL AND height !=0
                AND waist IS NOT NULL AND waist !=0
                AND hip IS NOT NULL AND hip !=0
                AND bust IS NOT NULL AND bust !=0
                AND cup IS NOT NULL
            '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        column_names = [description[0] for description in cursor.description]
        results = [dict(zip(column_names, row)) for row in rows]
    return results


def get_null_actress() -> list:
    '''返回所有的没有作品的actress_id列表'''
    query = """
    SELECT a.actress_id
    FROM actress AS a
    LEFT JOIN work_actress_relation AS r
        ON a.actress_id = r.actress_id
    WHERE r.actress_id IS NULL;
    """
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [row[0] for row in rows]


def exist_actress(name) -> int | None:
    '''根据name查询actress是否在库内'''
    query = '''
        SELECT
        actress_id
        FROM
        actress_name
        WHERE
        actress_name.jp=? OR actress_name.cn=? OR actress_name.en=?
        '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (name, name, name))
        id = cursor.fetchone()
        if id is None:
            return None
        else:
            return id[0]


def exist_minnao_id(actress_id) -> int:
    '''查询女优是否存在minnao-av的缓存'''
    query = '''
        SELECT
            minnano_url
        FROM actress
        WHERE
            actress_id=?
        '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (actress_id,))
        id = cursor.fetchone()
        if id is None:
            return None
        else:
            return id[0]


def get_actressname() -> list:
    '''获得库中所有的女优的名字，包括曾用名，返回女优的名字'''
    query = '''
    SELECT
    cn
    FROM
    actress_name
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [row[0] for row in rows]


def get_actress_allname(actress_id) -> list[dict]:
    '''反回某个女优的所有名字,而且是根据链式返回的，最前面的是最新的'''
    query = '''
    WITH RECURSIVE chain AS (
    -- 递归的起始部分：找到链条的起点
    SELECT
        actress_name_id,
        cn,
        jp,
        en,
        kana,
        redirect_actress_name_id,
        1 AS level
    FROM
        actress_name
    WHERE
        actress_id = ? AND redirect_actress_name_id IS NULL

    UNION ALL

    -- 递归部分：顺着链条查找
    SELECT
        t2.actress_name_id,
        t2.cn,
        t2.jp,
        t2.en,
        t2.kana,
        t2.redirect_actress_name_id,
        chain.level + 1 AS level
    FROM
        actress_name AS t2
    JOIN
        chain ON t2.redirect_actress_name_id = chain.actress_name_id
    )
    SELECT
        actress_name_id,
        cn,
        jp,
        kana,
        en,
        redirect_actress_name_id,
        level
    FROM
        chain
    ORDER BY
        level;
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (actress_id,))
        rows = cursor.fetchall()
        column_names = [description[0] for description in cursor.description]
        results = [dict(zip(column_names, row)) for row in rows]
        return results


def get_cup_type() -> list[str]:
    '''返回女优所有的罩杯类型'''
    query = "SELECT DISTINCT cup FROM actress WHERE cup is not NULL ORDER BY cup"
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        cup_list = [row[0] for row in cursor.fetchall()]
    cup_list = [s for s in cup_list if s and s.strip()]
    return cup_list


def get_actress_body_data() -> list[dict]:
    '''公共库内女优的身材数据'''
    query = '''
            SELECT
                bust,
                waist,
                hip,
                cup
            FROM
                actress a
            WHERE
                waist IS NOT NULL
                AND hip IS NOT NULL
                AND bust IS NOT NULL
                AND cup IS NOT NULL
                AND waist !=0
                AND hip !=0
                AND bust !=0
            '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        column_names = [description[0] for description in cursor.description]
        results = [dict(zip(column_names, row)) for row in rows]
    return results


# Deprecated alias
getActressBodyData = get_actress_body_data


def get_all_actress_name(actress_id: int) -> list[dict]:
    query = """
SELECT
    actress_name_id AS id,
    jp AS name,
    redirect_actress_name_id AS redirect
FROM
    actress_name
WHERE actress_id=?
    """
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (actress_id,))
        rows = cursor.fetchall()
        column_names = [description[0] for description in cursor.description]
    if not rows:
        return None
    result = [dict(zip(column_names, row)) for row in rows]
    return result
