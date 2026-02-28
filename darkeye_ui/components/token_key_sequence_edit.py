# darkeye_ui/components/token_key_sequence_edit.py - 设计系统快捷键编辑框，样式由 mymain.qss + 令牌驱动
from PySide6.QtWidgets import QKeySequenceEdit, QLineEdit


class TokenKeySequenceEdit(QKeySequenceEdit):
    """可复用快捷键编辑框（QKeySequenceEdit），通过 objectName=DesignKeySequenceEdit 由 QSS 令牌驱动样式，随主题切换变色。
    QKeySequenceEdit 内部使用 QLineEdit 显示内容，需给子控件设置 objectName 以便 QSS 正确匹配。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DesignKeySequenceEdit")
        # 内部 QLineEdit 默认 objectName=qt_keysequenceedit_lineedit，改为令牌名以便 QSS 精确匹配
        for child in self.findChildren(QLineEdit):
            child.setObjectName("DesignKeySequenceEditLineEdit")
