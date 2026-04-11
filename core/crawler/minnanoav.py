# 根据数据库中的日文名信息，到https://www.minnano-av.com/网站上去爬女优的数据包括身材，出道年份，等等。

# 如何维护女优的名字是一个很麻烦的问题，现用名，曾用名，然后数据与网站上不一致如何更新？
import random
import time
import re
import requests
from bs4 import BeautifulSoup
import sqlite3
import logging
from config import DATABASE, ACTRESSIMAGES_PATH
from core.database.update import (
    update_db_actress,
    update_actress_image,
    update_actress_minnano_id,
)
from pathlib import Path
from core.crawler.download import download_image_js


# 测试情况英文名的都有问题，日向なつ，杏奈，高瀬りな,白石もも重名问题
# 有年份内的重名问题，这个问题可以通过哪年出道的数据来解决


def actress_need_update() -> bool:
    """判断女优数据库是否需要更新"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    query = """
    SELECT "女优ID","日文名",need_update 
    FROM v_actress_all_info
    WHERE need_update=1
    """
    cursor.execute(query)
    result = cursor.fetchall()

    cursor.close()
    conn.close()
    if not result or all(not item for item in result):
        return False
    else:
        return True


def persist_actress_if_minnano_api_ok(actress_id: int, payload: dict) -> bool:
    """``fetch_actress_minnano_via_api`` 返回体：成功且含 ``data`` 时写入数据库。"""
    if not payload.get("ok") or not payload.get("data"):
        return False
    raw = payload.get("data")
    if not isinstance(raw, dict):
        return False
    try:
        data = normalize_minnano_extension_payload(dict(raw))
        persist_minnano_scrape_to_db(actress_id, data)
    except Exception:
        logging.exception("persist_actress_if_minnano_api_ok actress_id=%s", actress_id)
        return False
    return True


def fetch_actress_minnano_for_edit_worker(
    jp: str,
    actress_id: int,
    minnano_url_fragment: str | None,
) -> tuple[str, dict]:
    """供 QThreadPool：仅 GET 女优 API，不写库。

    成功返回 ``("data", payload)``，否则 ``("error", payload)``。
    """
    from core.crawler.jump import fetch_actress_minnano_via_api

    _ = actress_id  # 保留签名与调用方一致，便于与 persist 版 worker 互换
    mid = (minnano_url_fragment or "").strip() or None
    payload = fetch_actress_minnano_via_api(jp, minnano_url=mid)
    if not payload.get("ok"):
        return ("error", payload)
    if not payload.get("data"):
        merged = dict(payload) if isinstance(payload, dict) else {}
        merged.setdefault("error", "no_data")
        return ("error", merged)
    return ("data", payload)


def fetch_and_persist_actress_minnano_worker(
    jp: str,
    actress_id: int,
    minnano_url_fragment: str | None,
) -> tuple[str, dict]:
    """供 QThreadPool：GET 女优 API + DB 队列写库。返回 ``(kind, payload)``。"""
    from core.crawler.jump import fetch_actress_minnano_via_api
    from core.database.db_queue import submit_db_raw

    mid = (minnano_url_fragment or "").strip() or None
    payload = fetch_actress_minnano_via_api(jp, minnano_url=mid)
    if not payload.get("ok"):
        return ("error", payload)

    def _do() -> bool:
        return persist_actress_if_minnano_api_ok(actress_id, payload)

    if submit_db_raw(_do).result():
        return ("success", payload)
    return ("persist_failed", payload)


def normalize_minnano_extension_payload(data: dict) -> dict:
    """插件 JSON 与 persist 写库共用的数值字段规范化。"""
    out = dict(data)
    for key in ("身高", "胸围", "腰围", "臀围"):
        if key in out:
            try:
                out[key] = int(out[key] or 0)
            except (TypeError, ValueError):
                out[key] = 0
    return out


def SearchActressInfo_js():
    """批量：need_update 女优逐条 GET /api/v1/actress/ 同步拉取并写库。

    返回提示字符串，或 ``(msg, any_persisted)`` 元组。
    """
    from core.crawler.jump import fetch_actress_minnano_via_api
    from core.database.db_queue import submit_db_raw
    from core.database.query import exist_minnao_id

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    query = """
    SELECT "女优ID","日文名",need_update
    FROM v_actress_all_info
    WHERE need_update=1
    """
    cursor.execute(query)
    tuple_list = cursor.fetchall()
    cursor.close()
    conn.close()

    result = [
        {"actress_id": a, "jp_name": b, "need_update": c} for a, b, c in tuple_list
    ]
    if not tuple_list or all(not item for item in tuple_list):
        return "无需要更新数据的女优"
    total_rows = len(result)
    ok_count = 0
    for i, row in enumerate(result):
        name = row["jp_name"]
        actress_id = row["actress_id"]
        raw_mid = exist_minnao_id(actress_id)
        mid = (
            str(raw_mid).strip()
            if raw_mid is not None and str(raw_mid).strip()
            else None
        )
        payload = fetch_actress_minnano_via_api(name, minnano_url=mid)
        if not payload.get("ok"):
            logging.debug(
                "SearchActressInfo_js: actress_id=%s err=%s",
                actress_id,
                payload.get("error"),
            )
        else:

            def _do(aid=actress_id, pl=payload):
                return persist_actress_if_minnano_api_ok(aid, pl)

            try:
                if submit_db_raw(_do).result():
                    ok_count += 1
            except Exception:
                logging.exception(
                    "SearchActressInfo_js persist actress_id=%s", actress_id
                )
        if i != total_rows - 1:
            time.sleep(random.uniform(5, 10))
    return (
        f"已处理 {total_rows} 条 minnano 同步，写库成功 {ok_count} 条。",
        ok_count > 0,
    )


def _local_actress_avatar_file_is_valid(path: str) -> bool:
    """校验本地文件是否为可读位图。

    插件按 URL 保存的内容可能是 HTML/错误页；download_image_js 仍会复制成功，
    若不校验会误把相对路径写入 image_urlA。
    """
    try:
        from PIL import Image

        with Image.open(path) as im:
            im.load()
            return im.width >= 2 and im.height >= 2
    except Exception:
        return False


def download_update_profile(id, data: dict):
    """下载女优的头像，并更新数据库
    输入的数据是这样的
        new_data={
    "日文名":str(jp_name),
    "假名":str(kana),
    "英文名":str(romaji),
    "出生日期": str(birth_date),
    "身高": int(height),
    "罩杯": str(cup),
    "胸围": int(bust),
    "腰围": int(waist),
    "臀围": int(hip),
    "出道日期": str(debut_date),
    "头像地址": full_img_src
    }
    """

    raw_url = (data.get("头像地址") or "").strip()
    if not raw_url:
        logging.debug("女优头像 URL 为空，跳过下载 actress_id=%s", id)
        return

    image_urlA = str(str(id) + "-" + data["日文名"] + ".jpg")  # 存数据库里的相对地址
    image_path = Path(ACTRESSIMAGES_PATH / image_urlA)  # 实际要下载地址
    ok, err = download_image_js(raw_url, str(image_path))
    if not ok:
        logging.warning("女优头像下载失败 actress_id=%s err=%s", id, err)
        return
    if not _local_actress_avatar_file_is_valid(str(image_path)):
        logging.warning(
            "女优头像文件无效（非可用图片），不写入 image_urlA actress_id=%s path=%s",
            id,
            image_path,
        )
        try:
            image_path.unlink(missing_ok=True)
        except OSError:
            pass
        return
    update_actress_image(id, image_urlA)  # 写入数据库


def persist_minnano_scrape_to_db(actress_id: int, new_data: dict) -> None:
    """将 minnano 解析结果写入数据库（批量同步 / 内部持久化用）。"""
    from core.database.insert import InsertAliasNameReplace

    update_db_actress(actress_id, new_data)
    InsertAliasNameReplace(actress_id, new_data["alias_chain"])
    download_update_profile(actress_id, new_data)
    update_actress_minnano_id(actress_id, new_data["minnano_actress_id"])
