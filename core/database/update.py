"""
更新数据库的操作都在这里。

【写操作后信号发射规范】
写操作完成后，调用方负责 emit 对应的 global_signals 全局信号（小驼峰命名）。
详见 docs/write_ops_signal_mapping.md 映射表。
"""

import logging
import random
import time
from collections.abc import Iterable

from utils.utils import translate_text_sync

from config import DATABASE
from .connection import get_connection
from sqlite3 import Cursor, IntegrityError
from .query.work import get_works_for_auto_cn_translation

# ----------------------------------------------------------------------------------------------------------
#                                               公共数据库的更新
# ----------------------------------------------------------------------------------------------------------


def update_tag_type(tag_type_data: list[dict]) -> bool:
    """更新tag_type。调用后需 emit: global_signals.tagDataChanged"""
    # 1.计算需要删除的部分然后删除
    # 获得当前所有的tag_type_id的集合
    conn = get_connection(DATABASE, False)
    cursor = conn.cursor()
    cursor.execute("SELECT tag_type_id FROM tag_type")
    existing_tag_type = {row[0] for row in cursor.fetchall()}
    # 比较现有的差距
    new_tag_type = set([data["tag_type_id"] for data in tag_type_data])
    delete_tag_type = existing_tag_type - new_tag_type
    logging.debug(f"要删除的tag_type_id{delete_tag_type}")

    try:
        for tag_type_id in delete_tag_type:
            cursor.execute("DELETE FROM tag_type WHERE tag_type_id=?", (tag_type_id,))
            # 现在没有外键会导致失误删除

        # 2.计算需要添加的部分然后添加
        # 要添加的就是tag_type_id为空的
        order = 1
        for data in tag_type_data:
            if not data.get("tag_type_id"):
                cursor.execute(
                    "INSERT INTO tag_type (tag_type_name,tag_order) VALUES(?,?)",
                    (data["tag_type_name"], order),
                )
                logging.debug(f"要添加的tag_type:{data["tag_type_name"]}")
            else:
                cursor.execute(
                    "UPDATE tag_type SET tag_type_name=?,tag_order=? Where tag_type_id=?",
                    (data["tag_type_name"], order, data["tag_type_id"]),
                )
            order += 1
        conn.commit()
        logging.debug("标签类型更新成功")
        return True
    except Exception as e:
        conn.rollback()
        logging.info(f"更新标签失败: {e}")
        return False
    finally:
        conn.close()


# 需要外键检查的
def UpdateWorkTags(work_id, new_tag_ids) -> bool:
    """更高效地更新作品标签关系（只删除不再需要的，只添加新的）。调用后需 emit: global_signals.workDataChanged"""
    try:
        conn = get_connection(DATABASE, False)
        cursor = conn.cursor()
        # 1. 获取现有的标签ID集合
        cursor.execute(
            "SELECT tag_id FROM work_tag_relation WHERE work_id = ?", (work_id,)
        )
        existing_tags = {row[0] for row in cursor.fetchall()}
        new_tags = set(new_tag_ids)

        # 2. 计算需要删除和需要添加的标签
        tags_to_remove = existing_tags - new_tags
        tags_to_add = new_tags - existing_tags

        # 3. 执行删除（只删除不再需要的）
        if tags_to_remove:
            placeholders = ",".join(["?"] * len(tags_to_remove))
            cursor.execute(
                f"DELETE FROM work_tag_relation WHERE work_id = ? AND tag_id IN ({placeholders})",
                (work_id, *tags_to_remove),
            )

        # 4. 执行添加（只添加新的）
        if tags_to_add:
            cursor.executemany(
                "INSERT INTO work_tag_relation (work_id, tag_id) VALUES (?, ?)",
                [(work_id, tag_id) for tag_id in tags_to_add],
            )

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logging.info(f"更新标签失败: {e}")
        return False
    finally:
        conn.close()


def _update_actor(cursor: Cursor, work_id: int, actor_ids: list):
    """更新作品的男优关系，传入一个cursor"""
    # 3. 更新男优----------------------------------------------------------------------------
    cursor.execute(
        "SELECT actor_id FROM work_actor_relation WHERE work_id = ?", (work_id,)
    )
    existing_actor = {row[0] for row in cursor.fetchall()}
    new_actor = set(actor_ids)

    #  计算需要删除和需要添加的男优
    actor_to_remove = existing_actor - new_actor
    actor_to_add = new_actor - existing_actor

    #  执行删除（只删除不再需要的）
    if actor_to_remove:
        placeholders = ",".join(["?"] * len(actor_to_remove))
        cursor.execute(
            f"DELETE FROM work_actor_relation WHERE work_id = ? AND actor_id IN ({placeholders})",
            (work_id, *actor_to_remove),
        )

    #  执行添加（只添加新的）
    if actor_to_add:
        cursor.executemany(
            "INSERT INTO work_actor_relation (work_id, actor_id) VALUES (?, ?)",
            [(work_id, tag_id) for tag_id in actor_to_add],
        )


def _update_actress(cursor: Cursor, work_id: int, actress_ids: list):
    # 2. 更新女优,用try包裹---------------------------------------------------------------------------------
    cursor.execute(
        "SELECT actress_id FROM work_actress_relation WHERE work_id = ?", (work_id,)
    )
    existing_actress = {row[0] for row in cursor.fetchall()}
    new_actress = set(actress_ids)

    #  计算需要删除和需要添加的女优
    actress_to_remove = existing_actress - new_actress
    actress_to_add = new_actress - existing_actress

    #  执行删除（只删除不再需要的）
    if actress_to_remove:
        placeholders = ",".join(["?"] * len(actress_to_remove))
        cursor.execute(
            f"DELETE FROM work_actress_relation WHERE work_id = ? AND actress_id IN ({placeholders})",
            (work_id, *actress_to_remove),
        )

    #  执行添加（只添加新的）
    if actress_to_add:
        cursor.executemany(
            "INSERT INTO work_actress_relation (work_id, actress_id) VALUES (?, ?)",
            [(work_id, tag_id) for tag_id in actress_to_add],
        )


