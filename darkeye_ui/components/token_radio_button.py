# darkeye_ui/components/token_radio_button.py - 设计系统单选按钮，样式由 mymain.qss + 令牌驱动
from PySide6.QtWidgets import QRadioButton


class TokenRadioButton(QRadioButton):
    """可复用单选按钮，通过 objectName=DesignRadioButton 由 QSS 令牌驱动样式，随主题切换变色。"""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("DesignRadioButton")
