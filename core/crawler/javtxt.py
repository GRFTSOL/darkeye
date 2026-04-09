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

from .basic import fetch_url

"""需要非日本ip才能爬"""


def search_work(serial_number) -> str | None:
    """返回真实目标页面"""
    base = "https://javtxt.com/search?type=id&q="

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    url = base + serial_number  # 这里要调成标准模式
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.exceptions.RequestException as e:
        logging.error(f"请求javatxt {url} 时出错: {e}")
        return None

    if response.status_code == 200:  # 判断请求成功
        logging.info("-----请求成功-----")
        soup = BeautifulSoup(response.text, "html.parser")
        work_link = soup.find("a", class_="work")
        if work_link:  # 确保找到元素
            href_value = work_link.get("href")  # 提取 href 属性
            # logging.info(href_value)
        else:
            logging.info("未找到符合条件的元素")
        # 验证元素
        work_id_link = soup.find("h4", class_="work-id")
        if work_id_link:
            target_work_id = work_id_link.text
            if serial_number_equal(target_work_id, serial_number):  # 验证是一个番号
                return href_value
        return None
    else:
        logging.info("-----请求失败-----")
        logging.info(response.status_code)
        return None


def _dt_link_or_text(dt) -> str:
    """属性区 dt：优先取首个链接文本，否则取 dt 全部文本。"""
    if dt is None:
        return "----"
    a = dt.find("a")
    if a:
        return a.get_text(strip=True)
    return dt.get_text(strip=True)


def _parse_javtxt_attributes(soup: BeautifulSoup) -> dict:
    """解析详情页 ``div.attributes`` 下 ``dl`` 的 dd/dt 键值对。"""
    out: dict = {
        "release_date": "",
        "series": "",
        "maker": "",
        "director": "",
        "label": "",
        "genre": [],
    }
    dl = soup.select_one("div.attributes dl")
    if not dl:
        return out

    for dd in dl.find_all("dd"):
        dt = dd.find_next_sibling("dt")
        if not dt:
            continue
        key = dd.get_text(" ", strip=True)
        if "发行时间" in key:
            raw = dt.get_text(strip=True)
            m = re.search(r"\d{4}-\d{2}-\d{2}", raw)
            out["release_date"] = m.group(0) if m else raw
        elif "系列" in key:
            out["series"] = _dt_link_or_text(dt)
        elif "片商" in key:
            out["maker"] = _dt_link_or_text(dt)
        elif "导演" in key:
            out["director"] = _dt_link_or_text(dt)
        elif "厂牌" in key:
            out["label"] = _dt_link_or_text(dt)
        elif "类别" in key:
            out["genre"] = [
                a.get_text(strip=True)
                for a in dt.select("a.tag")
                if a.get_text(strip=True)
            ]

    return out


def scrape_javtxt_movie_details(url: str) -> dict:
    """
    从 JAVTXT 网站抓取电影详细信息。

    Args:
        url (str): 要抓取的 JAVTXT 电影详情页 URL

    Returns:
        dict: 包含电影信息的字典，字段包括
            cn_title, jp_title, cn_story, jp_story；
            以及属性区解析得到的 release_date, series, maker,
            director, label, genre（列表）。
            请求失败时返回空字典。
    """

    # 设置请求头
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.exceptions.RequestException as e:
        logging.error(f"请求javatxt {url} 时出错: {e}")
        return {}
    if response.status_code == 200:  # 判断请求成功
        logging.info("-----javtxt请求成功-----")
        # 解析页面
        soup = BeautifulSoup(response.text, "html.parser")
        jp_title = ""
        cn_title = ""
        cn_story = ""
        jp_story = ""
        jp_title_link = soup.find("h1", class_="title is-4 text-jp")
        cn_title_link = soup.find("h2", class_="title is-4 text-zh")

        if jp_title_link:
            jp_title = jp_title_link.text
            # logging.debug(jp_title)
        if cn_title_link:
            cn_title = cn_title_link.text
            # logging.debug(cn_title)

        jp_story_link = soup.find("p", class_="text-jp")
        if jp_story_link:
            jp_story = jp_story_link.text
            # logging.debug(jp_story)
        cn_story_link = soup.find("div", class_="text-zh")
        if cn_story_link:
            cn_p = cn_story_link.find("p")
            if cn_p:
                cn_story = cn_p.text
                # logging.debug(cn_story)

        attrs = _parse_javtxt_attributes(soup)
        data = {
            "cn_title": cn_title,
            "jp_title": jp_title,
            "cn_story": cn_story,
            "jp_story": jp_story,
            "release_date": attrs["release_date"],
            "series": attrs["series"],
            "maker": attrs["maker"],
            "director": attrs["director"],
            "label": attrs["label"],
            "genre": attrs["genre"],
        }

        return data
    else:
        logging.warning("-----javtxt请求失败,状态码%s-----", response.status_code)
        return {}


