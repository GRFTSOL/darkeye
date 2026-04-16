import logging
import os
import shutil
import threading
import uuid

import requests

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


def download_image_js(url, save_path) -> tuple[bool, str]:
    """通过本地 HTTP 服务通知浏览器插件 fetch 图片并写入 save_path。

    应用内统一用此函数拉取远程图片；完成结果通过 ``bridge.coverBrowserFetchResult``
    唤醒，与手工添加页同源，不做 HTTP 轮询。
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
