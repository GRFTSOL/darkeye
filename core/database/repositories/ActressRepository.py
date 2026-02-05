from typing import Optional, List

from config import DATABASE
from core.database.connection import get_connection
from core.database.model.model import Actress


class ActressRepository:
    """
    actress 表的仓储：
    - 根据 actress_id 获取 / 更新女优基础信息
    - 新增女优记录（仅基础信息，不含姓名表 actress_name）
    """

    def get_by_id(self, actress_id: int) -> Optional[Actress]:
        query = """
        SELECT
            actress_id,
            birthday,
            height,
            bust,
            waist,
            hip,
            cup,
            debut_date,
            need_update,
            create_time,
            update_time,
            image_urlA,
            image_urlB,
            minnano_url
        FROM actress
        WHERE actress_id = ?
        """
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (actress_id,))
            row = cursor.fetchone()
            if not row:
                return None
            columns = [d[0] for d in cursor.description]
            data = dict(zip(columns, row))
        return Actress.from_dict(data)

    def list_all(self) -> List[Actress]:
        query = """
        SELECT
            actress_id,
            birthday,
            height,
            bust,
            waist,
            hip,
            cup,
            debut_date,
            need_update,
            create_time,
            update_time,
            image_urlA,
            image_urlB,
            minnano_url
        FROM actress
        ORDER BY actress_id
        """
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [d[0] for d in cursor.description]
        return [Actress.from_dict(dict(zip(columns, row))) for row in rows]

    def create(self, actress: Actress) -> int:
        """
        新增一条 actress 记录。
        注意：actress_name 相关数据仍然使用原有的 insert 辅助函数。
        """
        query = """
        INSERT INTO actress (
            birthday,
            height,
            bust,
            waist,
            hip,
            cup,
            debut_date,
            need_update,
            image_urlA,
            image_urlB,
            minnano_url
        ) VALUES (
            ?,?,?,?,?,?,
            ?,?,?,?,
            ?
        )
        """
        with get_connection(DATABASE, False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    actress.birthday,
                    actress.height,
                    actress.bust,
                    actress.waist,
                    actress.hip,
                    actress.cup,
                    actress.debut_date,
                    actress.need_update,
                    actress.image_urlA,
                    actress.image_urlB,
                    actress.minnano_url,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def update(self, actress: Actress) -> bool:
        if actress.actress_id is None:
            return False

        query = """
        UPDATE actress
        SET
            birthday = ?,
            height = ?,
            bust = ?,
            waist = ?,
            hip = ?,
            cup = ?,
            debut_date = ?,
            need_update = ?,
            image_urlA = ?,
            image_urlB = ?,
            minnano_url = ?
        WHERE actress_id = ?
        """
        with get_connection(DATABASE, False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    actress.birthday,
                    actress.height,
                    actress.bust,
                    actress.waist,
                    actress.hip,
                    actress.cup,
                    actress.debut_date,
                    actress.need_update,
                    actress.image_urlA,
                    actress.image_urlB,
                    actress.minnano_url,
                    actress.actress_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

