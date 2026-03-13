'''混合库统计查询（scope 相关）'''
import logging

from config import DATABASE
from ..connection import get_connection
from ..db_utils import attach_private_db, detach_private_db

from ._common import masturbationsql, masturbation_actress_sql, all_years_sql


def fetch_work_actress_avg_age(scope: int) -> list[tuple]:
    """
    获取作品中女优的平均拍摄年龄及权重。

    参数：
        scope (int):
            0 - 收藏作品内数据
            1 - 撸过作品的数据（权重固定为 1）
            2 - 撸过作品带权重的数据（权重为撸的次数）
           -1 - 公共库内作品平均年龄数据

    返回：
        list[tuple]: [(avg_age, weight), ...]
    """
    match scope:
        case 0:
            query = '''
            SELECT
            avg_age ,
            1 AS weight
            FROM v_work_all_info
            JOIN priv.favorite_work fav ON fav.work_id=v_work_all_info.work_id
            WHERE avg_age is not NULL
            '''
        case 1:
            query = f'''WITH {masturbationsql}
SELECT
    avg_age ,
     1 AS weight
FROM v_work_all_info
JOIN masturbation_count ON masturbation_count.work_id=v_work_all_info.work_id
WHERE avg_age is not NULL
            '''
        case 2:
            query = f'''WITH {masturbationsql}
SELECT
    avg_age ,
    masturbation_count.masturbation_count AS weight
FROM v_work_all_info
JOIN masturbation_count ON masturbation_count.work_id=v_work_all_info.work_id
WHERE avg_age is not NULL
            '''
        case -1:
            query = '''
            SELECT
                avg_age,
                1 AS weight
            FROM
                v_work_all_info
            WHERE avg_age is not NULL
            '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        if scope in (0, 1, 2):
            attach_private_db(cursor)
        cursor.execute(query)
        results = cursor.fetchall()
        if scope in (0, 1, 2):
            detach_private_db(cursor)
    return results


def fetch_actress_cup_distribution(scope: int) -> list[tuple]:
    """
    获取女优罩杯分布数据。

    参数:
        scope (int):
            - -1: 统计主库内所有女优的罩杯分布
            -  0: 统计收藏作品中女优的罩杯分布（来自私有库 priv）
            -  1: 统计撸管过的女优罩杯分布（人数，不重复）
            -  2: 统计撸管次数按罩杯分布（次数总和）

    返回:
        list[tuple]: [(cup, num/count), ...]
    """
    match scope:
        case 0:
            query = '''
            SELECT
                cup ,
                COUNT(*) AS num
            FROM actress
            JOIN priv.favorite_actress fav ON fav.actress_id=actress.actress_id
            WHERE cup is not NULL AND cup != ''
            GROUP BY cup
            ORDER BY cup
            '''
        case 1:
            query = f'''WITH {masturbation_actress_sql}
                SELECT
                    cup,
                    COUNT(*) AS count
                FROM actress a
                JOIN masturbation_actress ma ON ma.actress_id=a.actress_id
                WHERE cup IS NOT NULL AND cup != '' AND ma.num !=0
                GROUP BY cup
                ORDER BY cup
            '''
        case 2:
            query = f'''WITH {masturbation_actress_sql}
            SELECT
                cup,
                sum(ma.num) AS count
            FROM actress a
            JOIN masturbation_actress ma ON ma.actress_id=a.actress_id
            WHERE cup IS NOT NULL AND cup != '' AND ma.num !=0
            GROUP BY cup
            ORDER BY cup
            '''
        case -1:
            query = '''
            SELECT
                cup,
                COUNT(*) AS num
            FROM actress
            WHERE cup IS NOT NULL AND cup != ''
            GROUP BY cup
            ORDER BY cup
            '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        if scope in (0, 1, 2):
            attach_private_db(cursor)
        cursor.execute(query)
        results = cursor.fetchall()
        if scope in (0, 1, 2):
            detach_private_db(cursor)
    return results


