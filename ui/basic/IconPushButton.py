from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
import logging
from config import ICONS_PATH
from utils.image import create_colored_icon, create_colored_icon_vector


class IconPushButton(QPushButton):
    """专门的只有icon的PushButton"""

    def __init__(
        self,
        iconpath: str = "arrow-up.png",
        iconsize=24,
        outsize=24,
        hoverable=True,
        color="#000000",
        parent=None,
    ):
        super().__init__(parent)
        if iconpath.endswith(".svg"):
            qicon = create_colored_icon_vector(
                str(ICONS_PATH / iconpath), color, iconsize, iconsize
            )
            self.setIcon(qicon)
        else:
            self.setIcon(QIcon(str(ICONS_PATH / iconpath)))
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setIconSize(QSize(iconsize, iconsize))
        self.outsize = outsize  # 保存这个值
        self.setFixedSize(outsize, outsize)

        if hoverable:
            self.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                border-radius: 6px;   /* 圆角半径 */
            }
            QPushButton:hover {
                background-color: lightgray; /* 悬停时灰色背景 */
            }
            """)
        else:
            self.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                border-radius: 6px;   /* 圆角半径 */
            }
            """)

    def set_icon(self, iconpath: str = "arrow-up.png"):
        self.setIcon(QIcon(str(ICONS_PATH / iconpath)))

    def sizeHint(self):
        # 强制返回你设定的尺寸，不给系统样式“指手画脚”的机会
        # 这是一个坑如果不设置这个，会至少返回(38,32)
        return QSize(self.outsize, self.outsize)
