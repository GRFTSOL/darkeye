# ui/components/label.py - 设计系统标签，样式由 mymain.qss + 令牌驱动
from typing import Optional

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt


class Label(QLabel):
    """可复用标签，通过 objectName=DesignLabel 由 QSS 驱动样式。"""

    def __init__(self, text: str = "", tone: Optional[str] = None, parent=None):
        super().__init__(text, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setObjectName("DesignLabel")
        if tone is not None:
            self.setProperty("tone", tone)

    def set_tone(self, tone: Optional[str]) -> None:
        """切换文字在不同背景上的语气（normal / onDark / onImage）。"""
        if tone is None:
            # 移除属性时传入空字符串，避免 QSS 残留匹配
            self.setProperty("tone", "")
        else:
            self.setProperty("tone", tone)
        # 触发样式重算
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
