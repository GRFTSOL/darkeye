from PySide6.QtCore import QObject, Slot


class ResultRelay(QObject):
    """将各源 Worker 结果投递回 CrawlerManager（主线程槽）。"""

    def __init__(self, manager, source, serial):
        super().__init__()
        self._manager = manager
        self._source = source
        self._serial = serial

    @Slot(object)
    def handle(self, result):
        self._manager.on_result_received(self._source, self._serial, result)


class MergeRelay(QObject):
    """预留：合并结果投递（当前流程使用 _on_merge_worker_finished）。"""

    def __init__(self, manager, serial):
        super().__init__()
        self._manager = manager
        self._serial = serial

    @Slot(object)
    def handle(self, final_data):
        if hasattr(self._manager, "on_merge_finished"):
            self._manager.on_merge_finished(self._serial, final_data)