def _update_worktag(cursor: Cursor, work_id: int, tag_ids: list):
    # 1. 更新tag
    cursor.execute("SELECT tag_id FROM work_tag_relation WHERE work_id = ?", (work_id,))
    existing_tags = {row[0] for row in cursor.fetchall()}
    new_tags = set(tag_ids)
    # 2. 计算需要删除和需要添加的标签
    tags_to_remove = existing_tags - new_tags
    tags_to_add = new_tags - existing_tags
    # 3. 执行删除（只删除不再需要的）
    if tags_to_remove:
        placeholders = ",".join(["?"] * len(tags_to_remove))
        cursor.execute(
            f"DELETE FROM work_tag_relation WHERE work_id = ? AND tag_id IN ({placeholders})",
            (work_id, *tags_to_remove),
        )
    # 4. 执行添加（只添加新的）
    if tags_to_add:
        cursor.executemany(
            "INSERT INTO work_tag_relation (work_id, tag_id) VALUES (?, ?)",
            [(work_id, tag_id) for tag_id in tags_to_add],
        )


def update_work_byhand(
    work_id,
    director,
    release_date,
    notes,
    runtime,
    actress_ids,
    actor_ids,
    cn_title,
    cn_story,
    jp_title,
    jp_story,
    image_url,
    tag_ids,
    maker_id,
    label_id,
    series_id,
    fanart=None,
) -> bool:
    """更新作品的信息，默认番号是不会出错的。调用后需 emit: global_signals.workDataChanged"""
    try:
        maker_id = int(maker_id) if maker_id not in (None, "") else None
        label_id = int(label_id) if label_id not in (None, "") else None
        series_id = int(series_id) if series_id not in (None, "") else None
        if maker_id is not None and maker_id <= 0:
            maker_id = None
        if label_id is not None and label_id <= 0:
            label_id = None
        if series_id is not None and series_id <= 0:
            series_id = None

        conn = get_connection(DATABASE, False)
        cursor: Cursor = conn.cursor()
        conn.execute("PRAGMA foreign_keys = ON")  # 打开外键约束
        # 1. 更新基本的信息
        cursor.execute(
            """
                        UPDATE work
                        SET director=?,
                        release_date=?,
                        notes=?,
                        runtime=?,
                        cn_title=?,
                        cn_story=?,
                        jp_title=?,
                        jp_story=?,
                        image_url=?,
                        maker_id=?,
                        label_id=?,
                        series_id=?,
                        fanart=?
                        WHERE work_id = ?
""",
            (
                director,
                release_date,
                notes,
                runtime,
                cn_title,
                cn_story,
                jp_title,
                jp_story,
                image_url,
                maker_id,
                label_id,
                series_id,
                fanart,
                work_id,
            ),
        )

        _update_actress(cursor, work_id, actress_ids)

        _update_actor(cursor, work_id, actor_ids)

        _update_worktag(cursor, work_id, tag_ids)

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logging.info(f"更新作品信息失败: {e}")
        return False
    finally:
        conn.close()


