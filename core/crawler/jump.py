"""跳转打开网页，没有什么其他的功能"""

from __future__ import annotations

from webbrowser import open
import logging
from typing import Any
from urllib.parse import quote

from config import DEFAULT_ACTRESS_API_BASE_URL, get_actress_api_base_url

DEFAULT_LOCAL_SERVER = DEFAULT_ACTRESS_API_BASE_URL
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


def fetch_actress_minnano_via_api(
    jp_name: str,
    *,
    minnano_url: str | None = None,
    timeout: float = DEFAULT_ACTRESS_FETCH_TIMEOUT_SEC,
    base_url: str | None = None,
) -> dict[str, Any]:
    """同步 GET ``{actress_api_prefix}/{jp}``，依赖 Firefox 扩展 SSE + minnano 采集。

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
    resolved_base_url = (base_url or get_actress_api_base_url()).rstrip("/")
    url = f"{resolved_base_url}/{path}"
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


def fetch_top_actresses_via_api(
    *,
    timeout: float = DEFAULT_ACTRESS_FETCH_TIMEOUT_SEC,
    base_url: str = DEFAULT_LOCAL_SERVER,
) -> dict[str, Any]:
    """同步 GET ``/api/v1/top-actresses``，依赖 Firefox 扩展 SSE + javtxt 页解析。

    返回服务端 JSON（``ok``、``names``、可选 ``error``）；HTTP/网络失败时 ``ok`` 为 False。
    """
    import requests

    url = f"{base_url.rstrip('/')}/api/v1/top-actresses"
    try:
        r = requests.get(url, timeout=timeout)
    except OSError as e:
        logging.error("fetch_top_actresses_via_api 请求失败: %s", e)
        return {
            "ok": False,
            "names": [],
            "error": str(e),
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
            "names": [],
            "error": detail,
            "http_status": r.status_code,
        }

    if not isinstance(body, dict):
        return {
            "ok": False,
            "names": [],
            "error": "invalid_response_json",
        }
    return body
