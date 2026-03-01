# darkeye_ui/components/token_date_time_edit.py - 设计系统日期时间选择器，样式由 mymain.qss + 令牌驱动
from PySide6.QtWidgets import QDateTimeEdit


class TokenDateTimeEdit(QDateTimeEdit):
    """可复用日期时间选择器（QDateTimeEdit），通过 objectName=DesignDateTimeEdit 由 QSS 令牌驱动样式，随主题切换变色。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DesignDateTimeEdit")
