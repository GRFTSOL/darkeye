# darkeye_ui/components/combo_box.py - 设计系统下拉框，样式由 mymain.qss + 令牌驱动
from PySide6.QtWidgets import QComboBox


class ComboBox(QComboBox):
    """可复用下拉框，通过 objectName=DesignComboBox 由 QSS 令牌驱动样式。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DesignComboBox")
        # 弹出框内的列表在 Qt 中处于独立窗口，父选择器 QComboBox QAbstractItemView 无法匹配，
        # 因此给 view 设置 objectName，由 QSS 中 QAbstractItemView#DesignComboBoxPopup 单独样式化。
        self.view().setObjectName("DesignComboBoxPopup")
