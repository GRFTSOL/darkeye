# ui/components/transparent_widget.py - 仅当层背景透明的容器组件
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget


class TransparentWidget(QWidget):
    """背景透明仅影响本层的容器组件。

    本控件自身不绘制背景，透出下层内容；子控件不受影响，可照常使用不透明背景。
    适用于浮层、遮罩、叠加面板等需要“只让这一层透明”的场景。

    注意：透出的是父控件或下层兄弟控件。若父控件会填充背景，需在父控件上同样
    设置 WA_TranslucentBackground + setAutoFillBackground(False)，才能透出更下层。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setObjectName("TransparentWidget")
        # 部分平台/风格仍会填充，用 QSS 再强制一次
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("TransparentWidget { background: transparent; }")