def update_work_byhand_(work_id: int, **fields) -> bool:
    """
    动态更新作品的信息，传入什么字段就更新什么字段,只能更新最基本的。
    例如：update_work_byhand(1, director="A", cn_title="标题")
    调用后需 emit: global_signals.workDataChanged
    """
    if not fields:
        return False  # 没有字段传入，不更新

    try:
        conn = get_connection(DATABASE, False)
        cursor = conn.cursor()
        conn.execute("PRAGMA foreign_keys = ON")  # 打开外键约束

        # 特殊处理 actress_ids
        if "actress_ids" in fields:
            actress_ids = fields.pop("actress_ids")  # 从 fields 中移除并获取值
            # 执行演员关联的更新逻辑
            _update_actress(cursor, work_id, actress_ids)

        if "actor_ids" in fields:
            actor_ids = fields.pop("actor_ids")  # 从 fields 中移除并获取值
            # 执行演员关联的更新逻辑
            _update_actor(cursor, work_id, actor_ids)

        if "tag_ids" in fields:
            tag_ids = fields.pop("tag_ids")  # 从 fields 中移除并获取值
            # 执行演员关联的更新逻辑
            _update_worktag(cursor, work_id, tag_ids)

        if not fields:
            conn.commit()
            return True  # 如果没有其他字段需要更新，直接提交并返回

        # 动态拼接 SET 子句
        set_clauses = []
        params = []
        for key, value in fields.items():
            set_clauses.append(f"{key}=?")
            params.append(value)

        sql = f"""
            UPDATE work
            SET {', '.join(set_clauses)}
            WHERE work_id=?
        """
        params.append(work_id)  # 最后加上 work_id

        cursor.execute(sql, params)
        conn.commit()
        return True

    except Exception as e:
        logging.warning(f"更新失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def update_work_actor(work_id: int, actor_ids: list) -> bool:
    """更新作品的男优关系。调用后需 emit: global_signals.workDataChanged"""
    try:
        conn = get_connection(DATABASE, False)
        cursor = conn.cursor()
        conn.execute("PRAGMA foreign_keys = ON")  # 打开外键约束
        _update_actor(cursor, work_id, actor_ids)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logging.info(f"更新作品信息失败: {e}")
        return False
    finally:
        conn.close()


# 不需要外键检查的


def check_workcover_integrity():
    """检查数据库中图片地址与实际位置的完整性

    文件夹中多出来的图片给删除
    文件夹中如果少了，也就是数据库中的image_url找不到指定的文件，把库中的相对位置给删除成NULL
    """
    return


def update_db_actress(id: int, data: dict):
    """更新女优名字，身材信息数据。调用后需 emit: global_signals.actressDataChanged"""

    conn = get_connection(DATABASE, False)
    logging.info("数据库打开成功")
    cursor = conn.cursor()

    try:
        logging.info(f"准备更新:{data},{id}")
        cursor.execute(
            "UPDATE actress SET birthday= ?,height = ?, bust = ?, waist = ?, hip = ?, cup = ?,debut_date=?,need_update=0 WHERE actress_id = ?",
            (
                data["出生日期"],
                data["身高"],
                data["胸围"],
                data["腰围"],
                data["臀围"],
                data["罩杯"],
                data["出道日期"],
                id,
            ),
        )

        # 更新英文名,假名；主日文名与站点不一致时同步为 data["日文名"]
        cursor.execute(
            "SELECT jp FROM actress_name WHERE actress_id=? AND name_type=1",
            (id,),
        )
        row_jp = cursor.fetchone()
        incoming_jp = data["日文名"]
        if row_jp is not None and row_jp[0] != incoming_jp:
            cursor.execute(
                "UPDATE actress_name SET cn=?,jp=? WHERE actress_id=? AND name_type=1",
                (incoming_jp, incoming_jp, id),
            )

        # 更新英文名,假名
        cursor.execute(
            "UPDATE actress_name SET en=?,kana=? WHERE actress_id=?",
            (data["英文名"], data["假名"], id),
        )

        conn.commit()
        logging.info("更新成功")
    except Exception as e:
        conn.rollback()
        logging.info("更新失败", e)
    finally:
        cursor.close()
        conn.close()
    return 0


def update_actress_image(id: int, image_url):
    """更新女优头像地址。调用后需 emit: global_signals.actressDataChanged"""

    conn = get_connection(DATABASE, False)
    logging.info("数据库打开成功")
    cursor = conn.cursor()

    try:
        logging.info("准备更新:%s,%s", image_url, id)
        cursor.execute(
            "UPDATE actress SET image_urlA=?,need_update=0 WHERE actress_id = ?",
            (image_url, id),
        )
        conn.commit()
        logging.info("更新成功")
    except Exception as e:
        conn.rollback()
        logging.info("更新失败", e)
    finally:
        cursor.close()
        conn.close()
    return 0


def update_actress_minnano_id(id, minnano_actress_id):
    """更新女优 minnano 信息。调用后需 emit: global_signals.actressDataChanged（若影响展示）"""
    conn = get_connection(DATABASE, False)
    logging.info("数据库打开成功")
    cursor = conn.cursor()

    try:
        logging.info("准备更新:%s,%s", minnano_actress_id, id)
        cursor.execute(
            "UPDATE actress SET minnano_url=?,need_update=0 WHERE actress_id = ?",
            (minnano_actress_id, id),
        )
        conn.commit()
        logging.info("更新成功")
    except Exception as e:
        conn.rollback()
        logging.info("更新失败", e)
    finally:
        cursor.close()
        conn.close()
    return 0


def update_work_javtxt(id, javtxt_id):
    """写入javtxt_id的缓存数据。通常无需 emit（内部缓存）"""
    conn = get_connection(DATABASE, False)
    logging.info("数据库打开成功")
    cursor = conn.cursor()

    try:
        logging.info("准备更新:%s,%s", javtxt_id, id)
        cursor.execute("UPDATE work SET javtxt_id=? WHERE work_id = ?", (javtxt_id, id))
        conn.commit()
        logging.info("更新成功")
    except Exception as e:
        conn.rollback()
        logging.info("更新失败", e)
    finally:
        cursor.close()
        conn.close()
    return 0


def _split_video_url_field(raw: str | None) -> list[str]:
    """按英文逗号拆分 video_url；strip 并丢弃空段。路径内若含逗号会被误切分（与存储约定一致）。"""
    if raw is None or not str(raw).strip():
        return []
    return [x.strip() for x in str(raw).split(",") if x.strip()]


def merge_work_video_urls_batch(work_id_to_paths: dict[int, list[str]]) -> int:
    """将本地视频绝对路径合并写入 work.video_url（逗号分隔、去重保序）。

    在已有内容上追加新路径；与合并后完全相同时跳过 UPDATE。
    成功后需由调用方 emit: global_signals.workDataChanged

    Args:
        work_id_to_paths: work_id -> 本轮扫描到的路径列表

    Returns:
        实际执行了 UPDATE 的 work 行数。
    """
    if not work_id_to_paths:
        return 0

    conn = get_connection(DATABASE, False)
    cursor = conn.cursor()
    n_updated = 0

    try:
        for work_id, path_list in work_id_to_paths.items():
            additions = [p.strip() for p in path_list if p and str(p).strip()]
            if not additions:
                continue

            cursor.execute(
                "SELECT video_url FROM work WHERE work_id = ?",
                (work_id,),
            )
            row = cursor.fetchone()
            if row is None:
                logging.warning(
                    "merge_work_video_urls_batch: work_id=%s 不存在，跳过", work_id
                )
                continue

            existing_parts = _split_video_url_field(row[0])
            merged: list[str] = []
            seen: set[str] = set()
            for x in existing_parts:
                if x not in seen:
                    merged.append(x)
                    seen.add(x)
            for x in additions:
                if x not in seen:
                    merged.append(x)
                    seen.add(x)

            new_val = ",".join(merged)
            old_val = ",".join(existing_parts)
            if new_val == old_val:
                continue

            cursor.execute(
                "UPDATE work SET video_url = ? WHERE work_id = ?",
                (new_val if new_val else None, work_id),
            )
            n_updated += 1

        conn.commit()
    except Exception as e:
        conn.rollback()
        logging.exception("merge_work_video_urls_batch 失败: %s", e)
        raise
    finally:
        cursor.close()
        conn.close()

    return n_updated


def replace_work_video_urls_batch(work_id_to_paths: dict[int, list[str]]) -> int:
    """用本次扫描结果完全覆盖 work.video_url（不保留库中原路径）。

    多条路径以英文逗号分隔，列表内去重保序；无有效路径时写入 NULL。
    与分割去空后拼回的值相同时跳过 UPDATE。
    成功后需由调用方 emit: global_signals.workDataChanged。

    Args:
        work_id_to_paths: work_id -> 本轮扫描到的路径列表

    Returns:
        实际执行了 UPDATE 的 work 行数。
    """
    if not work_id_to_paths:
        return 0

    conn = get_connection(DATABASE, False)
    cursor = conn.cursor()
    n_updated = 0

    try:
        for work_id, path_list in work_id_to_paths.items():
            parts = [p.strip() for p in path_list if p and str(p).strip()]
            merged: list[str] = []
            seen: set[str] = set()
            for x in parts:
                if x not in seen:
                    merged.append(x)
                    seen.add(x)

            new_val = ",".join(merged) if merged else None

            cursor.execute(
                "SELECT video_url FROM work WHERE work_id = ?",
                (work_id,),
            )
            row = cursor.fetchone()
            if row is None:
                logging.warning(
                    "replace_work_video_urls_batch: work_id=%s 不存在，跳过", work_id
                )
                continue

            old_parts = _split_video_url_field(row[0])
            old_val = ",".join(old_parts) if old_parts else None
            if old_val == new_val:
                continue

            cursor.execute(
                "UPDATE work SET video_url = ? WHERE work_id = ?",
                (new_val, work_id),
            )
            n_updated += 1

        conn.commit()
    except Exception as e:
        conn.rollback()
        logging.exception("replace_work_video_urls_batch 失败: %s", e)
        raise
    finally:
        cursor.close()
        conn.close()

    return n_updated


def update_titlestory(serial_number, cn_title, jp_title, cn_story, jp_story):
    """更新故事进去。调用后需 emit: global_signals.workDataChanged"""
    conn = get_connection(DATABASE, False)
    logging.info("数据库打开成功")
    cursor = conn.cursor()

    try:
        logging.info("准备更新:%s", serial_number)
        cursor.execute(
            "UPDATE work SET cn_title=?,jp_title=?,cn_story=?,jp_story==? WHERE serial_number = ?",
            (cn_title, jp_title, cn_story, jp_story, serial_number),
        )
        conn.commit()
        logging.info("更新成功")
    except Exception as e:
        conn.rollback()
        logging.info("更新失败", e)
    finally:
        cursor.close()
        conn.close()
    return 0


def update_tag_color(tag_ids: list, color):
    """更新tag的color。调用后需 emit: global_signals.tagDataChanged"""
    conn = get_connection(DATABASE, False)
    logging.info("数据库打开成功")
    cursor = conn.cursor()
    try:
        logging.info("准备更新:%s", tag_ids)
        cursor.executemany(
            "UPDATE tag SET color=? Where tag_id=?",
            [(color, tag_id) for tag_id in tag_ids],
        )
        conn.commit()
        logging.info("更新成功")
    except Exception as e:
        conn.rollback()
        logging.info("更新失败", e)
    finally:
        cursor.close()
        conn.close()
    return 0


def update_fanza_cover_url(work_id: int, fcover_url: str):
    """更新作品 FANZA 封面 URL。通常无需 emit（内部缓存）"""
    conn = get_connection(DATABASE, False)
    logging.info("数据库打开成功")
    cursor = conn.cursor()

    try:
        logging.info("准备更新:%s,%s", work_id, fcover_url)
        cursor.execute(
            "UPDATE work SET fcover_url=? WHERE work_id = ?", (fcover_url, work_id)
        )
        conn.commit()
        logging.info("更新成功")
    except Exception as e:
        conn.rollback()
        logging.info("更新失败", e)
    finally:
        cursor.close()
        conn.close()
    return 0


def update_on_dan(work_id: int, on_dan: int):
    """更新一部作品能否在avdan上找到。通常无需 emit（内部状态）"""
    conn = get_connection(DATABASE, False)
    logging.info("数据库打开成功")
    cursor = conn.cursor()

    try:
        logging.info("准备更新:%s,%s", work_id, on_dan)
        cursor.execute("UPDATE work SET on_dan=? WHERE work_id = ?", (on_dan, work_id))
        conn.commit()
        logging.info("更新成功")
    except Exception as e:
        conn.rollback()
        logging.info("更新失败", e)
    finally:
        cursor.close()
        conn.close()


def update_tag(
    tag_id: int,
    tag_name: str,
    tag_type_id: int,
    tag_color: str,
    tag_detail: str,
    tag_redirect_tag_id: int,
    tag_alias: list[dict],
) -> bool:
    """
    更新标签信息。调用后需 emit: global_signals.tagDataChanged
    参数示例:
            "tag_id": self._tag_id,
            "tag_name":self._tag_name,
            "tag_type":self._tag_type,
            "tag_color":self._tag_color,
            "tag_detail":self._tag_detail,
            "tag_redirect_tag_id":self._tag_redirect_tag_id
    """
    conn = get_connection(DATABASE, False)
    logging.info("数据库打开成功")
    cursor = conn.cursor()

    try:
        logging.info("准备更新:%s,%s", tag_id, tag_name)
        cursor.execute(
            "UPDATE tag SET tag_name=?,tag_type_id=?,color=?,detail=?,redirect_tag_id=? WHERE tag_id = ?",
            (tag_name, tag_type_id, tag_color, tag_detail, tag_redirect_tag_id, tag_id),
        )
        update_tag_alias(cursor, tag_alias, tag_id)
        conn.commit()
        logging.info("更新成功")
        return True
    except IntegrityError as e:
        if "UNIQUE constraint failed: tag.tag_name" in str(e):
            print(f"错误：标签名称 '{tag_name}' 已存在")
            # 标签已存在
        else:
            print(f"其他完整性错误: {e}")
        conn.rollback()
        return False
    except Exception as e:
        conn.rollback()
        logging.info(f"更新失败{e}")
        return False
    finally:
        cursor.close()
        conn.close()


def update_tag_alias(cursor: Cursor, tag_alias: list[dict], tag_id):
    """更新tag_alias"""
    # 先计算要删除的部分，然后计算添加的部分
    # 先取原来的
    cursor.execute(
        f"""
SELECT
    tag_id
FROM tag
WHERE redirect_tag_id=?""",
        (tag_id,),
    )
    existing_ids = {row[0] for row in cursor.fetchall()}
    existing_ids = set(existing_ids)
    logging.debug(existing_ids)
    new_ids = {name["tag_id"] for name in tag_alias if name["tag_id"] is not None}
    logging.debug(new_ids)
    delete_ids = existing_ids - new_ids
    logging.debug(delete_ids)
    # 3. 执行删除（只删除不再需要的）
    if delete_ids:
        placeholders = ",".join(["?"] * len(delete_ids))
        cursor.execute(
            f"DELETE FROM tag WHERE tag_id IN ({placeholders})", (*delete_ids,)
        )
    logging.debug("删除成功")
    # 修改与添加
    for tag in tag_alias:
        if tag["tag_id"] is None or tag["tag_id"] == "":  # 表明是新添加的
            cursor.execute(
                "INSERT INTO tag (tag_name,redirect_tag_id) VALUES (?,?)",
                (tag["tag_name"], tag_id),
            )
        else:  # 修改
            cursor.execute(
                "UPDATE tag SET tag_name=? WHERE tag_id=?",
                (tag["tag_name"], tag["tag_id"]),
            )


def mark_delete(work_id) -> bool:
    """将作品标记为已删除。调用后需 emit: global_signals.workDataChanged"""
    conn = get_connection(DATABASE, False)
    logging.info("数据库打开成功")
    cursor = conn.cursor()
    try:
        # logging.info("准备更新:%s,%s",work_id)
        cursor.execute("UPDATE work SET is_deleted=1 WHERE work_id = ?", (work_id,))
        conn.commit()
        logging.info("标记作品为删除状态")
        return True
    except Exception as e:
        conn.rollback()
        logging.info(f"标记作品为删除状态失败{e}")
        return False
    finally:
        cursor.close()
        conn.close()


_SQLITE_IN_MAX = 500


def mark_delete_many(work_ids: Iterable[int]) -> bool:
    """批量将作品标记为已删除（单次连接）。调用后需 emit: global_signals.workDataChanged"""
    ids = list({int(w) for w in work_ids})
    if not ids:
        return True
    conn = get_connection(DATABASE, False)
    logging.info("数据库打开成功")
    cursor = conn.cursor()
    try:
        for i in range(0, len(ids), _SQLITE_IN_MAX):
            chunk = ids[i : i + _SQLITE_IN_MAX]
            ph = ",".join("?" * len(chunk))
            cursor.execute(
                f"UPDATE work SET is_deleted=1 WHERE work_id IN ({ph})",
                chunk,
            )
        conn.commit()
        logging.info("批量标记作品为删除状态，共 %s 条", len(ids))
        return True
    except Exception as e:
        conn.rollback()
        logging.info("批量标记作品为删除状态失败%s", e)
        return False
    finally:
        cursor.close()
        conn.close()


def mark_undelete_many(work_ids: Iterable[int]) -> bool:
    """批量将作品标记为未删除（单次连接）。调用后需 emit: global_signals.workDataChanged"""
    ids = list({int(w) for w in work_ids})
    if not ids:
        return True
    conn = get_connection(DATABASE, False)
    logging.info("数据库打开成功")
    cursor = conn.cursor()
    try:
        for i in range(0, len(ids), _SQLITE_IN_MAX):
            chunk = ids[i : i + _SQLITE_IN_MAX]
            ph = ",".join("?" * len(chunk))
            cursor.execute(
                f"UPDATE work SET is_deleted=0 WHERE work_id IN ({ph})",
                chunk,
            )
        conn.commit()
        logging.info("批量标记作品为未删除状态，共 %s 条", len(ids))
        return True
    except Exception as e:
        conn.rollback()
        logging.info("批量标记作品为未删除状态失败%s", e)
        return False
    finally:
        cursor.close()
        conn.close()


def mark_undelete(work_id) -> bool:
    """将作品标记为未删除。调用后需 emit: global_signals.workDataChanged"""
    conn = get_connection(DATABASE, False)
    logging.info("数据库打开成功")
    cursor = conn.cursor()
    try:
        # logging.info("准备更新:%s,%s",work_id)
        cursor.execute("UPDATE work SET is_deleted=0 WHERE work_id = ?", (work_id,))
        conn.commit()
        logging.info("标记作品为未删除状态")
        return True
    except Exception as e:
        conn.rollback()
        logging.info(
            f"标记作品为未删除状态失败{e}",
        )
        return False
    finally:
        cursor.close()
        conn.close()


def update_actress_name(cursor: Cursor, actress_name: list[dict], actress_id) -> bool:
    """更新女优的名字"""
    # 先计算要删除的部分，然后计算添加的部分
    cursor.execute(
        "SELECT actress_name_id FROM actress_name WHERE actress_id = ?", (actress_id,)
    )
    existing_ids = {row[0] for row in cursor.fetchall()}
    existing_ids = set(existing_ids)
    new_ids = {
        name["actress_name_id"]
        for name in actress_name
        if name["actress_name_id"] is not None
    }
    delete_ids = existing_ids - new_ids
    print(delete_ids)
    # 外键全删除
    cursor.execute(
        "UPDATE actress_name SET redirect_actress_name_id = NULL WHERE actress_id = ?",
        (actress_id,),
    )
    print("外键清理成功")
    # 3. 执行删除（只删除不再需要的）
    if delete_ids:  # 这个删除的时候还有外键问题
        placeholders = ",".join(["?"] * len(delete_ids))
        cursor.execute(
            f"DELETE FROM actress_name WHERE actress_name_id IN ({placeholders})",
            (*delete_ids,),
        )
    # TODO
    print("删除成功")
    # 修改与添加
    for i, name_data in enumerate(actress_name):
        # 确定 name_type 和 redirect_id 的值
        # 假设 name_type 0 为主要名字，1为其他名字
        # 且 redirect_actress_name_id 指向上一条记录
        if i == 0:
            # 列表的第一条数据，name_type=1，redirect_id=None
            name_type = 1
            redirect_id = None
        else:
            # 后续数据，name_type=0，redirect_id指向上一条数据的ID
            name_type = 0
            redirect_id = last_id

        if name_data["actress_name_id"] is None or name_data["actress_name_id"] == "":
            # 插入新名字
            print(f"插入新名字{name_data['jp']}")
            cursor.execute(
                "INSERT INTO actress_name (actress_id, name_type, cn, jp, en, kana, redirect_actress_name_id) VALUES (?,?,?,?,?,?,?)",
                (
                    actress_id,
                    name_type,
                    name_data["cn"],
                    name_data["jp"],
                    name_data["en"],
                    name_data["kana"],
                    redirect_id,
                ),
            )
            print("插入新名字")
            last_id = cursor.lastrowid  # 更新上一条记录的ID

        else:
            # 修改已有的名字
            print(f"修改现有名字{name_data['jp']}")
            cursor.execute(
                "UPDATE actress_name SET name_type = ?, cn = ?, jp = ?, en = ?, kana = ?, redirect_actress_name_id = ? WHERE actress_name_id = ?",
                (
                    name_type,
                    name_data["cn"],
                    name_data["jp"],
                    name_data["en"],
                    name_data["kana"],
                    redirect_id,
                    name_data["actress_name_id"],
                ),
            )
            last_id = name_data["actress_name_id"]  # 更新上一条记录的ID


def update_actress_byhand(
    actress_id,
    height,
    cup,
    birthday,
    hip,
    waist,
    bust,
    debut_date,
    need_update,
    image_urlA,
    actress_name,
    minnano_url,
    notes="",
):
    """更新女优信息。调用后需 emit: global_signals.actressDataChanged
    参数示例: {
            "actress_id": self._actress_id,
            "height": self._height,
            "cup": self._cup,
            "birthday": self._birthday,
            "hip": self._hip,
            "waist": self._waist,
            "bust": self._bust,
            "debut_date": self._debut_date,
            "need_update": self._need_update,
            "image_urlA": self._image_urlA,
            "actress_name": self._actress_name,
            "minnano_url": self._minnano_url,
            "notes": self._notes
        }"""

    conn = get_connection(DATABASE, False)
    logging.info("数据库打开成功")
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE actress SET birthday=?,height=?,bust=?,waist=?,hip=?,cup=?,debut_date=?,need_update=?,image_urlA=?,minnano_url=?,notes=? WHERE actress_id=?",
            (
                birthday,
                height,
                bust,
                waist,
                hip,
                cup,
                debut_date,
                need_update,
                image_urlA,
                minnano_url,
                notes or "",
                actress_id,
            ),
        )

        # actress_name的修改部分
        update_actress_name(cursor, actress_name, actress_id)

        conn.commit()
        logging.info("更新成功")
        print("更新成功")
        return True

    except Exception as e:
        conn.rollback()
        logging.info(f"更新女优数据失败{e}")
        return False
    finally:
        cursor.close()
        conn.close()


