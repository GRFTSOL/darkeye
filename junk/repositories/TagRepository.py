from typing import Optional, List

from config import DATABASE
from core.database.connection import get_connection
from core.database.model.model import Tag


class TagRepository:
    """
    tag 表的仓储：
    - 按 id / 名称获取标签
    - 新增 / 更新 / 删除标签
    """

    def get_by_id(self, tag_id: int) -> Optional[Tag]:
        query = """
        SELECT
            tag_id,
            tag_name,
            tag_type_id,
            color,
            redirect_tag_id,
            detail,
            group_id
        FROM tag
        WHERE tag_id = ?
        """
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (tag_id,))
            row = cursor.fetchone()
            if not row:
                return None
            columns = [d[0] for d in cursor.description]
            data = dict(zip(columns, row))
        return Tag.from_dict(data)

    def get_by_name(self, tag_name: str) -> Optional[Tag]:
        query = """
        SELECT
            tag_id,
            tag_name,
            tag_type_id,
            color,
            redirect_tag_id,
            detail,
            group_id
        FROM tag
        WHERE tag_name = ?
        """
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (tag_name,))
            row = cursor.fetchone()
            if not row:
                return None
            columns = [d[0] for d in cursor.description]
            data = dict(zip(columns, row))
        return Tag.from_dict(data)

    def list_all(self) -> List[Tag]:
        query = """
        SELECT
            tag_id,
            tag_name,
            tag_type_id,
            color,
            redirect_tag_id,
            detail,
            group_id
        FROM tag
        ORDER BY tag_type_id, tag_name
        """
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [d[0] for d in cursor.description]
        return [Tag.from_dict(dict(zip(columns, row))) for row in rows]

    def create(self, tag: Tag) -> int:
        """
        新增一条 tag 记录。
        注意：如果你当前仍使用 insert.insert_tag，可以逐步迁移到本仓储。
        """
        query = """
        INSERT INTO tag (
            tag_name,
            tag_type_id,
            color,
            redirect_tag_id,
            detail,
            group_id
        ) VALUES (
            ?,?,?,?,
            ?,?
        )
        """
        with get_connection(DATABASE, False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    tag.tag_name,
                    tag.tag_type_id,
                    tag.color,
                    tag.redirect_tag_id,
                    tag.detail,
                    tag.group_id,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def update(self, tag: Tag) -> bool:
        if tag.tag_id is None:
            return False

        query = """
        UPDATE tag
        SET
            tag_name = ?,
            tag_type_id = ?,
            color = ?,
            redirect_tag_id = ?,
            detail = ?,
            group_id = ?
        WHERE tag_id = ?
        """
        with get_connection(DATABASE, False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    tag.tag_name,
                    tag.tag_type_id,
                    tag.color,
                    tag.redirect_tag_id,
                    tag.detail,
                    tag.group_id,
                    tag.tag_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete(self, tag_id: int) -> bool:
        query = "DELETE FROM tag WHERE tag_id = ?"
        with get_connection(DATABASE, False) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (tag_id,))
            conn.commit()
            return cursor.rowcount > 0