def fetch_actress_height_with_weights(scope: int) -> list[tuple]:
    """
    根据不同的统计范围 (scope) 获取女优身高及权重数据。

    参数:
        scope (int):
            - 0: 收藏的女优（数据来自私有库 priv.favorite_actress）
            - 1: 有过自慰记录的女优（权重=1）
            - 2: 有过自慰记录的女优（权重=次数 num）
            - -1: 所有女优（权重=1）

    返回:
        list[tuple]: 每个元素为 (height, weight) 的元组列表。
    """
    match scope:
        case 0:
            query = '''
            SELECT
                height,
                1 AS weight
            FROM actress
            JOIN priv.favorite_actress fav ON fav.actress_id=actress.actress_id
            WHERE height IS NOT NULL AND height != '' AND height != 0
            '''
        case 1:
            query = f'''WITH {masturbation_actress_sql}
            SELECT
                a.height,
                1 AS weight
            FROM actress a
            JOIN masturbation_actress ma ON ma.actress_id=a.actress_id
            WHERE height IS NOT NULL AND height != '' AND ma.num !=0  AND height != 0
            '''
        case 2:
            query = f'''WITH {masturbation_actress_sql}
            SELECT
                a.height,
                ma.num AS weights
            FROM actress a
            JOIN masturbation_actress ma ON ma.actress_id=a.actress_id
            WHERE height IS NOT NULL AND height != '' AND ma.num !=0  AND height != 0
            '''
        case -1:
            query = '''
            SELECT
                height,
                1 AS weight
            FROM actress
            WHERE height IS NOT NULL AND height != '' AND height != 0
            '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        if scope in (0, 1, 2):
            attach_private_db(cursor)
        cursor.execute(query)
        results = cursor.fetchall()
        if scope in (0, 1, 2):
            detach_private_db(cursor)
    return results


def fetch_actress_waist_hip_stats(scope: int) -> list[tuple]:
    """
    获取女优腰围、臀围及腰臀比的统计数据。

    参数:
        scope (int):
            - 0: 收藏女优数据（从私库 favorite_actress 获取）
            - 1: 撸过的女优数据（从 masturbation_actress 获取）
            - 2: 撸过的女优数据，并按撸的次数加权统计（SUM(num)）
            - -1: 公共库中所有女优数据（不依赖私库）

    返回:
        list[tuple]: 每个元组包含 (waist, hip, frequency/weight, wh_ratio)
    """
    match scope:
        case 0:
            query = '''
            SELECT
                waist,
                hip,
                COUNT(*) AS frequency,
                round(waist*1.0/hip,2)AS wh_ratio
            FROM
                actress a
            JOIN priv.favorite_actress fav ON fav.actress_id=a.actress_id
            WHERE
                waist IS NOT NULL AND hip IS NOT NULL  AND waist != 0  AND hip != 0
            GROUP BY
                waist, hip
            ORDER BY
                frequency DESC
            '''
        case 1:
            query = f'''WITH {masturbation_actress_sql}
                SELECT
                    waist,
                    hip,
                    COUNT(*) AS frequency,
                    round(waist*1.0/hip,2)AS wh_ratio
                FROM
                    actress a
                JOIN masturbation_actress ma ON ma.actress_id=a.actress_id

                WHERE
                    waist IS NOT NULL
                    AND hip IS NOT NULL
                    AND ma.num !=0 AND waist != 0  AND hip != 0
                GROUP BY
                    waist, hip
                ORDER BY
                    frequency DESC
            '''
        case 2:
            query = f'''WITH {masturbation_actress_sql}
            SELECT
                waist,
                hip,
                SUM(ma.num) as weight,
                round(waist*1.0/hip,2)AS wh_ratio
            FROM
                actress a
            JOIN masturbation_actress ma ON ma.actress_id=a.actress_id

            WHERE
                waist IS NOT NULL
                AND hip IS NOT NULL
                AND ma.num !=0 AND waist != 0  AND hip != 0
            GROUP BY
                waist, hip
            ORDER BY
                weight DESC
            '''
        case -1:
            query = '''
            SELECT
                waist,
                hip,
                COUNT(*) AS frequency,
                round(waist*1.0/hip,2)AS wh_ratio
            FROM
                actress a
            WHERE
                waist IS NOT NULL AND hip IS NOT NULL AND waist != 0  AND hip != 0
            GROUP BY
                waist, hip
            ORDER BY
                frequency DESC
            '''
    logging.debug(f"Executing SQL:\n{query}")
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        if scope in (0, 1, 2):
            attach_private_db(cursor)
        cursor.execute(query)
        results = cursor.fetchall()
        if scope in (0, 1, 2):
            detach_private_db(cursor)
    return results


def fetch_top_directors_by_scope(scope: int) -> list[tuple]:
    """
    获取导演及其对应拍片数量的排名数据。

    参数:
        scope (int): 查询范围
            0  - 收藏作品中的导演及作品数
            1  - 撸过的作品导演及作品数（次数统计）
            2  - 撸过的作品导演及作品数（权重统计）
           -1  - 全库导演及作品数

    返回:
        List[tuple]: 每项为 (director:str, num:int)，按拍片数降序排列，最多返回10条
    """
    match scope:
        case 0:
            query = '''
            SELECT
                director AS director,
                COUNT(*) AS num
            FROM
                work
            JOIN priv.favorite_work fav ON fav.work_id=work.work_id
            WHERE
                director IS NOT NULL AND director != '----' AND director != ''
            GROUP BY
                director
            ORDER BY
                num DESC
            Limit 20
            '''
        case 1:
            query = f'''WITH {masturbationsql}
            SELECT
                director AS director,
                COUNT(*) AS num
            FROM
                work
            JOIN masturbation_count ON masturbation_count.work_id=work.work_id
            WHERE
                director IS NOT NULL AND director != '----' AND director != ''
            GROUP BY
                director
            ORDER BY
                num DESC
            Limit 20
            '''
        case 2:
            query = f'''WITH {masturbationsql}
            SELECT
                director AS director,
                sum(masturbation_count.masturbation_count) AS num
            FROM
                work
            JOIN masturbation_count ON masturbation_count.work_id=work.work_id
            WHERE
                director IS NOT NULL AND director != '----' AND director != ''
            GROUP BY
                director
            ORDER BY
                num DESC
            Limit 20
            '''
        case -1:
            query = '''
            SELECT
                director AS director,
                COUNT(*) AS num
            FROM
                work
            WHERE
                director IS NOT NULL AND director != '----' AND director != ''
            GROUP BY
                director
            ORDER BY
                num DESC
            Limit 20
            '''
    logging.debug(f"Executing SQL:\n{query}")
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        if scope in (0, 1, 2):
            attach_private_db(cursor)
        cursor.execute(query)
        results = cursor.fetchall()
        if scope in (0, 1, 2):
            detach_private_db(cursor)
    return results


def fetch_top_studios_by_scope(scope: int) -> list[tuple]:
    """
    获取制作商及其对应出现次数的排名信息。

    参数:
        scope (int): 查询范围
            0  - 收藏作品中出现的制作商及数量
            1  - 作品中撸管次数非空的制作商及作品数量统计
            2  - 作品中撸管次数非空的制作商及撸管次数加权统计
           -1  - 全库中出现的制作商及数量统计

    返回:
        List[tuple]: 每项为 (studio:str, num:int)，按出现次数降序排列，最多返回10条
    """
    match scope:
        case 0:
            query = '''
            SELECT
                studio ,
                COUNT(*) AS num
            FROM
                v_work_all_info
            JOIN priv.favorite_work fav ON fav.work_id=v_work_all_info.work_id
            WHERE
                studio IS NOT NULL
            GROUP BY
                studio
            ORDER BY
                num DESC
            LIMIT 20
            '''
        case 1:
            query = f'''WITH {masturbationsql}
            SELECT
                studio ,
                COUNT(*) AS num
            FROM
                v_work_all_info
            JOIN masturbation_count ON masturbation_count.work_id=v_work_all_info.work_id
            WHERE
                studio IS NOT NULL
            GROUP BY
                studio
            ORDER BY
                num DESC
            LIMIT 20
            '''
        case 2:
            query = f'''