def jump_to_javtxt(serial_number: str) -> dict:
    """由浏览器插件在页面内爬取（同步阻塞），逻辑与 jump_to_javdb 一致。"""
    event = threading.Event()
    result_container: dict = {"data": {}}

    def temp_callback(data: dict) -> None:
        if serial_number_equal(data.get("id", ""), serial_number):
            result_container["data"] = data
            event.set()

    bridge.javtxtFinished.connect(temp_callback)
    try:
        send_crawler_request("javtxt", serial_number)
        is_set = event.wait(timeout=20)
        if not is_set:
            logging.info("Error: JavTxt crawl timeout for %s", serial_number)
            return {}
        return result_container["data"]
    finally:
        try:
            bridge.javtxtFinished.disconnect(temp_callback)
        except Exception as e:
            logging.debug(
                "jump_to_javtxt: 断开临时回调失败（可能未连接）: %s",
                e,
                exc_info=True,
            )


def fetch_javtxt_movie_info_via_http(serial_number: str) -> dict:
    """
    无缓存 HTTP：搜索番号后抓取详情（不经过浏览器插件）。
    供批量脚本等无插件环境使用。
    """
    truepage = search_work(serial_number)
    if truepage is None:
        logging.info("Javtxt HTTP：搜不到番号，结束")
        return {}
    base = "https://javtxt.com"
    url = base + truepage
    logging.info("请求 javtxt URL: %s", url)
    return scrape_javtxt_movie_details(url)


def fetch_javtxt_movie_info(serial_number: str) -> dict:
    """
    根据番号获取 JAVTXT 网站上的电影详细信息（带缓存机制）。
        # 标记非正规作品，非正规作品是没有封面，导演，故事等等的
    流程：
    1. 先检查本地是否有该番号对应的 JAVTXT ID 缓存
    2. 若无缓存则进行搜索获取 ID
    3. 使用 ID 构建最终 URL 并抓取详细信息

    Args:
        serial_number (str): 影片番号(如 ABP-123)

    Returns:
        dict: 包含电影信息的字典，结构同 scrape_javtxt_movie_details()；
            获取失败则返回空字典。
    """
    javtxt_id = get_javtxt_id_by_serialnumber(serial_number)
    if javtxt_id is None:  # 先查有无缓存
        truepage = search_work(serial_number)
        if truepage is None:
            logging.info("Javtxt_id无缓而且搜不到,结束")
            return {}
        javtxt_id = truepage.split("/")[-1]
        work_id = get_workid_by_serialnumber(serial_number)
        logging.info(
            "获取到新JAVTXT ID: %s并写入本地缓存，work_id:%s",
            javtxt_id,
            work_id,
        )
        if work_id is not None:
            update_work_javtxt(work_id, javtxt_id)
    else:  # 有缓存
        logging.info("番号 %s 使用缓存JAVTXT ID: %s", serial_number, javtxt_id)
        truepage = "/v/" + str(javtxt_id)

    base = "https://javtxt.com"
    url = base + truepage
    logging.info("请求javatxt URL: %s", url)

    return scrape_javtxt_movie_details(url)


def top_actresses():
    """获得javtxt的最受欢迎女优"""
    url = "https://javtxt.com/top-actresses"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    response = fetch_url(url=url, headers=headers, timeout=10)
    if not response:
        logging.warning("-----请求失败-----")
        return False

    result: list[str] = []
    if response.status_code == 200:  # 判断请求成功
        logging.info("-----请求成功-----")
        soup = BeautifulSoup(response.text, "html.parser")
        actress_links = soup.find_all("p", class_="actress-name")
        for actress in actress_links:
            result.append(actress.text)
    else:
        logging.info("-----请求失败-----")
        logging.info(response.status_code)
        return False

    # 下面是写入
    logging.info(f"获取到热门女优{result}")
    from core.database.query import exist_actress

    for actress in result[:50]:  # 只取前50个
        actress = actress.replace("卜", "ト")
        if not exist_actress(actress):
            from core.database.insert import InsertNewActress

            if InsertNewActress(actress, actress):
                logging.info(f"添加热门女优{actress}")

            from controller.global_signal_bus import global_signals

            global_signals.actressDataChanged.emit()
        else:
            logging.info(f"热门女优{actress}已存在")
    return True
