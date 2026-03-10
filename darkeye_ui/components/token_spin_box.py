# darkeye_ui/components/token_spin_box.py - 设计系统数字旋钮，样式由 mymain.qss + 令牌驱动
from PySide6.QtWidgets import QSpinBox


class TokenSpinBox(QSpinBox):
    """可复用数字旋钮（QSpinBox），通过 objectName=DesignSpinBox 由 QSS 令牌驱动样式，随主题切换变色。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DesignSpinBox")
