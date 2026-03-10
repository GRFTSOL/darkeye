'''私有库查询'''
from config import PRIVATE_DATABASE
from ..connection import get_connection


def query_actress(actress_id) -> bool:
    '''判断某个actress_id是否在私有库内'''
    query = '''
    SELECT
        actress_id
    FROM
        favorite_actress
    WHERE actress_id=?
    '''
    with get_connection(PRIVATE_DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (actress_id,))
        id = cursor.fetchone()
    if id:
        return True
    return False


def query_work(work_id) -> bool:
    '''判断某个work_id是否在私有库内'''
    query = '''
    SELECT
        work_id
    FROM
        favorite_work
    WHERE work_id=?
    '''
    with get_connection(PRIVATE_DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (work_id,))
        id = cursor.fetchone()
    if id:
        return True
    return False


def get_unique_tools_from_masturbation() -> list:
    """
    查询自慰记录表 masturbation 中所有不重复的工具名称，并按使用频次从高到低排序。

    返回:
    - list: 工具名称的列表，按使用次数降序排列
    """
    query = '''
        SELECT
            tool_name ,
            count(*) AS num
        FROM masturbation
        GROUP BY tool_name
        ORDER BY num DESC
        '''
    with get_connection(PRIVATE_DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
    return [row[0] for row in rows]


def get_record_by_year(year: int, scope: int) -> dict:
    """
    根据指定年份，查询撸管记录 masturbation 表中每天的次数统计，
    并返回一个字典，键为 QDate 类型日期，值为当天次数。

    参数:
    - year: 整数年份，例如 2025
    - scope: 0撸管，1做爱，2晨勃

    返回:
    - dict: {QDate: int}，键为 PySide6.QtCore.QDate 对象，值为该日次数
    """
    match scope:
        case 0:
            query = '''
    SELECT
        DATE(start_time) AS day,
        COUNT(*) AS count_per_day
    FROM masturbation
    WHERE strftime('%Y', start_time) = ?
    GROUP BY day
    ORDER BY day;
    '''
        case 1:
            query = '''
    SELECT
        DATE(event_time) AS day,
        COUNT(*) AS count_per_day
    FROM love_making
    WHERE strftime('%Y', event_time) = ?
    GROUP BY day
    ORDER BY day;
    '''
        case 2:
            query = '''
    SELECT
        DATE(arousal_time) AS day,
        COUNT(*) AS count_per_day
    FROM sexual_arousal
    WHERE strftime('%Y', arousal_time) = ?
    GROUP BY day
    ORDER BY day;
    '''

    with get_connection(PRIVATE_DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (str(year),))
        data = cursor.fetchall()
    result = {}
    from PySide6.QtCore import QDate
    for date_str, val in data:
        y, month, day = map(int, date_str.split('-'))
        qdate = QDate(y, month, day)
        result[qdate] = val
    return result


def get_record_count_in_days(days: int, scope: int) -> int:
    """
    统计指定天数内的撸管总次数。

    参数:
        days (int): 向前统计的天数范围。
        scope (int): 统计范围，0撸管，1做爱，2晨勃

    返回:
        int: 在该时间范围内的总数。
    """
    match scope:
        case 0:
            query = '''
            SELECT
                count(*) AS count
            FROM
                masturbation
            WHERE start_time >= DATE('now', printf('-%d day', ?))
            '''
        case 1:
            query = '''
            SELECT
                count(*) AS count
            FROM
                love_making
            WHERE event_time >= DATE('now', printf('-%d day', ?))
            '''
        case 2:
            query = '''
            SELECT
                count(*) AS count
            FROM
                sexual_arousal
            WHERE arousal_time >= DATE('now', printf('-%d day', ?))
            '''
    with get_connection(PRIVATE_DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (days,))
        return cursor.fetchone()[0]


def get_record_count_by_year(year: int, scope: int) -> int:
    """
    根据指定年份，查询记录的次数

    参数:
    - year: 整数年份，例如 2025
    - scope: 范围，0撸管，1做爱，2晨勃

    返回:
    - 次数
    """
    match scope:
        case 0:
            query = '''
    SELECT
        COUNT(*) AS count
    FROM masturbation
    WHERE strftime('%Y', start_time) = ?
    '''
        case 1:
            query = '''
    SELECT
        COUNT(*) AS count
    FROM love_making
    WHERE strftime('%Y', event_time) = ?
    '''
        case 2:
            query = '''
    SELECT
        COUNT(*) AS count
    FROM sexual_arousal
    WHERE strftime('%Y', arousal_time) = ?
    '''
    with get_connection(PRIVATE_DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (str(year),))
        return cursor.fetchone()[0]


def get_record_early_year() -> int | None:
    '''返回三表最早记录的年份'''
    query = '''
    SELECT MIN(year) AS earliest_year FROM (
        SELECT MIN(strftime('%Y', start_time)) AS year FROM masturbation
        UNION ALL
        SELECT MIN(strftime('%Y', event_time)) AS year FROM love_making
        UNION ALL
        SELECT MIN(strftime('%Y', arousal_time)) AS year FROM sexual_arousal
    );
    '''
    with get_connection(PRIVATE_DATABASE, True) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        row = cursor.fetchone()
        if row and row[0]:
            return int(row[0])
        else:
            return None
