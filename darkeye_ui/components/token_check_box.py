# darkeye_ui/components/token_check_box.py - 设计系统复选框，样式由 mymain.qss + 令牌驱动
from PySide6.QtWidgets import QCheckBox


class TokenCheckBox(QCheckBox):
    """可复用复选框，通过 objectName=DesignCheckBox 由 QSS 令牌驱动样式，随主题切换变色。"""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("DesignCheckBox")