WITH {masturbationsql}
SELECT
    studio ,
    sum(masturbation_count.masturbation_count) AS num
FROM
    v_work_all_info
JOIN masturbation_count ON masturbation_count.work_id=v_work_all_info.work_id
WHERE
    studio IS NOT NULL

GROUP BY
    studio
ORDER BY
    num DESC
LIMIT 20
'''
        case -1:
            query = '''
            SELECT
                studio ,
                COUNT(*) AS num
            FROM
                v_work_all_info
            WHERE
                studio IS NOT NULL
            GROUP BY
                studio
            ORDER BY
                num DESC
            LIMIT 20
            '''
    logging.debug(f"Executing SQL:\n{query}")
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        if scope in (0, 1, 2):
            attach_private_db(cursor)
        cursor.execute(query)
        results = cursor.fetchall()
        if scope in (0, 1, 2):
            detach_private_db(cursor)
    return results


def get_tag_frequence(scope: int) -> dict:
    '''获得tag使用次数的sql语句
    参数:
        scope (int): 查询范围
            0  - 收藏作品中出现的制作商及数量
            1  - 作品中撸管作品统计
            2  - 作品中撸管次数加权统计
           -1  - 全库中出及数量统计
    返回字典，形式如下：
    {
        '黑丝':20,
        '制服':35,
        '口交':50
    }
    然后可以直接传给wordcloud生成词云
    '''
    match scope:
        case 0:
            query = '''
        SELECT
        tag_name,
        count(tag_name) AS num
        FROM work_tag_relation
        JOIN priv.favorite_work fav ON fav.work_id=work_tag_relation.work_id
        JOIN tag ON work_tag_relation.tag_id=tag.tag_id
        WHERE tag.tag_type_id !=1 AND tag.tag_type_id !=6
        GROUP BY tag_name
        ORDER BY num DESC
            '''
        case 1:
            query = f'''WITH {masturbationsql}
            SELECT
            tag_name,
            count(tag_name) AS num
            FROM work_tag_relation
            JOIN masturbation_count ON masturbation_count.work_id=work_tag_relation.work_id
            JOIN tag ON work_tag_relation.tag_id=tag.tag_id
            WHERE tag.tag_type_id !=1 AND tag.tag_type_id !=6
            GROUP BY tag_name
            ORDER BY num DESC
            '''
        case 2:
            query = f'''
