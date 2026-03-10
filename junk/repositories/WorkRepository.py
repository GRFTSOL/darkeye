from typing import Optional, List, Dict, Any

from config import DATABASE
from core.database.connection import get_connection
from core.database.model.model import Work


class WorkRepository:
    '''
    放在 WorkRepository 里的：
    - 根据 work_id / serial_number 获取作品；
    - 新增 / 修改 / 软删除作品的基础信息；
    - 查询 / 更新作品的 直接关系 ：标签、女优、男优（以及将来可能的“场景列表”等）。
    '''
    def get_by_id(self, work_id: int) -> Optional[Work]:
        query = """
        SELECT
            w.work_id,
            w.serial_number, 
            w.director,
            w.story,
            w.release_date,
            w.image_url,
            w.video_url,
            w.cn_title,
            w.jp_title,
            w.cn_story,
            w.jp_story,
            w.create_time,
            w.update_time,
            w.is_deleted,
            w.on_dan,
            (SELECT GROUP_CONCAT(actress_id) FROM work_actress_relation WHERE work_id = w.work_id) as actress_ids,
            (SELECT GROUP_CONCAT(actor_id) FROM work_actor_relation WHERE work_id = w.work_id) as actor_ids,
            (SELECT GROUP_CONCAT(tag_id) FROM work_tag_relation WHERE work_id = w.work_id) as tag_ids
        FROM work w
        WHERE w.work_id = ?
        """
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (work_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            columns = [d[0] for d in cursor.description]
            data = dict(zip(columns, row))
            
            # 处理 list 字段
            for field in ['actress_ids', 'actor_ids', 'tag_ids']:
                if data.get(field):
                    data[field] = [int(x) for x in str(data[field]).split(',')]
                else:
                    data[field] = []
                
        return Work.from_dict(data)

    def get_by_serial_number(self, serial_number: str) -> Optional[Work]:
        query = """
        SELECT
            w.work_id,
            w.serial_number,
            w.director,
            w.story,
            w.release_date,
            w.image_url,
            w.video_url,
            w.cn_title,
            w.jp_title,
            w.cn_story,
            w.jp_story,
            w.create_time,
            w.update_time,
            w.is_deleted,
            w.javtxt_id,
            w.fcover_url,
            w.on_dan,
            (SELECT GROUP_CONCAT(actress_id) FROM work_actress_relation WHERE work_id = w.work_id) as actress_ids,
            (SELECT GROUP_CONCAT(actor_id) FROM work_actor_relation WHERE work_id = w.work_id) as actor_ids,
            (SELECT GROUP_CONCAT(tag_id) FROM work_tag_relation WHERE work_id = w.work_id) as tag_ids
        FROM work w
        WHERE w.serial_number = ?
        """
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (serial_number,))
            row = cursor.fetchone()
            if not row:
                return None
            
            columns = [d[0] for d in cursor.description]
            data = dict(zip(columns, row))
            
            for field in ['actress_ids', 'actor_ids', 'tag_ids']:
                if data.get(field):
                    data[field] = [int(x) for x in str(data[field]).split(',')]
                else:
                    data[field] = []
                
        return Work.from_dict(data)

    def create(self, work: Work) -> int:
        query = """
        INSERT INTO work (
            serial_number,
            director,
            story,
            release_date,
            image_url,
            video_url,
            cn_title,
            jp_title,
            cn_story,
            jp_story,
            is_deleted,
            javtxt_id,
            fcover_url,
            on_dan
        ) VALUES (
            ?,?,?,?,?,?,
            ?,?,?,?,?,?,
            ?,?
        )
        """
        with get_connection(DATABASE, False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    work.serial_number,
                    work.director,
                    work.story,
                    work.release_date,
                    work.image_url,
                    work.video_url,
                    work.cn_title,
                    work.jp_title,
                    work.cn_story,
                    work.jp_story,
                    work.is_deleted,
                    work.javtxt_id,
                    work.fcover_url,
                    work.on_dan,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def update(self, work: Work) -> bool:
        if work.work_id is None:
            return False
        query = """
        UPDATE work
        SET
            director = ?,
            story = ?,
            release_date = ?,
            image_url = ?,
            video_url = ?,
            cn_title = ?,
            jp_title = ?,
            cn_story = ?,
            jp_story = ?,
            is_deleted = ?,
            javtxt_id = ?,
            fcover_url = ?,
            on_dan = ?
        WHERE work_id = ?
        """
        with get_connection(DATABASE, False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    work.director,
                    work.story,
                    work.release_date,
                    work.image_url,
                    work.video_url,
                    work.cn_title,
                    work.jp_title,
                    work.cn_story,
                    work.jp_story,
                    work.is_deleted,
                    work.javtxt_id,
                    work.fcover_url,
                    work.on_dan,
                    work.work_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def soft_delete(self, work_id: int) -> bool:
        query = """
        UPDATE work
        SET is_deleted = 1
        WHERE work_id = ?
        """
        with get_connection(DATABASE, False) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (work_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_tags(self, work_id: int) -> List[Dict[str, Any]]:
        query = """
        SELECT
            t.tag_id,
            t.tag_name,
            tt.tag_type_name,
            t.color,
            t.detail,
            tt.tag_order
        FROM work_tag_relation wtr
        JOIN tag t ON t.tag_id = wtr.tag_id
        JOIN tag_type tt ON tt.tag_type_id = t.tag_type_id
        WHERE wtr.work_id = ?
        ORDER BY tt.tag_order, t.color
        """
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (work_id,))
            rows = cursor.fetchall()
            columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def get_actresses(self, work_id: int) -> Optional[List[Dict[str, Any]]]:
        query = """
        SELECT
            a.actress_id,
            (SELECT cn FROM actress_name WHERE actress_id = a.actress_id AND name_type = 1) AS actress_name
        FROM work w
        JOIN work_actress_relation war ON w.work_id = war.work_id
        JOIN actress a ON war.actress_id = a.actress_id
        WHERE w.work_id = ?
        """
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (work_id,))
            rows = cursor.fetchall()
            if not rows:
                return None
            columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def get_actors(self, work_id: int) -> Optional[List[Dict[str, Any]]]:
        query = """
        SELECT
            a.actor_id,
            (SELECT cn FROM actor_name WHERE actor_id = a.actor_id) AS actor_name
        FROM work w
        JOIN work_actor_relation war ON w.work_id = war.work_id
        JOIN actor a ON war.actor_id = a.actor_id
        WHERE w.work_id = ?
        """
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (work_id,))
            rows = cursor.fetchall()
            if not rows:
                return None
            columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
