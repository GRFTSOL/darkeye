"""
插入数据库的操作在这里。

【写操作后信号发射规范】
写操作完成后，调用方负责 emit 对应的 global_signals.*_changed 信号。
详见 docs/write_ops_signal_mapping.md 映射表。
"""

from sqlite3 import IntegrityError
from config import DATABASE, PRIVATE_DATABASE
import logging
from .connection import get_connection


def InsertNewActress(ch_name, jp_name) -> bool:
    """插入女优数据。调用后需 emit: global_signals.actressDataChanged"""
    conn = get_connection(DATABASE, False)
    cursor = conn.cursor()
    success = False
    try:
        cursor.execute("INSERT INTO actress DEFAULT VALUES")
        new_id = cursor.lastrowid

        # 添加中文日文名
        cursor.execute(
            "INSERT INTO actress_name (actress_id,name_type,cn,jp) VALUES(?,?,?,?)",
            (new_id, 1, ch_name, jp_name),
        )

        conn.commit()
        logging.info(f"新插入的 actress_id 是: {new_id}:日文名:{jp_name}")
        success = True
    except Exception as e:
        conn.rollback()
        logging.warning("插入失败:", e)
        success = False
    finally:
        cursor.close()
        conn.close()
    return success


def InsertNewActor(cn_name, jp_name) -> bool:
    """插入男优数据。调用后需 emit: global_signals.actorDataChanged"""
    conn = get_connection(DATABASE, False)
    cursor = conn.cursor()
    success = False
    try:
        # 添加中文日文名
        cursor.execute("INSERT INTO actor DEFAULT VALUES")
        new_id = cursor.lastrowid

        # 添加中文日文名
        cursor.execute(
            "INSERT INTO actor_name (actor_id,name_type,cn,jp) VALUES(?,?,?,?)",
            (new_id, 1, cn_name, jp_name),
        )
        conn.commit()

        logging.info(f"新插入的 actor_id 是: {new_id}:日文名:{jp_name}")
        success = True
    except Exception as e:
        conn.rollback()
        logging.warning("插入失败:", e)
        success = False
    finally:
        cursor.close()
        conn.close()
    return success


def InsertNewWork(serial_number: str) -> int:
    """添加新作品。调用后需 emit: global_signals.workDataChanged"""
    conn = get_connection(DATABASE, False)
    cursor = conn.cursor()
    success = False
    try:
        # 添加新作品
        cursor.execute("INSERT INTO work (serial_number) VALUES(?)", (serial_number,))
        new_id = cursor.lastrowid

        conn.commit()
        logging.info(f"新插入的 work_id 是: {new_id}")
        success = new_id
    except Exception as e:
        conn.rollback()
        logging.warning("插入失败:", e)
        return None
    finally:
        cursor.close()
        conn.close()

    return success


