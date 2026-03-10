from PySide6.QtWidgets import QWidget


class LazyWidget(QWidget):
    """惰性初始化基类：首次 show 时再执行 _lazy_load()。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initialized = False

    def showEvent(self, event):
        if not self._initialized:
            self._lazy_load()
            self._initialized = True
        super().showEvent(event)

    def _lazy_load(self):
        """子类必须实现：惰性初始化 UI（首次 show 时调用）"""
        raise NotImplementedError("子类必须实现 _lazy_load()")
