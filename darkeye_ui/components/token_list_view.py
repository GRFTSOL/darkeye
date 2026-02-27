# darkeye_ui/components/token_list_view.py - 设计系统列表视图，样式由 mymain.qss + 令牌驱动
from PySide6.QtWidgets import QListView


class TokenListView(QListView):
    """可复用列表视图，通过 objectName=DesignListView 由 QSS 令牌驱动样式，随主题切换变色。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DesignListView")