def InsertNewWorkByHand(
    serial_number,
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
    """手动添加新作品。调用后需 emit: global_signals.workDataChanged"""
    success = False
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
        cursor = conn.cursor()
        # 添加新作品（列顺序与表定义一致：runtime 后接 release_date）
        cursor.execute(
            """INSERT INTO work (serial_number,director,notes,runtime,release_date,cn_title,cn_story,jp_title,jp_story,image_url,maker_id,label_id,series_id,fanart)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                serial_number,
                director,
                notes,
                runtime,
                release_date,
                cn_title,
                cn_story,
                jp_title,
                jp_story,
                image_url,
                maker_id,
                label_id,
                series_id,
                fanart,
            ),
        )
        new_id = cursor.lastrowid
        for id in actress_ids:
            cursor.execute(
                "INSERT INTO work_actress_relation (work_id,actress_id) VALUES(?,?)",
                (new_id, id),
            )
        for id in actor_ids:
            cursor.execute(
                "INSERT INTO work_actor_relation (work_id,actor_id) VALUES(?,?)",
                (new_id, id),
            )
        for id in tag_ids:
            cursor.execute(
                "INSERT INTO work_tag_relation (work_id,tag_id) VALUES(?,?)",
                (new_id, id),
            )
        conn.commit()
        logging.info(f"新插入的 work_id 是: {new_id}")
        success = True
    except Exception as e:
        conn.rollback()
        logging.warning("插入失败:", e)
    finally:
        cursor.close()
        conn.close()
    return success


def insert_tag(
    tag_name: str,
    tag_type_id: int,
    tag_color: str,
    tag_detail: str,
    tag_redirect_tag_id: int,
    tag_alias: list[dict],
) -> tuple[bool, str, int | None]:
    """插入标签。调用后需 emit: global_signals.tagDataChanged"""
    success = False
    try:
        conn = get_connection(DATABASE, False)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tag (tag_name,tag_type_id,color,detail,redirect_tag_id) VALUES(?,?,?,?,?)",
            (tag_name, tag_type_id, tag_color, tag_detail, tag_redirect_tag_id),
        )
        new_id = cursor.lastrowid
        conn.commit()
        logging.info(f"新插入的 tag_id 是: {new_id}")
        return (True, "插入成功", new_id)

    except IntegrityError as e:
        if "UNIQUE constraint failed: tag.tag_name" in str(e):
            print(f"错误：标签名称 '{tag_name}' 已存在")
            # 标签已存在
            message = f"标签名称 '{tag_name}' 已存在"
        else:
            print(f"其他完整性错误: {e}")
        conn.rollback()
        return False, message, None

    except Exception as e:
        conn.rollback()
        logging.warning(f"插入失败:{e}")
        return False, str(e), None  # 将错误信息转换为字符串返回
    finally:
        cursor.close()
        conn.close()

    return success


def add_tag2work(work_id: int, tag_ids: list[int]) -> bool:
    """给作品添加标签,只添加没有的,是直写入数据库。调用后需 emit: global_signals.workDataChanged"""
    success = False
    try:
        conn = get_connection(DATABASE, False)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT tag_id FROM work_tag_relation WHERE work_id = ?", (work_id,)
        )
        existing_tags = {row[0] for row in cursor.fetchall()}
        new_tags = set(tag_ids)
        # 2. 计算需要需要添加的标签
        tags_to_add = new_tags - existing_tags
        print(f"要添加的新标签{tags_to_add}")
        # 4. 执行添加（只添加新的）
        if tags_to_add:
            cursor.executemany(
                "INSERT INTO work_tag_relation (work_id, tag_id) VALUES (?, ?)",
                [(work_id, tag_id) for tag_id in tags_to_add],
            )
        conn.commit()
        success = True
    except Exception as e:
        conn.rollback()
        logging.warning(f"插入失败:{e}")
    finally:
        cursor.close()
        conn.close()
    return success


def rename_save_image(_path: str, name: str, type: str):
    """将图片复制到库目录并按 name 保存为 jpg（webp/png 会转换）。

    _path：源文件绝对路径。源在配置项临时目录（TEMP_PATH）内时，成功后删除源文件；
    其它路径仅复制，不删除原文件。
    """
    from pathlib import Path
    from config import (
        WORKCOVER_PATH,
        FANART_PATH,
        ACTRESSIMAGES_PATH,
        ACTORIMAGES_PATH,
        TEMP_PATH,
    )
    from utils.utils import delete_image, webp_to_jpg_pillow, png_to_jpg_pillow
    import shutil

    if type == "cover":
        dst_path: Path = Path(WORKCOVER_PATH) / name
    elif type == "actress":
        dst_path: Path = Path(ACTRESSIMAGES_PATH) / name
    elif type == "actor":
        dst_path: Path = Path(ACTORIMAGES_PATH) / name
    elif type == "fanart":
        dst_path: Path = Path(FANART_PATH) / name
    else:
        logging.info("选择保存的类型错误")
        return

    # 检查源路径是否存在
    if not _path:
        return
    src_path = Path(_path)

    # 当源路径和目标路径相同时不操作
    if src_path.resolve() == dst_path.resolve():
        return

    dst_path.parent.mkdir(parents=True, exist_ok=True)

    match src_path.suffix.lower():
        case ".jpg" | ".jpeg":
            shutil.copy(src_path, dst_path)
        case ".webp":
            webp_to_jpg_pillow(src_path, dst_path)
        case ".png":
            png_to_jpg_pillow(src_path, dst_path)

    logging.info("图片复制成功，已保存位置为：%s", dst_path)

    # 仅删除临时目录内的源文件（如下载缓存）；库外路径只复制，保留原文件
    try:
        src_path.resolve().relative_to(Path(TEMP_PATH).resolve())
    except ValueError:
        pass
    else:
        delete_image(_path)


def InsertNewMaker(name: str) -> int | None:
    """插入新的片商,成功返回 maker_id，失败返回 None"""
    query = """
    INSERT INTO maker (cn_name, jp_name) VALUES (?, ?)
    """
    conn = get_connection(DATABASE, False)
    cursor = conn.cursor()
    try:
        cursor.execute(query, (name, name))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        conn.rollback()
        logging.warning("插入片商失败: %s", e)
        return None
    finally:
        cursor.close()
        conn.close()


def InsertNewLabel(name: str) -> int | None:
    """插入新的厂牌,成功返回 label_id，失败返回 None"""
    query = """
    INSERT INTO label (cn_name, jp_name) VALUES (?, ?)
    """
    conn = get_connection(DATABASE, False)
    cursor = conn.cursor()
    try:
        cursor.execute(query, (name, name))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        conn.rollback()
        logging.warning("插入厂牌失败: %s", e)
        return None
    finally:
        cursor.close()
        conn.close()


def InsertNewSeries(name: str) -> int | None:
    """插入新的系列,成功返回 series_id，失败返回 None"""
    query = """
    INSERT INTO series (cn_name, jp_name) VALUES (?, ?)
    """
    conn = get_connection(DATABASE, False)
    cursor = conn.cursor()
    try:
        cursor.execute(query, (name, name))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        conn.rollback()
        logging.warning("插入系列失败: %s", e)
        return None
    finally:
        cursor.close()
        conn.close()


# ----------------------------------------------------------------------------------------------------------
#                                      私有数据库的插入数据
# ----------------------------------------------------------------------------------------------------------


def insert_masturbation_record(
    work_id, serial_number, start_time, rating, tool_name, comment
) -> bool:
    """
    向自慰记录表 masturbation 插入一条新的记录。调用后需 emit: global_signals.masterbationChanged

    参数:
    - work_id: 关联作品的ID（整数）
    - start_time: 起飞时间，文本格式（如“YYYY-MM-DD HH:MM”）
    - rating: 满意度评分，整数，范围1-5
    - tool_name: 使用的工具名称（如“手”，“飞机杯”等）
    - comment: 对此次记录的备注或评论（文本）

    返回:
    - bool: 插入是否成功，True表示成功，False表示失败
    """
    success = False
    try:
        conn = get_connection(PRIVATE_DATABASE, False)
        cursor = conn.cursor()

        # 添加的自慰记录
        cursor.execute(
            "INSERT INTO masturbation (work_id,serial_number,start_time,tool_name,rating,comment) VALUES(?,?,?,?,?,?)",
            (work_id, serial_number, start_time, tool_name, rating, comment),
        )
        new_id = cursor.lastrowid
        conn.commit()
        logging.info(f"新插入的 masturbate_id 是: {new_id}")
        success = True
    except Exception as e:
        conn.rollback()
        logging.warning("插入失败:", e)
    finally:
        cursor.close()
        conn.close()

    return success


def insert_lovemaking_record(event_time, rating, comment) -> bool:
    """
    向做爱记录表 lovemaking 插入一条新的记录。调用后需 emit: global_signals.lovemakingChanged

    参数:
    - event_time: 做爱事件的时间，文本格式（如“YYYY-MM-DD HH:MM”）
    - rating: 满意度评分，整数，范围1-5
    - comment: 对此次做爱的备注或评价（文本）

    返回:
    - bool: 插入是否成功，True表示成功，False表示失败
    """
    success = False
    try:
        conn = get_connection(PRIVATE_DATABASE, False)
        cursor = conn.cursor()

        # 添加的自慰记录
        cursor.execute(
            "INSERT INTO love_making (event_time,rating,comment) VALUES(?,?,?)",
            (event_time, rating, comment),
        )
        new_id = cursor.lastrowid
        conn.commit()
        logging.info(f"新插入的 love_making_id 是: {new_id}")
        success = True
    except Exception as e:
        conn.rollback()
        logging.warning("插入失败:", e)
    finally:
        cursor.close()
        conn.close()

    return success


def insert_sexual_arousal_record(arousal_time, comment) -> bool:
    """
    向晨勃记录表 sexual_arousal 插入一条新的记录。调用后需 emit: global_signals.sexarousalChanged

    参数:
    - arousal_time: 晨勃时间，文本格式（如“YYYY-MM-DD HH:MM”）
    - comment: 对此次晨勃的备注或梦境描述（文本）

    返回:
    - bool: 插入是否成功，True表示成功，False表示失败
    """
    success = False
    try:
        conn = get_connection(PRIVATE_DATABASE, False)
        cursor = conn.cursor()

        # 添加的自慰记录
        cursor.execute(
            "INSERT INTO sexual_arousal (arousal_time,comment) VALUES(?,?)",
            (arousal_time, comment),
        )
        new_id = cursor.lastrowid
        conn.commit()
        logging.info(f"新插入的 sexual_arousal_id 是: {new_id}")
        success = True
    except Exception as e:
        conn.rollback()
        logging.warning("插入失败:", e)
    finally:
        cursor.close()
        conn.close()

    return success


def insert_liked_actress(actress_id) -> bool:
    """向私库中添加喜欢的女优。调用后需 emit: global_signals.likeActressChanged"""
    from .db_utils import attach_private_db, detach_private_db

    success = False
    try:
        # 先查询后添加
        conn = get_connection(DATABASE, False)
        cursor = conn.cursor()
        query = """
SELECT 
(SELECT jp FROM actress_name WHERE actress_id=actress.actress_id AND redirect_actress_name_id is NULL)AS jp_name
FROM actress 
WHERE actress_id=?
"""
        cursor.execute(query, (actress_id,))
        jp_name = cursor.fetchone()[0]

        attach_private_db(cursor)

        cursor.execute(
            "INSERT INTO priv.favorite_actress (actress_id,jp_name) VALUES(?,?)",
            (actress_id, jp_name),
        )
        new_id = cursor.lastrowid
        conn.commit()
        logging.info(f"新插入的 favorite_actress_id 是: {new_id}")
        success = True
    except Exception as e:
        conn.rollback()
        logging.warning("插入失败:", e)
    finally:
        detach_private_db(cursor)
        cursor.close()
        conn.close()

    return success


def insert_liked_work(work_id) -> bool:
    """向私库中添加喜欢的作品。调用后需 emit: global_signals.likeWorkChanged"""
    from .db_utils import attach_private_db, detach_private_db

    success = False
    try:
        # 先查询后添加
        conn = get_connection(DATABASE, False)
        cursor = conn.cursor()
        query = """
SELECT 
serial_number
FROM work 
WHERE work_id=?
"""
        cursor.execute(query, (work_id,))
        serial_number = cursor.fetchone()[0]

        attach_private_db(cursor)

        cursor.execute(
            "INSERT INTO priv.favorite_work (work_id,serial_number) VALUES(?,?)",
            (work_id, serial_number),
        )
        new_id = cursor.lastrowid
        conn.commit()
        logging.info(f"新插入的 favorite_work_id 是: {new_id}")
        success = True
    except Exception as e:
        conn.rollback()
        logging.warning("插入失败:", e)
    finally:
        detach_private_db(cursor)
        cursor.close()
        conn.close()

    return success


def InsertAliasName(id, alias_chain: list[dict]) -> bool:
    """插入女优别名链。调用后需 emit: global_signals.actressDataChanged"""
    conn = get_connection(DATABASE, False)
    cursor = conn.cursor()
    success = False
    try:
        cursor.execute(
            "SELECT actress_name_id FROM actress_name WHERE actress_id=?", (id,)
        )
        cur_id = cursor.fetchone()[0]

        for alias in reversed(alias_chain):
            print(alias)
            # 添加中文日文名
            cursor.execute(
                "INSERT INTO actress_name (actress_id,jp,kana,en,redirect_actress_name_id) VALUES(?,?,?,?,?)",
                (id, alias["jp"], alias["kana"], alias["en"], cur_id),
            )
            cur_id = cursor.lastrowid

        conn.commit()
        logging.info(f"")
        success = True
    except Exception as e:
        conn.rollback()
        logging.warning("插入失败:", e)
        success = False
    finally:
        cursor.close()
        conn.close()
    return success
