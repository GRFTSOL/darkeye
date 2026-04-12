# darkeye_ui/components/token_list_widget.py - 设计系统列表控件，样式由 mymain.qss + 令牌驱动
from PySide6.QtWidgets import QListWidget


class TokenListWidget(QListWidget):
    """可复用列表控件，通过 objectName=DesignListWidget 由 QSS 令牌驱动样式，随主题切换变色。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DesignListWidget")
