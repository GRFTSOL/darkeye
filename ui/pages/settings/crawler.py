"""爬虫相关设置页面。"""

from PySide6.QtWidgets import QVBoxLayout, QWidget
from darkeye_ui.components.label import Label


class ClawerSettingPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(Label("<h3>爬虫相关设置</h3>"))
