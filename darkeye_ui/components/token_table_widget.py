# darkeye_ui/components/token_table_widget.py - 设计系统表格控件，样式由 mymain.qss + 令牌驱动
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import QModelIndex
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTableWidget,
    QWidget,
)

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class _TableEditorDelegate(QStyledItemDelegate):
    """缩小编辑框与单元格边缘的间距；不绘制焦点框，避免失去焦点后残留。"""

    def __init__(self, margin: int = 1, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._margin = margin

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        opt = QStyleOptionViewItem(option)
        opt.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter, opt, index)

    def updateEditorGeometry(
        self,
        editor: QWidget,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        rect = option.rect.adjusted(
            self._margin, self._margin, -self._margin, -self._margin
        )
        editor.setGeometry(rect)


class TokenTableWidget(QTableWidget):
    """令牌驱动 TableWidget。

    - 通过 objectName=DesignTableWidget，使样式由 QSS 中的 {{token}} 驱动
    - 可选接入 ThemeManager，在主题切换时自动刷新样式
    - 与 TokenTableView 共享同一套 QSS 规则，保证视觉一致
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        theme_manager: Optional["ThemeManager"] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DesignTableWidget")
        self.setItemDelegate(_TableEditorDelegate(margin=0, parent=self))

        self._theme_manager = theme_manager
        if theme_manager is not None:
            theme_manager.themeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self, *_args) -> None:
        """主题切换时强制重新应用 QSS。"""
        style = self.style()
        style.unpolish(self)
        style.polish(self)
