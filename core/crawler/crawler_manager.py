import logging
import random
import threading
from collections import deque
from typing import Dict, Optional
from urllib.parse import quote

import requests
from PySide6.QtCore import QObject, QThreadPool, QTimer, Qt, Signal, Slot

from controller.global_signal_bus import global_signals
from core.crawler.crawler_task import CrawlerTask, CrawlWorkflowState
from core.crawler.cover_download import SequentialDownloader
from core.crawler.merge_service import crawled_work_from_extension_payload
from core.crawler.work_persistence import DataUpdate

# 与 server.app WORK_MERGE_TIMEOUT_SEC + 余量一致（manual_tests 使用 130s）
_WORK_API_BASE = "http://127.0.0.1:56789"
_WORK_API_TIMEOUT_SEC = 130.0

# 兼容旧 import：其他模块可能 from crawler_manager import DataUpdate / CrawlerTask 等
__all__ = [
    "CrawlerManager2",
    "CrawlerTask",
    "CrawlWorkflowState",
    "DataUpdate",
    "SequentialDownloader",
    "get_manager",
]


class _WorkApiSignals(QObject):
    """后台线程完成 GET /api/v1/work 后向主线程投递结果。"""

    finished = Signal(
        str, object, object
    )  # serial, payload dict | None, err str | None


