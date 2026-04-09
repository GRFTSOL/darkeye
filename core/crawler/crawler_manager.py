import json
import logging
import random
from collections import deque
from typing import Dict, Optional

from PySide6.QtCore import QObject, QThread, QThreadPool, QTimer, Qt, Signal, Slot

from controller.global_signal_bus import global_signals
from core.crawler.worker import Worker
from core.crawler.crawler_relays import ResultRelay
from core.crawler.crawler_task import CrawlerTask, CrawlWorkflowState
from core.crawler.cover_download import SequentialDownloader
from core.crawler.merge_service import merge_crawl_results
from core.crawler.work_persistence import DataUpdate
from utils.utils import timeit

# 兼容旧 import：其他模块可能 from crawler_manager import DataUpdate / CrawlerTask 等
__all__ = [
    "CrawlerManager2",
    "CrawlerTask",
    "CrawlWorkflowState",
    "DataUpdate",
    "SequentialDownloader",
    "get_manager",
]


class CrawlerManager2(QObject):
    _instance = None
    taskFinished = Signal(str, dict)

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        super().__init__()
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self.tasks: Dict[str, CrawlerTask] = {}
            # 源抓取 ResultRelay：(source, serial)；下载 DownloadRelay：id(Worker)
            self._source_relays: Dict[tuple[str, str], QObject] = {}
            self._download_relays: Dict[int, QObject] = {}

            self._unfinished_serials: set[str] = set()
            self._persist_key_unfinished = "Inbox/UnfinishedSerials"

            self._crawl_terminated: bool = False

            self._crawl_pool = QThreadPool(self)
            self._crawl_pool.setObjectName("CrawlerSourcePool")
            self._crawl_pool.setMaxThreadCount(max(5, QThread.idealThreadCount()))
            self._merge_pool = QThreadPool(self)
            self._merge_pool.setObjectName("CrawlerMergePool")
            self._merge_pool.setMaxThreadCount(2)
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
        """标记运行中任务在源全部返回后跳过合并与入库（不中断已提交 Worker）。"""
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
        else:
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
        return

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

        import time

        self.last_schedule_time = time.time() * 1000

        serial, withGUI, selected_fields = self.request_queue.popleft()
        self._execute_crawl(serial, withGUI, selected_fields)

        if self.request_queue:
            self._schedule_next()
        else:
            logging.info("队列已空，停止后续调度")

    def _execute_crawl(
        self, serial_number, withGUI=False, selected_fields: set[str] | None = None
    ):
        task = CrawlerTask(
            serial_number,
            ["javlib", "javtxt", "avdanyuwiki", "javdb"],
            withGUI,
            selected_fields,
        )
        self.tasks[serial_number] = task

        self._dispatch_request("javlib", serial_number)
        self._dispatch_request("javdb", serial_number)
        self._dispatch_request("fanza", serial_number)
        self._dispatch_request("javtxt", serial_number)
        self._dispatch_request("avdanyuwiki", serial_number)

    def _dispatch_request(self, source, serial):
        if source == "javlib":
            from core.crawler.javlib import jump_to_javlib

            worker = Worker(lambda: jump_to_javlib(serial))
            relay = ResultRelay(self, "javlib", serial)
            self._source_relays[("javlib", serial)] = relay
            worker.signals.setParent(relay)
            worker.signals.finished.connect(
                relay.handle, Qt.ConnectionType.QueuedConnection
            )
            self._crawl_pool.start(worker)
        elif source == "fanza":
            pass
        elif source == "javdb":
            from core.crawler.javdb import jump_to_javdb

            worker = Worker(lambda: jump_to_javdb(serial))
            relay = ResultRelay(self, "javdb", serial)
            self._source_relays[("javdb", serial)] = relay
            worker.signals.setParent(relay)
            worker.signals.finished.connect(
                relay.handle, Qt.ConnectionType.QueuedConnection
            )
            self._crawl_pool.start(worker)
            print(f"已发送javdb请求，serial:{serial}")
        elif source == "javtxt":
            from core.crawler.javtxt import jump_to_javtxt

            worker = Worker(lambda: jump_to_javtxt(serial))
            relay = ResultRelay(self, "javtxt", serial)
            self._source_relays[("javtxt", serial)] = relay
            worker.signals.setParent(relay)
            worker.signals.finished.connect(
                relay.handle, Qt.ConnectionType.QueuedConnection
            )
            self._crawl_pool.start(worker)
        elif source == "avdanyuwiki":
            from core.crawler.avdanyuwiki import SearchInfoDanyukiwi

            worker = Worker(lambda: SearchInfoDanyukiwi(serial))
            relay = ResultRelay(self, "avdanyuwiki", serial)
            self._source_relays[("avdanyuwiki", serial)] = relay
            worker.signals.setParent(relay)
            worker.signals.finished.connect(
                relay.handle, Qt.ConnectionType.QueuedConnection
            )
            self._crawl_pool.start(worker)

    @timeit
    @Slot(str, str, dict)
    def on_result_received(self, source, serial, data):
        key = (source, serial)
        task = self.tasks.get(serial)
        if not task:
            logging.error("未找到任务 %s", serial)
            if key in self._source_relays:
                del self._source_relays[key]
            return

        result_dict = data if isinstance(data, dict) else {}
        task.results[source] = result_dict
        task.pending_sources.discard(source)
        logging.info(
            "已接收 %s 的结果 (serial=%s), 剩余待处理: %s\n%s",
            source,
            serial,
            task.pending_sources,
            json.dumps(result_dict, ensure_ascii=False, indent=2, default=str),
        )
        if key in self._source_relays:
            del self._source_relays[key]

        if not task.pending_sources:
            task.workflow_state = CrawlWorkflowState.MERGING
            if task.cancel_requested:
                if serial in self.tasks:
                    del self.tasks[serial]
                return
            worker = Worker(lambda: (serial, self._do_merge_only(serial)))
            worker.signals.setParent(self)
            worker.signals.finished.connect(
                self._on_merge_worker_finished,
                Qt.ConnectionType.QueuedConnection,
            )
            self._merge_pool.start(worker)

    def _do_merge_only(self, serial: str):
        task = self.tasks.get(serial)
        if not task or task.cancel_requested:
            return None
        return merge_crawl_results(task.results, task.serial)

    @Slot(object)
    def _on_merge_worker_finished(self, result):
        try:
            if result is None:
                return
            if isinstance(result, tuple) and len(result) == 2:
                serial, final_data = result
            else:
                final_data = result
                serial = (
                    getattr(final_data, "serial_number", None) if final_data else None
                )
            if not serial:
                return
            if not final_data:
                if serial in self.tasks:
                    del self.tasks[serial]
                return
            task = self.tasks.get(serial)
            if not task or task.cancel_requested:
                if serial in self.tasks:
                    del self.tasks[serial]
                return
            task.workflow_state = CrawlWorkflowState.PERSISTING
            DataUpdate(
                final_data,
                self,
                withGUI=task.withGUI,
                selected_fields=task.selected_fields,
            )
        finally:
            snd = self.sender()
            if snd is not None:
                snd.deleteLater()


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