def update_actor_byhand(actor_id, handsome, fat, image_url, actor_name, notes=""):
    """更新男优信息。调用后需 emit: global_signals.actorDataChanged"""

    conn = get_connection(DATABASE, False)
    logging.info("数据库打开成功")
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE actor SET handsome=?,fat=?,image_url=?,notes=? WHERE actor_id=?",
            (handsome, fat, image_url, notes or "", actor_id),
        )

        # actor_name的修改部分
        update_actor_name(cursor, actor_name, actor_id)

        conn.commit()
        logging.info("更新成功")
        print("更新成功")
        return True

    except Exception as e:
        conn.rollback()
        logging.info(f"更新男优数据失败{e}")
        return False
    finally:
        cursor.close()
        conn.close()


def update_actor_name(cursor: Cursor, actor_name: list[dict], actor_id) -> bool:
    """更新男优的名字"""
    # 先计算要删除的部分，然后计算添加的部分
    cursor.execute(
        "SELECT actor_name_id FROM actor_name WHERE actor_id = ?", (actor_id,)
    )
    existing_ids = {row[0] for row in cursor.fetchall()}
    existing_ids = set(existing_ids)
    new_ids = {
        name["actor_name_id"]
        for name in actor_name
        if name["actor_name_id"] is not None
    }
    delete_ids = existing_ids - new_ids
    print(delete_ids)

    # 3. 执行删除（只删除不再需要的）
    if delete_ids:  # 这个删除的时候还有外键问题
        placeholders = ",".join(["?"] * len(delete_ids))
        cursor.execute(
            f"DELETE FROM actor_name WHERE actor_name_id IN ({placeholders})",
            (*delete_ids,),
        )
    # TODO
    print("删除成功")
    # 修改与添加
    for i, name_data in enumerate(actor_name):
        # 确定 name_type 和 redirect_id 的值
        # 假设 name_type 0 为主要名字，1为其他名字
        # 且 redirect_actor_name_id 指向上一条记录
        if i == 0:
            # 列表的第一条数据，name_type=0
            name_type = 1
        else:
            # 后续数据，name_type=1
            name_type = 0

        if name_data["actor_name_id"] is None or name_data["actor_name_id"] == "":
            # 插入新名字
            print(f"插入新名字{name_data['jp']}")
            cursor.execute(
                "INSERT INTO actor_name (actor_id, name_type, cn, jp, en, kana) VALUES (?,?,?,?,?,?)",
                (
                    actor_id,
                    name_type,
                    name_data["cn"],
                    name_data["jp"],
                    name_data["en"],
                    name_data["kana"],
                ),
            )
            print("插入新名字")
        else:
            # 修改已有的名字
            print(f"修改现有名字{name_data['jp']}")
            cursor.execute(
                "UPDATE actor_name SET name_type = ?, cn = ?, jp = ?, en = ?, kana = ? WHERE actor_name_id = ?",
                (
                    name_type,
                    name_data["cn"],
                    name_data["jp"],
                    name_data["en"],
                    name_data["kana"],
                    name_data["actor_name_id"],
                ),
            )