class CrawlerManager2(QObject):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        super().__init__()
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self.tasks: Dict[str, CrawlerTask] = {}
            self._download_relays: Dict[int, QObject] = {}

            self._unfinished_serials: set[str] = set()
            self._persist_key_unfinished = "Inbox/UnfinishedSerials"

            self._crawl_terminated: bool = False
            self._work_fetch_busy: bool = False

            self._work_api_signals = _WorkApiSignals(self)
            self._work_api_signals.finished.connect(
                self._on_work_api_finished,
                Qt.ConnectionType.QueuedConnection,
            )

            self._download_pool = QThreadPool(self)
            self._download_pool.setObjectName("CoverDownloadPool")
            self._download_pool.setMaxThreadCount(4)

            self.request_queue = deque()
            self.schedule_timer = QTimer(self)
            self.schedule_timer.setSingleShot(True)
            self.schedule_timer.timeout.connect(self._on_schedule_tick)
            self.last_schedule_time = 0

            from server.bridge import bridge

            bridge.captureOneReceived.connect(
                lambda serial_number: self.start_crawl([serial_number]),
                Qt.ConnectionType.QueuedConnection,
            )

            global_signals.downloadTaskFinished.connect(
                self._on_download_task_finished,
                Qt.ConnectionType.QueuedConnection,
            )

            self._restore_unfinished_from_ini()

    def inbox_snapshot(self) -> tuple[set[str], set[str]]:
        """只读：待爬队列番号集合、元数据爬取中任务番号集合。"""
        return ({item[0] for item in self.request_queue}, set(self.tasks.keys()))

    def get_serial_workflow_state(self, serial: str) -> CrawlWorkflowState | None:
        """只读：某番号当前工作流阶段；不在队列且不在 tasks 则返回 None。"""
        serial = self._norm_serial(serial)
        if not serial:
            return None
        if any(item[0] == serial for item in self.request_queue):
            return CrawlWorkflowState.QUEUED
        task = self.tasks.get(serial)
        return task.workflow_state if task else None

    def request_cancel_running(self, serial: str) -> bool:
        """标记运行中任务在请求返回后跳过入库（不中断已发出的 HTTP）。"""
        serial = self._norm_serial(serial)
        task = self.tasks.get(serial)
        if not task or task.serial != serial:
            return False
        task.cancel_requested = True
        return True

    def start_crawl(
        self, serial_numbers, withGUI=False, selected_fields: set[str] | None = None
    ):
        if getattr(self, "_crawl_terminated", False):
            logging.info("检测到爬虫调度器处于终止状态：自动恢复后继续 start_crawl")
            self.resume_crawl()
        if isinstance(serial_numbers, str):
            serial_numbers = [serial_numbers]

        existing_serials = {item[0] for item in self.request_queue}

        for serial_number in serial_numbers:
            serial_number = self._norm_serial(serial_number)
            if not serial_number:
                continue
            if serial_number in existing_serials:
                logging.info("任务 %s 已在队列中，跳过重复添加", serial_number)
                continue
            self.request_queue.append(
                (
                    serial_number,
                    withGUI,
                    set(selected_fields) if selected_fields else None,
                )
            )
            logging.info(
                "任务 %s 已入队，当前队列长度: %s",
                serial_number,
                len(self.request_queue),
            )

            self._unfinished_serials.add(serial_number)
            self._persist_unfinished_to_ini()

        if not self.schedule_timer.isActive() and self.request_queue:
            import time

            now = time.time() * 1000
            elapsed = now - self.last_schedule_time
            min_interval = 12000

            if elapsed < min_interval:
                delay = int(min_interval - elapsed)
                self._schedule_next(delay)
            else:
                self._schedule_next(0)

    def terminate_crawl(self, *, clear_queue: bool = True):
        self._crawl_terminated = True

        if self.schedule_timer.isActive():
            self.schedule_timer.stop()

        if clear_queue:
            dropped = len(self.request_queue)
            dropped_serials = {item[0] for item in self.request_queue}
            self.request_queue.clear()
            logging.info(
                "爬虫调度器已终止：已丢弃未开始任务 %s 个；正在运行的任务将继续执行",
                dropped,
            )
            if dropped_serials:
                self._unfinished_serials.difference_update(dropped_serials)
                self._persist_unfinished_to_ini()
        else:
            logging.info("爬虫调度器已终止：未清空队列（但也不会再调度）")

    def is_crawl_terminated(self) -> bool:
        return bool(getattr(self, "_crawl_terminated", False))

    def resume_crawl(self):
        self._crawl_terminated = False

        if self.request_queue and not self.schedule_timer.isActive():
            import time

            now = time.time() * 1000
            elapsed = now - self.last_schedule_time
            min_interval = 12000
            delay = int(min_interval - elapsed) if elapsed < min_interval else 0
            self._schedule_next(delay)

    def drop_pending(self, serial: str) -> bool:
        serial = self._norm_serial(serial)
        if not serial:
            return False

        removed_from_queue = False
        new_q = deque()
        while self.request_queue:
            s, withGUI, selected_fields = self.request_queue.popleft()
            if s == serial and not removed_from_queue:
                removed_from_queue = True
                continue
            new_q.append((s, withGUI, selected_fields))
        self.request_queue = new_q

        if serial in self._unfinished_serials:
            self._unfinished_serials.discard(serial)
        self._persist_unfinished_to_ini()

        return removed_from_queue

    def _norm_serial(self, serial: str) -> str:
        if serial is None:
            return ""
        return str(serial).strip()

    def _load_unfinished_from_ini(self) -> list[str]:
        from config import settings

        raw = settings.value(self._persist_key_unfinished, "", type=str)
        if not raw:
            return []
        parts = [p.strip() for p in str(raw).split(",") if p and str(p).strip()]
        seen: set[str] = set()
        out: list[str] = []
        for p in parts:
            if p in seen:
                continue
            seen.add(p)
            out.append(p)
        return out

    def _persist_unfinished_to_ini(self) -> None:
        from config import settings

        serials = sorted(self._unfinished_serials)
        settings.setValue(self._persist_key_unfinished, ",".join(serials))

    def _restore_unfinished_from_ini(self) -> None:
        serials = self._load_unfinished_from_ini()
        if not serials:
            return

        self._crawl_terminated = True

        existing = {item[0] for item in self.request_queue}
        restored = 0
        for s in serials:
            s = self._norm_serial(s)
            if not s or s in existing:
                continue
            self.request_queue.append((s, False, None))
            self._unfinished_serials.add(s)
            restored += 1

        if restored:
            logging.info(
                "已从 settings.ini 恢复未完成任务 %s 个到队列（默认暂停调度）",
                restored,
            )
            self._persist_unfinished_to_ini()

    @Slot(str, bool, str)
    def _on_download_task_finished(self, serial: str, success: bool, msg: str) -> None:
        serial = self._norm_serial(serial)
        if not serial:
            return
        if serial in self._unfinished_serials:
            self._unfinished_serials.discard(serial)
            self._persist_unfinished_to_ini()
        if serial in self.tasks:
            del self.tasks[serial]

    def _schedule_next(self, delay=None):
        if getattr(self, "_crawl_terminated", False):
            logging.info("爬虫调度器已终止：跳过 _schedule_next")
            return
        if delay is None:
            delay = random.randint(12000, 18000)
        self.schedule_timer.start(delay)
        logging.info("调度器将在 %.1f 秒后执行下一个任务", delay / 1000)

    def _on_schedule_tick(self):
        if getattr(self, "_crawl_terminated", False):
            logging.info("爬虫调度器已终止：停止后续调度")
            return
        if not self.request_queue:
            logging.info("队列为空，调度器停止")
            return
        if self._work_fetch_busy:
            self._schedule_next(1000)
            return

        import time

        self.last_schedule_time = time.time() * 1000

        serial, withGUI, selected_fields = self.request_queue.popleft()
        self._execute_work_api_fetch(serial, withGUI, selected_fields)

    def _work_api_url(self, serial: str) -> str:
        return f"{_WORK_API_BASE}/api/v1/work/{quote(serial, safe='')}"

    def _execute_work_api_fetch(
        self,
        serial_number: str,
        withGUI: bool = False,
        selected_fields: set[str] | None = None,
    ) -> None:
        serial_number = self._norm_serial(serial_number)
        if not serial_number:
            self._after_work_api_cycle()
            return

        self._work_fetch_busy = True
        task = CrawlerTask(serial_number, withGUI, selected_fields)
        self.tasks[serial_number] = task

        url = self._work_api_url(serial_number)
        sig = self._work_api_signals

        def run() -> None:
            try:
                r = requests.get(url, timeout=_WORK_API_TIMEOUT_SEC)
                if r.status_code != 200:
                    tail = (r.text or "")[:400]
                    sig.finished.emit(
                        serial_number,
                        None,
                        f"HTTP {r.status_code} {tail}",
                    )
                    return
                try:
                    body = r.json()
                except Exception as e:
                    sig.finished.emit(serial_number, None, f"invalid JSON: {e}")
                    return
                if not isinstance(body, dict):
                    sig.finished.emit(serial_number, None, "response is not an object")
                    return
                sig.finished.emit(serial_number, body, None)
            except Exception as e:
                sig.finished.emit(serial_number, None, str(e))

        threading.Thread(target=run, daemon=True).start()

    @Slot(str, object, object)
    def _on_work_api_finished(
        self, serial: str, payload: object, err: Optional[str]
    ) -> None:
        self._work_fetch_busy = False
        serial = self._norm_serial(serial)
        if not serial:
            self._after_work_api_cycle()
            return

        task = self.tasks.get(serial)
        if task and task.cancel_requested:
            if serial in self.tasks:
                del self.tasks[serial]
            logging.info("任务 %s 已取消，跳过入库", serial)
            self._after_work_api_cycle()
            return

        if err:
            logging.error("work API 失败 serial=%s: %s", serial, err)
            if serial in self.tasks:
                del self.tasks[serial]
            self._after_work_api_cycle()
            return

        if not isinstance(payload, dict):
            logging.error("work API 无效 payload serial=%s", serial)
            if serial in self.tasks:
                del self.tasks[serial]
            self._after_work_api_cycle()
            return

        if not payload.get("ok"):
            logging.warning(
                "work API ok=false serial=%s error=%s",
                serial,
                payload.get("error"),
            )
            if serial in self.tasks:
                del self.tasks[serial]
            self._after_work_api_cycle()
            return

        data = payload.get("data")
        if not isinstance(data, dict) or not data:
            logging.warning("work API 缺少 data serial=%s", serial)
            if serial in self.tasks:
                del self.tasks[serial]
            self._after_work_api_cycle()
            return

        task = self.tasks.get(serial)
        if not task or task.cancel_requested:
            if serial in self.tasks:
                del self.tasks[serial]
            self._after_work_api_cycle()
            return

        try:
            merged = crawled_work_from_extension_payload(data)
        except Exception as e:
            logging.error("解析 extension data 失败 serial=%s: %s", serial, e)
            if serial in self.tasks:
                del self.tasks[serial]
            self._after_work_api_cycle()
            return

        task.workflow_state = CrawlWorkflowState.PERSISTING
        DataUpdate(
            merged,
            self,
            withGUI=task.withGUI,
            selected_fields=task.selected_fields,
        )
        self._after_work_api_cycle()

    def _after_work_api_cycle(self) -> None:
        if getattr(self, "_crawl_terminated", False):
            return
        if self.request_queue:
            self._schedule_next()
        else:
            logging.info("队列已空，停止后续调度")


_crawler_manager2: Optional["CrawlerManager2"] = None


def get_manager() -> "CrawlerManager2":
    global _crawler_manager2
    if _crawler_manager2 is None:
        from PySide6.QtCore import QCoreApplication, QThread

        app = QCoreApplication.instance()
        if app is not None and QThread.currentThread() != app.thread():
            raise RuntimeError(
                "CrawlerManager2 必须在主线程首次初始化（请在 MainWindow show 后调用 get_manager()）"
            )

        _crawler_manager2 = CrawlerManager2()
    return _crawler_manager2