WITH {masturbationsql}
SELECT
    tag_name,
    sum(masturbation_count.masturbation_count) AS num
FROM work_tag_relation
JOIN masturbation_count ON masturbation_count.work_id=work_tag_relation.work_id
JOIN tag ON work_tag_relation.tag_id=tag.tag_id
WHERE tag.tag_type_id !=1 AND tag.tag_type_id !=6
GROUP BY tag_name
ORDER BY num DESC

'''
        case -1:
            query = '''
        SELECT
        tag_name,
        count(tag_name) AS num
        FROM work_tag_relation
        JOIN tag ON work_tag_relation.tag_id=tag.tag_id
        WHERE tag.tag_type_id !=1 AND tag.tag_type_id !=6
        GROUP BY tag_name
        ORDER BY num DESC
        '''
    logging.debug(f"Executing SQL:\n{query}")
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        if scope in (0, 1, 2):
            attach_private_db(cursor)
        cursor.execute(query)
        tag_dict = dict(cursor.fetchall())
        if scope in (0, 1, 2):
            detach_private_db(cursor)
    return tag_dict


def fetch_work_release_by_year_by_scope(scope: int) -> list[tuple]:
    '''根据范围返回作品的发行年份统计
        参数:
        scope (int): 查询范围
            0  - 收藏作品
            1  - 作品中撸管作品统计
            2  - 作品中撸管次数加权统计
           -1  - 公共库
    '''
    year_range_sql = '''
year_range AS (
    SELECT
        CAST(MIN(SUBSTR(release_date, 1, 4)) AS INTEGER) AS min_year,
        CAST(MAX(SUBSTR(release_date, 1, 4)) AS INTEGER) AS max_year
    FROM work
    WHERE release_date != '' AND release_date IS NOT NULL
)
'''

    fillna_sql = '''
SELECT
    ay.year,
    COALESCE(ac.count, 0) AS count
