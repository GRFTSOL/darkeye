
from PySide6.QtWidgets import QPushButton, QHBoxLayout, QWidget,QVBoxLayout
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from darkeye_ui import LazyWidget
from darkeye_ui.components.label import Label

class AvPage(LazyWidget):
    def __init__(self):
        super().__init__()
        
    def _lazy_load(self):
        mainlayout = QVBoxLayout(self)
        mainlayout.setContentsMargins(0, 0, 0, 0)

        #mainlayout.addSpacing(70)

        self.label = Label("AV知识科普页面")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(f"font-size: 28px;")
        mainlayout.addWidget(self.label)

