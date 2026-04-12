import logging
import traceback
from collections.abc import Callable

from PySide6.QtCore import (
    QCoreApplication,
    QObject,
    QRunnable,
    QThread,
    Qt,
    Signal,
    Slot,
)


# 定义信号类（用于线程间通信）
class WorkerSignals(QObject):
    finished = Signal(object)  # 完成信号，返回结果


# 定义任务类,是那种一个一个的任务
class Worker(QRunnable):
    """给现程池用的
    QThreadPool+QRunnable
    使用方法：
    worker=Worker(lambda:SearchSingleActressInfo(self.actress_id,self.actress_name[0]["jp"]))#传一个函数名进去
    worker.signals.finished.connect(self.on_result)
    QThreadPool.globalInstance().start(worker)
    """

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        # 线程池在 run 结束后回收 QRunnable；否则 Worker/闭包/result 会永久堆积（典型内存泄漏）
        self.setAutoDelete(True)
        self.signals = WorkerSignals()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.result = None

    def run(self):
        try:
            thread_name = getattr(self.func, "__name__", "<lambda>")
            qt_thread = QThread.currentThread()
            if not qt_thread.objectName():
                qt_thread.setObjectName(str(thread_name))
            logging.info(
                "Worker 开始: %s (Qt 线程 %s)",
                thread_name,
                qt_thread.objectName(),
            )
            self.result = self.func(*self.args, **self.kwargs)
            logging.info("Worker 完成: %s，即将 emit", thread_name)
            self.signals.finished.emit(self.result)
        except Exception as e:
            logging.error(f"Worker 异常: {e}\n{traceback.format_exc()}")
            self.signals.finished.emit(None)
        finally:
            # 尽快断开对大对象（爬取结果等）的引用；signals 由父对象或 wire 槽内 deleteLater 回收
            self.func = None
            self.args = ()
            self.kwargs = {}
            self.result = None


def wire_worker_finished(worker: "Worker", slot: Callable[[object], None]) -> None:
    """连接 finished 到 slot，并在投递完成后释放 WorkerSignals（需伴 setAutoDelete(True) 的 Worker）。"""
    app = QCoreApplication.instance()
    if app is not None:
        worker.signals.setParent(app)

    @Slot(object)
    def _wrapped(result: object) -> None:
        try:
            slot(result)
        finally:
            signals = worker.signals
            if signals is not None:
                worker.signals = None
                signals.deleteLater()

    worker.signals.finished.connect(_wrapped, Qt.ConnectionType.QueuedConnection)
