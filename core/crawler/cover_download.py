import logging
from collections import deque

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot, Qt

from core.crawler.worker import Worker


class DownloadRelay(QObject):
    """防止下载 Worker 回调期间 relay 被回收。"""

    def __init__(self, downloader):
        super().__init__()
        self.downloader = downloader

    @Slot(object)
    def handle(self, result):
        self.downloader._on_download_result(result)


class SequentialDownloader(QObject):
    """顺序尝试多个 URL 下载封面（每步一个 Worker）。"""

    finished = Signal(bool, str)
    success = Signal(str)

    def __init__(
        self,
        manager,
        withGUI: bool = False,
        *,
        task_id: str | None = None,
        total: int = 0,
        thread_pool: QThreadPool | None = None,
    ):
        super().__init__()
        self.manager = manager
        self._thread_pool = thread_pool
        self.current_worker_id = None
        self._download_in_progress = False
        self.withGUI = withGUI
        self.task_id = task_id
        self.total = max(0, int(total)) if total is not None else 0
        self._current_index = 0

    def _pool(self) -> QThreadPool:
        return (
            self._thread_pool
            if self._thread_pool is not None
            else QThreadPool.globalInstance()
        )

    def __del__(self):
        logging.info("SequentialDownloader 实例已成功销毁，内存已释放")

    def start(self, url_list, save_path, image_filename):
        if (
            not self._download_in_progress
            and self.current_worker_id
            and self.current_worker_id in self.manager._download_relays
        ):
            del self.manager._download_relays[self.current_worker_id]
            self.current_worker_id = None

        logging.info("开始下载%s到%s", url_list, save_path)
        self.urls = deque(url_list)
        self.save_path = save_path
        self.image_filename = image_filename
        self._current_index = 0

        if self.task_id:
            from controller.global_signal_bus import global_signals

            total = self.total or len(self.urls)
            global_signals.downloadTaskStarted.emit(self.task_id, int(total))

        self._try_next()

    def _emit_progress(self, msg: str):
        if not self.task_id:
            return
        from controller.global_signal_bus import global_signals

        total = self.total or (self._current_index or 0)
        global_signals.downloadTaskProgress.emit(
            self.task_id, int(self._current_index), int(total), msg
        )

    def _try_next(self):
        if not self.urls:
            self.finished.emit(False, "所有地址均下载失败")
            if self.task_id:
                from controller.global_signal_bus import global_signals

                self._emit_progress("所有地址均下载失败")
                global_signals.downloadTaskFinished.emit(
                    self.task_id, False, "所有地址均下载失败"
                )
            return

        from core.crawler.download import download_image

        url = self.urls.popleft()
        self._current_index += 1
        self._emit_progress(f"正在下载封面 {self._current_index} ...")

        worker = Worker(lambda: download_image(url, self.save_path))
        relay = DownloadRelay(self)
        worker.signals.setParent(relay)
        relay.moveToThread(self.manager.thread())

        self.current_worker_id = id(worker)
        self.manager._download_relays[self.current_worker_id] = relay
        self._download_in_progress = True

        worker.signals.finished.connect(relay.handle, Qt.QueuedConnection)
        self._pool().start(worker)

    @Slot(object)
    def _on_download_result(self, result):
        worker_id = self.current_worker_id
        try:
            if result is None:
                success, e = False, "Unknown Error (None result)"
            else:
                success, e = result

            if success:
                logging.info("成功下载图片到临时地址%s", self.save_path)
                self.finished.emit(True, str(self.save_path))
                if self.task_id:
                    from controller.global_signal_bus import global_signals

                    self._emit_progress("封面下载完成")
                    global_signals.downloadTaskFinished.emit(
                        self.task_id, True, "封面下载完成"
                    )
            else:
                self._emit_progress(f"下载失败，尝试下一个地址 ({e})")
                self._try_next()
                return
        finally:
            if worker_id and worker_id in self.manager._download_relays:
                del self.manager._download_relays[worker_id]
            if self.current_worker_id == worker_id:
                self.current_worker_id = None
                self._download_in_progress = False
