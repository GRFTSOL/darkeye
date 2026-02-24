from PySide6.QtWidgets import QLineEdit, QCompleter
from PySide6.QtCore import Qt, QEvent, Signal, Slot, QThreadPool, QRunnable
from typing import Callable
from controller.GlobalSignalBus import global_signals


class CompleterLoaderRunnable(QRunnable):
    """在后台线程执行 loader_func，结果通过 signal 传回主线程"""

    def __init__(self, loader_func: Callable[[], list], signal: Signal):
        super().__init__()
        self.loader_func = loader_func
        self.signal = signal

    def run(self):
        try:
            items = self.loader_func() if self.loader_func else []
        except Exception:
            items = []
        self.signal.emit(items)


# 点击后把补全器 list 全弹出的类
class CompleterLineEdit(QLineEdit):
    """支持传入加载函数的 QLineEdit，带弹出补全；异步加载 + 缓存。"""

    items_loaded = Signal(list)

    def __init__(self, loader_func: Callable[[], list] = None, parent=None):
        """
        初始化
        :param loader_func: 返回项目列表的函数（在后台线程执行）
        :param parent: 父组件
        """
        super().__init__(parent)
        self.items: list = []
        self.loader_func = loader_func
        self._loading = False
        self._cache: list = []  # 最近一次成功加载的结果，用于展示与防抖
        self.setup_completer()
        self.items_loaded.connect(self._on_items_loaded)
        self.installEventFilter(self)
        global_signals.work_data_changed.connect(self.reload_items)
        self.load_items()

    def set_loader_func(self, loader_func: Callable[[], list]):
        """设置新的加载函数并异步重新加载"""
        self.loader_func = loader_func
        self.reload_items()

    def load_items(self):
        """发起异步加载；若正在加载则忽略（防抖）。"""
        if self.loader_func is None or self._loading:
            return
        self._loading = True
        runnable = CompleterLoaderRunnable(self.loader_func, self.items_loaded)
        QThreadPool.globalInstance().start(runnable)

    @Slot(list)
    def _on_items_loaded(self, items: list):
        """主线程：收到异步加载结果，更新缓存与补全列表"""
        self._loading = False
        self._cache = list(items) if items is not None else []
        self.items = self._cache
        self.setup_completer()

    def setup_completer(self):
        """设置/重新设置自动完成器（使用当前 items）。"""
        self.completer1 = QCompleter(self.items)
        self.completer1.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer1.setFilterMode(Qt.MatchContains)
        self.completer1.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(self.completer1)

    def reload_items(self):
        """重新异步加载项目并刷新自动完成（会忽略缓存，重新请求）。"""
        self.load_items()

    def eventFilter(self, obj, event):
        if obj == self and event.type() == QEvent.FocusIn:
            self.try_show_completer()
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        self.try_show_completer()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.try_show_completer()

    def try_show_completer(self):
        """尝试显示自动完成弹出框"""
        if not hasattr(self, "completer1") or self.completer1 is None:
            return
        text = self.text()
        self.completer1.setCompletionPrefix(text)
        if not self.completer1.popup().isVisible() and text == "":
            self.completer1.complete(self.rect())