FROM all_years ay
LEFT JOIN actual_counts ac ON ay.year = ac.year
ORDER BY ay.year;
'''

    match scope:
        case 0:
            query = f'''
WITH {year_range_sql},
{all_years_sql},
actual_counts AS (
    SELECT
        SUBSTR(release_date, 1, 4) AS year,
        COUNT(*) AS count
    FROM work
    JOIN priv.favorite_work fav ON fav.work_id=work.work_id
    WHERE release_date != '' AND release_date IS NOT NULL
    GROUP BY year
)
{fillna_sql}
'''
        case 1:
            query = f'''
WITH {masturbationsql},
{year_range_sql},
{all_years_sql},
actual_counts AS (
    SELECT
        SUBSTR(release_date, 1, 4) AS year,
        COUNT(*) AS count
    FROM work
    JOIN masturbation_count ON masturbation_count.work_id=work.work_id
    WHERE release_date != '' AND release_date IS NOT NULL
    GROUP BY year
)
{fillna_sql}
'''
        case 2:
            query = f'''
WITH {masturbationsql},
{year_range_sql},
{all_years_sql},
actual_counts AS (
    SELECT
        SUBSTR(release_date, 1, 4) AS year,
        sum(masturbation_count.masturbation_count) AS count
    FROM work
    JOIN masturbation_count ON masturbation_count.work_id=work.work_id
    WHERE release_date != '' AND release_date IS NOT NULL
    GROUP BY year
)
{fillna_sql}
'''
        case -1:
            query = f'''
WITH {year_range_sql},
{all_years_sql},
actual_counts AS (
    SELECT
        SUBSTR(release_date, 1, 4) AS year,
        COUNT(*) AS count
    FROM work
    WHERE release_date != '' AND release_date IS NOT NULL
    GROUP BY year
)
{fillna_sql}
'''
    logging.debug(f"Execute SQL\n{query}")

    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        attach_private_db(cursor)
        cursor.execute(query)
        results = cursor.fetchall()
        detach_private_db(cursor)
    return results


def fetch_actress_debut_by_year_by_scope(scope: int) -> list[tuple]:
    '''根据范围返回女优的出道年份统计
        参数:
        scope (int): 查询范围
            0  - 收藏作品
            1  - 作品中撸管作品统计
            2  - 作品中撸管次数加权统计
           -1  - 公共库
    '''
    year_range_sql = '''
year_range AS (
    SELECT
        CAST(MIN(SUBSTR(debut_date, 1, 4)) AS INTEGER) AS min_year,
        CAST(MAX(SUBSTR(debut_date, 1, 4)) AS INTEGER) AS max_year
    FROM actress
    WHERE debut_date != '' AND debut_date IS NOT NULL
)
'''

    fillna_sql = '''
SELECT
    ay.year,
    COALESCE(ac.count, 0) AS count
FROM all_years ay
LEFT JOIN actual_counts ac ON ay.year = ac.year
ORDER BY ay.year;
'''

    match scope:
        case 0:
            query = f'''
WITH {year_range_sql},
{all_years_sql},
actual_counts AS (
    SELECT
        SUBSTR(debut_date, 1, 4) AS year,
        COUNT(*) AS count
    FROM actress
    JOIN priv.favorite_actress fav ON fav.actress_id=actress.actress_id
    WHERE debut_date != '' AND debut_date IS NOT NULL
    GROUP BY year
)
{fillna_sql}
'''
        case 1:
            query = f'''
WITH {masturbation_actress_sql},
{year_range_sql},
{all_years_sql},
actual_counts AS (
    SELECT
        SUBSTR(debut_date, 1, 4) AS year,
        COUNT(*) AS count
    FROM actress
    JOIN masturbation_actress ma ON ma.actress_id=actress.actress_id
    WHERE debut_date != '' AND debut_date IS NOT NULL AND ma.num!=0
    GROUP BY year
)
{fillna_sql}
'''
        case 2:
            query = f'''
