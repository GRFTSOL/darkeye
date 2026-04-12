import logging

from core.crawler.jump import fetch_top_actresses_via_api

"""需要非日本ip才能爬"""


def apply_javtxt_top_actress_names(names: list[str]) -> bool:
    """将 javtxt 热门女优名列表写入数据库（仅处理前 50 条）。"""
    from core.database.insert import InsertNewActress
    from core.database.query import exist_actress
    from controller.global_signal_bus import global_signals

    logging.info("获取到热门女优 %s", names[:50])
    any_inserted = False
    for actress in names[:50]:
        actress = actress.replace("卜", "ト")
        if not exist_actress(actress):
            if InsertNewActress(actress, actress):
                logging.info("添加热门女优%s", actress)
                any_inserted = True
        else:
            logging.info("热门女优%s已存在", actress)
    if any_inserted:
        global_signals.actressDataChanged.emit()
    return True


def top_actresses() -> bool:
    """经本地 HTTP GET /api/v1/top-actresses 由 Firefox 插件解析 javtxt 热门页，再写库。"""
    payload = fetch_top_actresses_via_api()
    if not isinstance(payload, dict):
        logging.error("javtxt 热门女优：无效响应")
        return False
    ok = bool(payload.get("ok"))
    names = payload.get("names")
    if not isinstance(names, list):
        names = []
    err = payload.get("error")
    if ok and not names:
        logging.warning("javtxt 热门女优：解析成功但未得到任何名称")
        ok = False
    if ok and names:
        apply_javtxt_top_actress_names(names)
        return True
    logging.warning(
        "javtxt 热门女优失败: %s",
        err if err else "unknown",
    )
    return False
