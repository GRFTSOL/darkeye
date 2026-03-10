from typing import Optional, List

from config import DATABASE
from core.database.connection import get_connection
from core.database.model.model import Actor


class ActorRepository:
    """
    actor 表的仓储：
    - 根据 actor_id 获取 / 更新男优基础信息
    - 新增男优记录（仅基础信息，不含 actor_name）
    """

    def get_by_id(self, actor_id: int) -> Optional[Actor]:
        query = """
        SELECT
            actor_id,
            birthday,
            height,
            handsome,
            fat,
            need_update,
            create_time
        FROM actor
        WHERE actor_id = ?
        """
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (actor_id,))
            row = cursor.fetchone()
            if not row:
                return None
            columns = [d[0] for d in cursor.description]
            data = dict(zip(columns, row))
        return Actor.from_dict(data)

    def list_all(self) -> List[Actor]:
        query = """
        SELECT
            actor_id,
            birthday,
            height,
            handsome,
            fat,
            need_update,
            create_time
        FROM actor
        ORDER BY actor_id
        """
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [d[0] for d in cursor.description]
        return [Actor.from_dict(dict(zip(columns, row))) for row in rows]

    def create(self, actor: Actor) -> int:
        """
        新增一条 actor 记录。
        注意：actor_name 相关数据仍然使用原有的 insert 辅助函数。
        """
        query = """
        INSERT INTO actor (
            birthday,
            height,
            handsome,
            fat,
            need_update
        ) VALUES (
            ?,?,?,?,
            ?
        )
        """
        with get_connection(DATABASE, False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    actor.birthday,
                    actor.height,
                    actor.handsome,
                    actor.fat,
                    actor.need_update,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def update(self, actor: Actor) -> bool:
        if actor.actor_id is None:
            return False

        query = """
        UPDATE actor
        SET
            birthday = ?,
            height = ?,
            handsome = ?,
            fat = ?,
            need_update = ?
        WHERE actor_id = ?
        """
        with get_connection(DATABASE, False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    actor.birthday,
                    actor.height,
                    actor.handsome,
                    actor.fat,
                    actor.need_update,
                    actor.actor_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