def redirect_tag_121(tag_id0, tag_id1):
    """标签重定向,1对1。调用后需 emit: global_signals.tagDataChanged
    tag_id0是需要被删除的标签
    tag_id1是被指向的标签
    """
    conn = get_connection(DATABASE, False)
    logging.info("数据库打开成功")
    cursor = conn.cursor()
    try:
        # 1. 更新标签重定向指针
        cursor.execute(
            "UPDATE tag SET redirect_tag_id=? WHERE tag_id=?", (tag_id1, tag_id0)
        )
        # 2. 把旧的关联的tag也要重定向
        cursor.execute(
            "UPDATE tag SET redirect_tag_id=? WHERE redirect_tag_id=?",
            (tag_id1, tag_id0),
        )
        # 2. 迁移作品关联 (核心修改)
        # 将所有关联了旧标签的作品，赋予新标签。如果有冲突(已存在)，则忽略
        # 2. 先处理冲突：如果作品已经有了新标签，就直接删除旧标签记录（因为不需要合并了）
        cursor.execute(
            """
            DELETE FROM work_tag_relation 
            WHERE tag_id = ? 
            AND work_id IN (
                SELECT work_id FROM work_tag_relation WHERE tag_id = ?
            )
        """,
            (tag_id0, tag_id1),
        )

        # 3. 更新剩余记录：剩下的旧标签记录都可以安全地变更为新标签
        cursor.execute(
            "UPDATE work_tag_relation SET tag_id = ? WHERE tag_id = ?",
            (tag_id1, tag_id0),
        )
        conn.commit()
        logging.info("更新成功")
        print("更新成功")
        return True
    except Exception as e:
        conn.rollback()
        logging.info(f"更新标签数据失败{e}")
        return False
    finally:
        cursor.close()
        conn.close()


