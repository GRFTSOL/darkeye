"""汇总查询「作品汇总」首列编辑按钮委托。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QModelIndex, Qt, QSize
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyleOptionButton,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)


class WorkSummaryEditDelegate(QStyledItemDelegate):
    """绘制「编辑」按钮，释放左键时按番号跳转管理页「添加/修改作品」。"""

    _LABEL = "编辑"

    def paint(self, painter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        opt = QStyleOptionButton()
        margin = 4
        opt.rect = option.rect.adjusted(margin, margin, -margin, -margin)
        opt.text = self._LABEL
        opt.state = QStyle.StateFlag.State_Enabled
        if option.state & QStyle.StateFlag.State_MouseOver:
            opt.state |= QStyle.StateFlag.State_MouseOver
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        QApplication.style().drawControl(QStyle.ControlElement.CE_PushButton, opt, painter)

    def editorEvent(self, event, model, option, index: QModelIndex) -> bool:
        if event.type() == QEvent.Type.MouseButtonRelease:
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            serial = index.data(Qt.ItemDataRole.UserRole)
            if not serial:
                return True
            from ui.navigation.router import Router

            Router.instance().push("database", serial_number=str(serial))
            return True
        return super().editorEvent(event, model, option, index)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        fm = option.fontMetrics
        w = fm.horizontalAdvance(self._LABEL) + 24
        h = max(fm.height() + 10, 24)
        return QSize(w, h)
