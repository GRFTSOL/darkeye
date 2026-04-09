"""跳转打开网页，没有什么其他的功能"""

from webbrowser import open
import logging


def jump_minnanoav(actressname):
    open(
        "https://www.minnano-av.com/search_result.php?search_scope=actress&search_word="
        + actressname
        + "&search= Go"
    )


def jump_avdanyuwiki(name):
    open("https://avdanyuwiki.com/?s=" + name)


def send_navigate_request(url: str, context: dict | None = None):
    import requests

    try:
        payload = {
            "url": url,
            "target": "new_tab",
        }
        if context is not None:
            payload["context"] = context
        # 发送导航指令到本地服务器
        response = requests.post(
            "http://localhost:56789/api/v1/navigate", json=payload, timeout=2
        )

        if response.status_code == 200:
            return True
        else:
            return False
    except Exception as e:
        logging.error(f"发送到本地浏览器跳转指令失败: {e}")
        return False


def send_crawler_request(web: str, serial_number: str):
    """发送爬取指令到本地服务器，由本地服务器经 SSE 指挥浏览器插件。

    ``web``：javlib、javdb、javtxt、fanza 等。
    """
    import requests

    try:
        # 发送导航指令到本地服务器
        response = requests.post(
            "http://localhost:56789/api/v1/startcrawler",
            json={"web": web, "serial_number": serial_number},
            timeout=2,
        )
        if response.status_code == 200:
            return True
        else:
            return False
    except Exception as e:
        logging.error(f"发送到本地浏览器跳转指令失败: {e}")
        return False