def _serial_prefix_for_maker_lookup(serial: str) -> str:
    """与视图一致：SUBSTR(serial, 1, INSTR(serial, '-') - 1)；无 '-' 时为空串。"""
    if serial is None:
        return ""
    s = str(serial).strip()
    if not s:
        return ""
    dash = s.find("-")
    if dash < 0:
        return ""
    return s[:dash]


def update_work_maker_from_prefix_relation() -> str:
    """按 prefix_maker_relation 更新 work.maker_id（番号为 serial_number，前缀为首个 '-' 之前段）。
    调用成功后需由调用方 emit: global_signals.workDataChanged
    """
    conn = get_connection(DATABASE, False)
    cursor = conn.cursor()
    skipped_same = 0
    skipped_no_rule = 0
    skipped_no_prefix = 0
    try:
        cursor.execute(
            "SELECT prefix, maker_id FROM prefix_maker_relation WHERE prefix IS NOT NULL AND TRIM(prefix) != ''"
        )
        prefix_to_maker: dict[str, int] = {}
        for pref, mid in cursor.fetchall():
            if mid is None:
                continue
            key = str(pref).strip()
            if not key:
                continue
            new_mid = int(mid)
            if key in prefix_to_maker and prefix_to_maker[key] != new_mid:
                logging.warning(
                    "prefix_maker_relation 前缀重复且 maker_id 不一致: prefix=%r 已有=%s 新=%s，采用后者",
                    key,
                    prefix_to_maker[key],
                    new_mid,
                )
            prefix_to_maker[key] = new_mid

        if not prefix_to_maker:
            return "prefix_maker_relation 为空，未执行更新"

        cursor.execute(
            """
            SELECT work_id, serial_number, maker_id
            FROM work
            WHERE IFNULL(is_deleted, 0) = 0
            """
        )
        updates: list[tuple[int, int]] = []
        for work_id, serial_number, cur_maker in cursor.fetchall():
            prefix = _serial_prefix_for_maker_lookup(serial_number)
            if not prefix:
                skipped_no_prefix += 1
                continue
            new_mid = prefix_to_maker.get(prefix)
            if new_mid is None:
                skipped_no_rule += 1
                continue
            cur_int = int(cur_maker) if cur_maker is not None else None
            if cur_int == new_mid:
                skipped_same += 1
                continue
            updates.append((new_mid, work_id))

        cursor.executemany(
            "UPDATE work SET maker_id = ? WHERE work_id = ?",
            updates,
        )
        updated = len(updates)

        conn.commit()
        return (
            f"已更新 {updated} 条作品的片商；"
            f"已匹配且相同 {skipped_same}；无此前缀规则 {skipped_no_rule}；"
            f"番号无前缀段 {skipped_no_prefix}"
        )
    except Exception as e:
        conn.rollback()
        logging.exception("按前缀更新片商失败: %s", e)
        raise
    finally:
        cursor.close()
        conn.close()


