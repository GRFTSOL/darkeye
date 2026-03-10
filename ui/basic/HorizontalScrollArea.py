from PySide6.QtWidgets import QScrollArea
from PySide6.QtCore import Qt, Signal

class HorizontalScrollArea(QScrollArea):
    # 滚动信号：传递当前滚动条值
    scrolled = Signal(int)

    def wheelEvent(self, event):
        """使用滚轮进行水平滚动"""
        if event.angleDelta().y() != 0:  # 垂直滚轮
            # 改成水平滚动
            new_value = self.horizontalScrollBar().value() - event.angleDelta().y()
            self.horizontalScrollBar().setValue(new_value)
            # 触发滚动信号
            self.scrolled.emit(new_value)
            event.accept()
        else:
            super().wheelEvent(event)