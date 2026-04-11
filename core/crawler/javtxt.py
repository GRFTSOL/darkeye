import logging
import re
import threading

import requests
from bs4 import BeautifulSoup

from core.database.query import (
    get_javtxt_id_by_serialnumber,
    get_workid_by_serialnumber,
)
from core.database.update import update_work_javtxt
from core.crawler.jump import send_crawler_request
from server.bridge import bridge
from utils.utils import serial_number_equal



"""需要非日本ip才能爬"""




def fetch_javtxt_movie_info_via_js(serial_number: str) -> dict:
    """
    由浏览器插件在页面内爬取（同步阻塞）。
    """
    pass



def apply_javtxt_top_actress_names(names: list[str]) -> bool:
    """将 javtxt 热门女优名列表写入数据库（仅处理前 50 条）。"""
    from core.database.insert import InsertNewActress
    from core.database.query import exist_actress
    from controller.global_signal_bus import global_signals

    logging.info("获取到热门女优 %s", names[:50])
    for actress in names[:50]:
        actress = actress.replace("卜", "ト")
        if not exist_actress(actress):
            if InsertNewActress(actress, actress):
                logging.info("添加热门女优%s", actress)
            global_signals.actressDataChanged.emit()
        else:
            logging.info("热门女优%s已存在", actress)
    return True


def top_actresses() -> bool:
    """由浏览器插件打开 javtxt 热门页并解析 DOM，再写库。"""
    event = threading.Event()
    result_holder: dict = {"ok": False}

    def on_done(payload: object) -> None:
        if not isinstance(payload, dict):
            event.set()
            return
        ok = bool(payload.get("ok"))
        names = payload.get("names")
        if not isinstance(names, list):
            names = []
        err = payload.get("error")
        if ok and not names:
            logging.warning("javtxt 热门女优：解析成功但未得到任何名称")
            ok = False
        result_holder["ok"] = ok
        if ok and names:
            apply_javtxt_top_actress_names(names)
        elif not ok:
            logging.warning(
                "javtxt 热门女优插件失败: %s",
                err if err else "unknown",
            )
        event.set()

    bridge.javtxtTopActressesFinished.connect(on_done)
    try:
        if not send_crawler_request("javtxt-top-actresses", ""):
            logging.error("发送热门女优爬虫指令失败（插件未连接或无 SSE 客户端）")
            return False
        if not event.wait(timeout=90):
            logging.error("javtxt 热门女优解析超时")
            return False
        return bool(result_holder.get("ok"))
    finally:
        try:
            bridge.javtxtTopActressesFinished.disconnect(on_done)
        except Exception as e:
            logging.debug(
                "top_actresses: 断开 javtxtTopActressesFinished 失败: %s",
                e,
                exc_info=True,
            )
