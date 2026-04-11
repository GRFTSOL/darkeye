"""跳转打开网页，没有什么其他的功能"""

from __future__ import annotations

from webbrowser import open
import logging
from typing import Any
from urllib.parse import quote

DEFAULT_LOCAL_SERVER = "http://127.0.0.1:56789"
# 略大于 server WORK_MERGE_TIMEOUT_SEC，避免客户端先断连
DEFAULT_ACTRESS_FETCH_TIMEOUT_SEC = 130.0


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


def fetch_actress_minnano_via_api(
    jp_name: str,
    *,
    minnano_url: str | None = None,
    timeout: float = DEFAULT_ACTRESS_FETCH_TIMEOUT_SEC,
    base_url: str = DEFAULT_LOCAL_SERVER,
) -> dict[str, Any]:
    """同步 GET ``/api/v1/actress/{jp}``，依赖 Firefox 扩展 SSE + minnano 采集。

    返回插件/服务端 JSON；失败时 ``ok`` 为 False，``error`` 为说明字符串。
    """
    import requests

    jp = (jp_name or "").strip()
    if not jp:
        return {
            "ok": False,
            "error": "actress_jp_name required",
            "actress_jp_name": jp,
            "data": None,
        }

    path = quote(jp, safe="")
    url = f"{base_url.rstrip('/')}/api/v1/actress/{path}"
    params = {}
    mid = (minnano_url or "").strip()
    if mid:
        params["minnano_url"] = mid

    try:
        r = requests.get(url, params=params, timeout=timeout)
    except OSError as e:
        logging.error("fetch_actress_minnano_via_api 请求失败: %s", e)
        return {
            "ok": False,
            "error": str(e),
            "actress_jp_name": jp,
            "data": None,
        }

    try:
        body = r.json()
    except Exception:
        body = {}

    if r.status_code != 200:
        detail: str
        if isinstance(body, dict):
            raw = body.get("detail")
            if isinstance(raw, str):
                detail = raw
            elif isinstance(raw, list):
                detail = str(raw)
            else:
                detail = (
                    str(raw) if raw is not None else (r.text or f"HTTP {r.status_code}")
                )
        else:
            detail = r.text or f"HTTP {r.status_code}"
        return {
            "ok": False,
            "error": detail,
            "actress_jp_name": jp,
            "data": None,
            "http_status": r.status_code,
        }

    if not isinstance(body, dict):
        return {
            "ok": False,
            "error": "invalid_response_json",
            "actress_jp_name": jp,
            "data": None,
        }
    return body


def send_crawler_request(web: str, serial_number: str):
    """发送爬取指令到本地服务器，由本地服务器经 SSE 指挥浏览器插件。

    ``web``：javlib、javdb、javtxt、fanza、avdanyuwiki 等。
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