def batch_translate_missing_cn_fields() -> str:
    """
    后台批量翻译：jp_title→cn_title（缺省时）、jp_story→cn_story（缺省时）。
    若某行 jp_title 与 jp_story 均无有效日文，则不会选中；翻译失败则跳过该字段写入。
    调用后需 emit: global_signals.workDataChanged
    """
    rows = get_works_for_auto_cn_translation()
    if not rows:
        return "没有需要翻译的作品"

    rows_touched = 0
    n_cn_title = 0
    n_cn_story = 0

    for row in rows:
        work_id = row.get("work_id")
        if work_id is None:
            continue
        jp_t = (row.get("jp_title") or "").strip()
        jp_s = (row.get("jp_story") or "").strip()
        cn_t_existing = (row.get("cn_title") or "").strip()
        cn_s_existing = (row.get("cn_story") or "").strip()

        fields: dict[str, str] = {}
        if jp_t and not cn_t_existing:
            out = translate_text_sync(jp_t)
            if out:
                fields["cn_title"] = out
                n_cn_title += 1
        if jp_s and not cn_s_existing:
            out_s = translate_text_sync(jp_s)
            if out_s:
                fields["cn_story"] = out_s
                n_cn_story += 1

        if fields and update_work_byhand_(int(work_id), **fields):
            rows_touched += 1

        time.sleep(random.uniform(0.35, 0.9))

    return (
        f"共 {len(rows)} 条待处理，已写入 {rows_touched} 条作品；"
        f"补充 cn_title {n_cn_title} 项，cn_story {n_cn_story} 项"
    )


