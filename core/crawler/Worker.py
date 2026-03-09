
import time
import traceback
from PySide6.QtCore import QRunnable, QThreadPool, Signal, Slot, QObject,QThread
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget
import logging
import threading

# 定义信号类（用于线程间通信）
class WorkerSignals(QObject):
    finished = Signal(object)  # 完成信号，返回结果

# 定义任务类,是那种一个一个的任务
class Worker(QRunnable):
    '''给现程池用的
    QThreadPool+QRunnable
    使用方法：
    worker=Worker(lambda:SearchSingleActressInfo(self.actress_id,self.actress_name[0]["jp"]))#传一个函数名进去
    worker.signals.finished.connect(self.on_result)
    QThreadPool.globalInstance().start(worker)
    '''
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.signals = WorkerSignals()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.result=None

    def run(self):
        try:
            thread_name = getattr(self.func, "__name__", "<lambda>")
            current_qt_thread = QThread.currentThread()
            current_qt_thread.setObjectName(str(thread_name))
            logging.info(f"Worker 开始: {thread_name} (线程 {threading.current_thread().name})")
            self.result = self.func(*self.args, **self.kwargs)
            logging.info(f"Worker 完成: {thread_name}，即将 emit")
            self.signals.finished.emit(self.result)
        except Exception as e:
            logging.error(f"Worker 异常: {e}\n{traceback.format_exc()}")
            self.signals.finished.emit(None)