WITH {masturbation_actress_sql},
{year_range_sql},
{all_years_sql},
actual_counts AS (
    SELECT
        SUBSTR(debut_date, 1, 4) AS year,
        sum(ma.num) AS count
    FROM actress
    JOIN masturbation_actress ma ON ma.actress_id=actress.actress_id
    WHERE debut_date != '' AND debut_date IS NOT NULL
    GROUP BY year
)
{fillna_sql}
'''
        case -1:
            query = f'''
WITH {year_range_sql},
{all_years_sql},
actual_counts AS (
    SELECT
        SUBSTR(debut_date, 1, 4) AS year,
        COUNT(*) AS count
    FROM actress
    WHERE debut_date != '' AND debut_date IS NOT NULL
    GROUP BY year
)
{fillna_sql}
'''
    logging.debug(f"Execute SQL\n{query}")

    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        attach_private_db(cursor)
        cursor.execute(query)
        results = cursor.fetchall()
        detach_private_db(cursor)
    return results


def get_actress_by_plane() -> list[tuple]:
    '''返回撸的最多的女优的次数,25个'''
    query = f'''WITH {masturbation_actress_sql}
    SELECT
        actress_name,
        num
    FROM masturbation_actress
    ORDER BY num DESC
    LIMIT 25
    '''
    logging.debug(f"Execute SQL\n{query}")
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        attach_private_db(cursor)
        cursor.execute(query)
        results = cursor.fetchall()
        detach_private_db(cursor)
    return results


# Deprecated aliases
fetch_workReleaseByYear_by_scope = fetch_work_release_by_year_by_scope
fetch_actressDebutByYear_by_scope = fetch_actress_debut_by_year_by_scope
getActressByPlane = get_actress_by_plane


def get_top_actress_by_masturbation_count(days_interval: int) -> dict | None:
    """
    获取指定天数内撸管次数最多的女优信息，若次数相同则最近撸管时间优先。

    参数:
        days_interval (int): 向前统计的天数范围。

    返回:
        dict: 包含女优姓名（中文）、头像链接、最近撸管时间及撸管次数的字典。
    """
    query = '''
    SELECT
        a.actress_id,
        (SELECT cn FROM actress_name WHERE actress_id = a.actress_id AND name_type = 1) AS actress_name,
        a.image_urlA,
        MAX(m.start_time) AS latest_masturbate_time,
        COUNT(m.work_id) AS masturbation_count
    FROM
        actress a
    JOIN work_actress_relation war ON a.actress_id = war.actress_id
    JOIN work w ON war.work_id = w.work_id
    JOIN priv.masturbation m ON m.work_id = w.work_id  AND m.start_time >= DATE('now', printf('-%d day',?))
    GROUP BY
        a.actress_id
    ORDER BY
        masturbation_count DESC,
        latest_masturbate_time DESC
    LIMIT 1
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        attach_private_db(cursor)
        cursor.execute(query, (days_interval,))
        data = cursor.fetchone()
        column_names = [description[0] for description in cursor.description]
        detach_private_db(cursor)
        if data:
            return dict(zip(column_names, data))
        else:
            return None


def get_unmasturbated_work_count() -> int:
    """
    统计收藏的影片中尚未有撸管记录的影片数量。

    返回：
        int: 收藏影片中未撸管的影片总数。
    """
    query = f'''WITH {masturbationsql}
SELECT
    count(*) AS total_count
FROM
    priv.favorite_work w
LEFT JOIN masturbation_count ON masturbation_count.work_id=w.work_id
WHERE masturbation_count is NULL
'''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        attach_private_db(cursor)
        cursor.execute(query)
        count = cursor.fetchone()[0]
        detach_private_db(cursor)
    return count


def fetch_actress_debut_age() -> list[tuple]:
    """
    获取女优的出道年龄及权重。

    返回：
        list[tuple]: [(debut_age, weight), ...]
    """
    query = '''
SELECT
    round((julianday(a.debut_date) - julianday(a.birthday)) / 365.25,1)-0.5 AS debut_age,
    1 AS weight
FROM actress a
WHERE  a.birthday IS NOT NULL AND a.debut_date IS NOT NULL AND a.debut_date !='' AND a.birthday !=''
    '''
    with get_connection(DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
    return results
