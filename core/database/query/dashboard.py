"""仪表盘域查询"""

import logging

from config import DATABASE
from ..connection import get_connection
from ..db_utils import attach_private_db, detach_private_db


def get_dashboard_stats() -> dict:
    """
    Dashboard 数据库概览统计，返回 7 项计数字典。
    键与 DashboardPage 统计卡片一一对应。
    """
    result = {
        "work_count": 0,
        "actress_count": 0,
        "actor_count": 0,
        "tag_count": 0,
        "recent_30_days": 0,
        "favorite_work_count": 0,
        "favorite_actress_count": 0,
    }
    try:
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()

            # 作品总数
            cursor.execute("SELECT COUNT(*) FROM work")
            result["work_count"] = cursor.fetchone()[0]

            # 女优总数
            cursor.execute("SELECT COUNT(*) FROM actress")
            result["actress_count"] = cursor.fetchone()[0]

            # 男优总数
            cursor.execute("SELECT COUNT(*) FROM actor")
            result["actor_count"] = cursor.fetchone()[0]

            # Tag 总数（排除重定向）
            cursor.execute("SELECT COUNT(*) FROM tag WHERE redirect_tag_id IS NULL")
            result["tag_count"] = cursor.fetchone()[0]

            # 近 30 天新增作品
            cursor.execute(
                """
                SELECT COUNT(*) FROM work
                WHERE create_time >= date('now', '-30 day')
                """
            )
            result["recent_30_days"] = cursor.fetchone()[0]

            # 收藏作品、收藏女优（需附加私有库）
            attach_private_db(cursor)
            try:
                cursor.execute("SELECT COUNT(*) FROM priv.favorite_work")
                result["favorite_work_count"] = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM priv.favorite_actress")
                result["favorite_actress_count"] = cursor.fetchone()[0]
            finally:
                detach_private_db(cursor)
    except Exception as e:
        logging.error(f"get_dashboard_stats 查询失败: {e}")
    return result
