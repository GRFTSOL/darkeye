import logging

from PySide6.QtWidgets import QVBoxLayout, QWidget
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon

from config import ICONS_PATH, HELP_MD_PATH
from darkeye_ui.components.input import TextEdit


class HelpPage(QWidget):
    # 帮助窗口
    success = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("帮助")
        self.setWindowIcon(QIcon(str(ICONS_PATH / "circle-question-mark.png")))

        layout = QVBoxLayout(self)
        self._text = TextEdit()
        self._text.setReadOnly(True)
        layout.addWidget(self._text)

        if HELP_MD_PATH.is_file():
            try:
                text = HELP_MD_PATH.read_text(encoding="utf-8")
                self._text.setMarkdown(text)
            except Exception:
                logging.exception("HelpPage: 读取帮助文档失败 path=%s", HELP_MD_PATH)
                self._text.setPlainText("帮助文件无法读取。")
        else:
            self._text.setPlainText("帮助文件不存在或无法读取。")
