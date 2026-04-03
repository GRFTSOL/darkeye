from PySide6.QtWidgets import QPushButton, QApplication, QMainWindow
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtCore import QSize, Signal, Qt
from config import ICONS_PATH
from utils.image import create_colored_icon


class StateToggleButton(QPushButton):
    stateChanged = Signal(bool)

    def __init__(
        self,
        state1_icon: str = "arrow-up.png",
        state1_color="#AAAAAA",
        state2_icon: str = "arrow-up.png",
        state2_color="#FF0000",
        iconsize=24,
        outsize=24,
        hoverable=True,
        parent=None,
    ):
        super().__init__(parent)
        self._state = False  # False: 状态1, True: 状态2

        # 设置两种状态的图标
        self.icon_state1 = create_colored_icon(
            str(ICONS_PATH / state1_icon), state1_color
        )
        self.icon_state2 = create_colored_icon(
            str(ICONS_PATH / state2_icon), state2_color
        )

        self.outsize = outsize
        # 初始图标
        self.setIcon(self.icon_state1)
        self.setIconSize(QSize(iconsize, iconsize))
        self.setFixedSize(outsize, outsize)

        if hoverable:
            self.setStyleSheet(
                """
            QPushButton {
                border: none;
                background: transparent;
                border-radius: 6px;   /* 圆角半径 */
            }
            QPushButton:hover {
                background-color: lightgray; /* 悬停时灰色背景 */
            }
            """
            )
        else:
            self.setStyleSheet(
                """
            QPushButton {
                border: none;
                background: transparent;
                border-radius: 6px;   /* 圆角半径 */
            }
            """
            )
        # 连接点击事件
        self.clicked.connect(self.toggle_state)

    def toggle_state(self):
        """切换状态"""
        self._state = not self._state
        if self._state:
            self.setIcon(self.icon_state2)
            self.setToolTip("状态2: 已激活")
        else:
            self.setIcon(self.icon_state1)
            self.setToolTip("状态1: 默认")

        # 发出状态变化信号
        self.stateChanged.emit(self._state)

    def set_state(self, state):
        """设置特定状态"""
        if state != self._state:
            self._state = state
            self.setIcon(self.icon_state2 if state else self.icon_state1)

    def get_state(self):
        """获取当前状态"""
        return self._state

    def sizeHint(self):
        # 强制返回你设定的尺寸，不给系统样式“指手画脚”的机会
        # 这是一个坑如果不设置这个，会至少返回(38,32)
        return QSize(self.outsize, self.outsize)
