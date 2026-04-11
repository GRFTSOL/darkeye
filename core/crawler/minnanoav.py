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

def handle_minnano_persist_capture_from_extension(body: dict) -> None:
    """主窗口统一处理：persist 回传写库；失败仅 debug，不打断批量静默."""
    if not body:
        return
    ctx = body.get("context") or {}
    if not ctx.get("persist"):
        return
    if body.get("error"):
        logging.debug(
            "minnano persist capture error actress_id=%s err=%s",
            ctx.get("actress_id"),
            body.get("error"),
        )
        return
    raw = body.get("data")
    if not raw:
        return
    aid = ctx.get("actress_id")
    if aid is None:
        return
    try:
        actress_id = int(aid)
    except (TypeError, ValueError):
        logging.debug("minnano persist: invalid actress_id %r", aid)
        return
    try:
        data = normalize_minnano_extension_payload(dict(raw))
        persist_minnano_scrape_to_db(actress_id, data)
    except Exception:
        logging.exception("persist minnano from extension (global)")
        return
    from controller.global_signal_bus import global_signals

    global_signals.actressDataChanged.emit()

def SearchActressInfo_js() -> str:
    """需更新的女优逐条静默下发浏览器插件；落库依赖插件 persist 回传."""
    from core.crawler.jump import send_minnano_actress_crawler_request
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
    for i, row in enumerate(result):
        name = row["jp_name"]
        actress_id = row["actress_id"]
        minnano_url = exist_minnao_id(actress_id)
        send_minnano_actress_crawler_request(name, actress_id, minnano_url, silent=True)
        if i != total_rows - 1:
            time.sleep(random.uniform(5, 10))
    return f"已向浏览器下发 {total_rows} 项 minnano 更新任务"


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
    """将 minnano 解析结果写入数据库（与 SearchSingleActressInfo 成功分支一致）。
    这个就是直接写入数据库
    """
    from core.database.insert import InsertAliasNameReplace

    update_db_actress(actress_id, new_data)
    InsertAliasNameReplace(actress_id, new_data["alias_chain"])
    download_update_profile(actress_id, new_data)
    update_actress_minnano_id(actress_id, new_data["minnano_actress_id"])

