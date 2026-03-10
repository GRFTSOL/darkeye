# ui/components/input.py - 设计系统单行/多行输入，样式由 mymain.qss + 令牌驱动
from PySide6.QtWidgets import QLineEdit, QPlainTextEdit, QTextEdit


class LineEdit(QLineEdit):
    """可复用单行输入框，通过 objectName=DesignInput 由 QSS 驱动样式。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DesignInput")


class TextEdit(QTextEdit):
    """可复用多行文本框，通过 objectName=DesignTextEdit 由 QSS 驱动样式。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DesignTextEdit")


class PlainTextEdit(QPlainTextEdit):
    """可复用纯文本多行编辑框（QPlainTextEdit），通过 objectName=DesignPlainTextEdit 由 QSS + 令牌驱动样式。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DesignPlainTextEdit")
