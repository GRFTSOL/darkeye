import logging
import os
import random
import shutil
import sqlite3
import threading
import time
import uuid

import requests

from config import DATABASE
from core.database.update import update_titlestory
from .javtxt import fetch_javtxt_movie_info

_LOCAL_COVER_FETCH_BASE = "http://127.0.0.1:56789"
_COVER_FETCH_WAIT_S = 45.0

_pending_cover_fetch: dict[str, dict] = {}
_pending_cover_fetch_lock = threading.Lock()
_cover_fetch_bridge_connected = False
_cover_fetch_bridge_conn_lock = threading.Lock()


def _cover_fetch_bridge_handler(rid: str, temp_path: object, err: str) -> None:
    """与 ``ServerBridge.coverBrowserFetchResult`` 直连；仅做线程安全唤醒。"""
    with _pending_cover_fetch_lock:
        box = _pending_cover_fetch.get(rid)
    if box is None:
        return
    box["temp_path"] = temp_path
    box["err"] = (err or "").strip() if err is not None else ""
    box["event"].set()


def _ensure_cover_fetch_bridge() -> None:
    global _cover_fetch_bridge_connected
    with _cover_fetch_bridge_conn_lock:
        if _cover_fetch_bridge_connected:
            return
        from PySide6.QtCore import Qt

        from server.bridge import bridge

        # 槽在发射线程（多为 uvicorn 处理线程）执行，用 Event 唤醒 Worker 线程，
        # 不依赖主线程事件循环。
        bridge.coverBrowserFetchResult.connect(
            _cover_fetch_bridge_handler,
            Qt.ConnectionType.DirectConnection,
        )
        _cover_fetch_bridge_connected = True


def download_image(url, save_path) -> tuple[bool, str]:
    """下载图片"""
    try:
        # 发送 HTTP GET 请求
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()  # 检查请求是否成功

        # 以二进制写入模式打开文件
        with open(save_path, "wb") as file:
            for chunk in response.iter_content(1024):
                file.write(chunk)
        print(f"图片已保存到: {save_path}")
        return True, "成功下载"
    except Exception as e:
        print(f"下载图片失败: {e}")
        return False, str(e)


def download_image_js(url, save_path) -> tuple[bool, str]:
    """通过本地 HTTP 服务通知浏览器插件 fetch 图片并写入 save_path（与 download_image 签名一致）。

    完成结果通过 ``bridge.coverBrowserFetchResult`` 唤醒，与手工添加页同源，不做 HTTP 轮询。
    """
    save_path = os.path.abspath(save_path)
    request_id = uuid.uuid4().hex
    _ensure_cover_fetch_bridge()
    box: dict = {
        "event": threading.Event(),
        "temp_path": None,
        "err": "",
    }
    with _pending_cover_fetch_lock:
        _pending_cover_fetch[request_id] = box
    try:
        try:
            r = requests.post(
                f"{_LOCAL_COVER_FETCH_BASE}/api/v1/cover-image-fetch",
                json={
                    "url": url,
                    "request_id": request_id,
                    "allow_any_host": True,
                },
                timeout=5,
            )
            data = r.json() if r.text else {}
            if not r.ok:
                detail = data.get("detail", "")
                if isinstance(detail, list):
                    detail = str(detail)
                return False, str(detail or r.reason or r.status_code)

            cnt = int(data.get("listener_count", 0))
            if cnt == 0:
                return (
                    False,
                    "未检测到已连接本地服务的浏览器插件，请打开浏览器并启用 DarkEye 扩展",
                )

            if not box["event"].wait(timeout=_COVER_FETCH_WAIT_S):
                _try_remove(save_path)
                return False, "浏览器未在时限内返回图片"

            err = box["err"]
            temp_path = box["temp_path"]
            if err:
                _try_remove(save_path)
                return False, err
            if not temp_path or not isinstance(temp_path, str):
                _try_remove(save_path)
                return False, "无临时文件路径"
            try:
                parent = os.path.dirname(save_path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                shutil.copyfile(temp_path, save_path)
            except Exception as e:
                _try_remove(save_path)
                logging.warning("插件图片复制失败: %s", e, exc_info=True)
                return False, str(e)
            print(f"图片已保存到: {save_path}")
            return True, "成功下载"
        except Exception as e:
            logging.warning("download_image_js 失败: %s", e, exc_info=True)
            _try_remove(save_path)
            return False, str(e)
    finally:
        with _pending_cover_fetch_lock:
            _pending_cover_fetch.pop(request_id, None)


def _try_remove(path: str) -> None:
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def download_image_with_retry(
    url,
    save_path,
    *,
    timeout_s: float = 10,
    retries: int = 0,  # 最多一次重复请求，下载图片
    backoff_base_s: float = 0.6,
) -> tuple[bool, str]:
    """下载图片"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }

    last_err: Exception | None = None
    for attempt in range(max(0, retries) + 1):
        try:
            response = requests.get(
                url, stream=True, timeout=timeout_s, headers=headers
            )
            response.raise_for_status()

            with open(save_path, "wb") as file:
                for chunk in response.iter_content(1024):
                    if chunk:
                        file.write(chunk)

            print(f"图片已保存到: {save_path}")
            return True, "成功下载"
        except Exception as e:
            last_err = e
            logging.warning(
                "下载图片失败 attempt=%s/%s url=%s err=%s",
                attempt + 1,
                max(0, retries) + 1,
                url,
                repr(e),
            )
            # 失败时尽量清理半成品文件
            try:
                if os.path.exists(save_path):
                    os.remove(save_path)
            except Exception as rm_exc:
                logging.debug(
                    "下载失败后清理半成品文件失败 path=%s: %s",
                    save_path,
                    rm_exc,
                    exc_info=True,
                )

            if attempt < max(0, retries):
                time.sleep(backoff_base_s * (2**attempt) + random.uniform(0.0, 0.2))

    print(f"下载图片失败: {last_err}")
    return False, str(last_err) if last_err is not None else "Unknown Error"


def update_title_story_db():
    """更新整个数据库中的story"""

    query = f"""
        SELECT serial_number
        FROM work
        WHERE jp_title is NULL
        """
    with sqlite3.connect(DATABASE) as conn:
        # 返回所有需要更新的番号
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        serial_number_list = [row[0] for row in rows]

    for serial_number in serial_number_list:
        print(serial_number)
        data = fetch_javtxt_movie_info(serial_number)
        if data is not None:
            update_titlestory(
                serial_number,
                data["cn_title"],
                data["jp_title"],
                data["cn_story"],
                data["jp_story"],
            )
        time.sleep(random.uniform(8, 15))
