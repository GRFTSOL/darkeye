from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QToolButton,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from pathlib import Path
import sys
root_dir = Path(__file__).resolve().parents[1]  # 上两级
sys.path.insert(0, str(root_dir))
from config import ICONS_PATH

class CollapsibleSection(QWidget):
    """
    可折叠面板（Accordion 风格）
    - 点击标题展开/收起内容区
    - 支持平滑动画
    """
    toggled = Signal(bool)  # 发出展开/收起状态

    def __init__(self, title: str = "标题", parent=None):
        super().__init__(parent)

        self._is_expanded = False

        # 标题栏（可点击）
        self.toggle_btn = QToolButton()
        self.toggle_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toggle_btn.setText(title)
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(False)
        self.toggle_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        #self.toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_btn.setIcon(QIcon(str(ICONS_PATH/"arrow-right.svg")))
        self.toggle_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background: #f0f0f0;
                padding: 8px;
                font-weight: bold;
                text-align: left;
            }
            QToolButton:checked {
                background: #e0e0e0;
            }
        """)
        self.toggle_btn.toggled.connect(self.toggle_content)

        # 内容区域
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.content.setVisible(False)

        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.toggle_btn)
        layout.addWidget(self.content)

    def toggle_content(self, checked):
        self._is_expanded = checked
        self.toggle_btn.setIcon(QIcon(str(ICONS_PATH/"arrow-down.svg")) if checked else QIcon(str(ICONS_PATH/"arrow-right.svg")))
        self.content.setVisible(checked)
        self.toggled.emit(checked)

    def addWidget(self, widget):
        """向内容区添加控件"""
        self.content_layout.addWidget(widget)

    def addLayout(self, layout):
        self.content_layout.addLayout(layout)

    def expand(self):
        """强制展开"""
        self.toggle_btn.setChecked(True)
        self.toggle_content(True)

    def collapse(self):
        self.toggle_btn.setChecked(False)
        self.toggle_content(False)