def normalize_work_cover_filenames_to_serial() -> str | None:
    """将 work.image_url 与 workcovers 下的封面文件统一为 ``{serial_number}.jpg``。

    按库中 ``image_url`` 相对路径在 ``WORKCOVER_PATH`` 下查找源文件，存在则重命名为
    根目录下的 ``{番号}.jpg`` 并写回 ``image_url``。目标路径已存在且与源不是同一文件
    时跳过，避免覆盖。

    Returns:
        结果摘要；发生意外时返回 ``None``。

    调用后需 emit: global_signals.workDataChanged
    """
    from pathlib import Path

    from config import WORKCOVER_PATH

    work_root = Path(WORKCOVER_PATH).resolve()
    query = """
    SELECT work_id, serial_number, image_url
    FROM work
    WHERE image_url IS NOT NULL AND TRIM(image_url) != ''
    """
    conn_read = get_connection(DATABASE, True)
    try:
        cursor = conn_read.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
    except Exception as e:
        logging.exception("读取 work 封面字段失败: %s", e)
        return None
    finally:
        conn_read.close()

    n_ok = 0
    n_db_only = 0
    n_skip_same = 0
    n_missing = 0
    n_conflict = 0
    n_no_serial = 0
    n_outside = 0
    n_rename_fail = 0

    conn = get_connection(DATABASE, False)
    cur = conn.cursor()
    try:
        for work_id, serial_number, image_url in rows:
            serial = str(serial_number or "").strip()
            if not serial:
                n_no_serial += 1
                continue
            raw = str(image_url or "").strip().replace("\\", "/")
            if not raw or raw in {".", ".."}:
                continue
            target_rel = f"{serial}.jpg"

            try:
                old_path = (Path(WORKCOVER_PATH) / raw).resolve()
            except (OSError, ValueError):
                n_missing += 1
                continue

            try:
                old_path.relative_to(work_root)
            except ValueError:
                n_outside += 1
                logging.warning(
                    "跳过 work_id=%s：封面路径不在 workcovers 内：%s",
                    work_id,
                    raw,
                )
                continue

            if not old_path.is_file():
                n_missing += 1
                continue

            try:
                new_path = (Path(WORKCOVER_PATH) / target_rel).resolve()
                new_path.relative_to(work_root)
            except ValueError:
                n_no_serial += 1
                continue

            if old_path == new_path:
                if raw != target_rel:
                    try:
                        cur.execute(
                            "UPDATE work SET image_url = ? WHERE work_id = ?",
                            (target_rel, work_id),
                        )
                        conn.commit()
                        n_db_only += 1
                    except Exception as e:
                        conn.rollback()
                        logging.warning(
                            "仅更新 image_url 失败 work_id=%s: %s", work_id, e
                        )
                else:
                    n_skip_same += 1
                continue

            if new_path.exists():
                n_conflict += 1
                logging.warning("跳过 work_id=%s：目标已存在 %s", work_id, target_rel)
                continue

            try:
                old_path.rename(new_path)
            except OSError as e:
                n_rename_fail += 1
                logging.warning(
                    "重命名失败 work_id=%s %s -> %s: %s",
                    work_id,
                    raw,
                    target_rel,
                    e,
                )
                continue

            try:
                cur.execute(
                    "UPDATE work SET image_url = ? WHERE work_id = ?",
                    (target_rel, work_id),
                )
                conn.commit()
                n_ok += 1
            except Exception as e:
                conn.rollback()
                logging.warning(
                    "更新 image_url 失败 work_id=%s，尝试回滚文件: %s",
                    work_id,
                    e,
                )
                try:
                    new_path.rename(old_path)
                except OSError as e2:
                    logging.error("回滚重命名失败：%s", e2)

        return (
            f"已重命名并写库 {n_ok} 条；仅纠正 image_url 字符串 {n_db_only} 条；"
            f"已是目标文件名跳过 {n_skip_same} 条；源文件缺失 {n_missing} 条；"
            f"目标已存在跳过 {n_conflict} 条；番号无效或路径越界 {n_no_serial + n_outside} 条；"
            f"重命名失败 {n_rename_fail} 条"
        )
    finally:
        cur.close()
        conn.close()
