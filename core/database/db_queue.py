# 单队列数据库工作线程：任务串行执行；每个任务在 fn 内自行短连接（对单库可 with get_connection(...)）。
from __future__ import annotations

import logging
import queue
import threading
from concurrent.futures import Future
from typing import Callable, TypeVar

from PySide6.QtCore import QThread

logger = logging.getLogger(__name__)

T = TypeVar("T")

_STOP = object()


class DatabaseQueueWorker(QThread):
    """所有任务在同一线程按 FIFO 执行；数据库访问写在 fn 里（可多次 get_connection）。"""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("DatabaseQueueWorker")
        self._q: queue.Queue = queue.Queue()
        self._accepting = True
        self._lock = threading.Lock()

    def submit_raw(self, fn: Callable[[], T]) -> Future[T]:
        fut: Future[T] = Future()
        with self._lock:
            if not self._accepting:
                fut.set_exception(RuntimeError("数据库队列已关闭，无法提交任务"))
                return fut
            self._q.put((fn, fut))
        return fut

    def run(self) -> None:
        threading.current_thread().name = "DatabaseQueueWorker"
        while True:
            item = self._q.get()
            if item is _STOP:
                self._q.task_done()
                break
            fn, fut = item
            try:
                if not fut.cancelled():
                    try:
                        result = fn()
                        if not fut.cancelled():
                            fut.set_result(result)
                    except BaseException as e:
                        if not fut.cancelled():
                            fut.set_exception(e)
            finally:
                self._q.task_done()

        self._drain_cancel_remaining()

    def _drain_cancel_remaining(self) -> None:
        while True:
            try:
                item = self._q.get_nowait()
            except queue.Empty:
                break
            if item is _STOP:
                self._q.task_done()
                continue
            _, fut = item
            fut.cancel()
            self._q.task_done()


_worker: DatabaseQueueWorker | None = None


def start_db_queue_worker() -> DatabaseQueueWorker:
    global _worker
    if _worker is not None:
        return _worker
    _worker = DatabaseQueueWorker()
    _worker.start()
    return _worker


def _get_db_queue_worker() -> DatabaseQueueWorker:
    if _worker is None:
        raise RuntimeError(
            "DatabaseQueueWorker 未启动，请在 main 中调用 start_db_queue_worker()"
        )
    return _worker


def submit_db_raw(fn: Callable[[], T]) -> Future[T]:
    """跨公库+私库、或多段短连接逻辑：整段放进一个 fn，在数据库线程里顺序执行。
    fn 在数据库工作线程执行，不得直接操作 GUI；更新界面请用信号等回到主线程」，避免以后误用。
    """
    return _get_db_queue_worker().submit_raw(fn)


def stop_db_queue_worker(timeout_ms: int = 30_000) -> None:
    global _worker
    w = _worker
    if w is None:
        return
    with w._lock:
        w._accepting = False
        w._q.put(_STOP)
    if not w.wait(timeout_ms):
        logger.warning("数据库队列线程在 %sms 内未结束", timeout_ms)
    _worker = None
