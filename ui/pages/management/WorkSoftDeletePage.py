"""未删除作品列表：首列勾选，批量软删除。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

from PySide6.QtCore import QModelIndex, Qt, QTimer, Slot
from PySide6.QtGui import (
    QBrush,
    QColor,
    QKeyEvent,
    QMouseEvent,
    QPalette,
    QPainter,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
    QVBoxLayout,
)

from config import DATABASE
from controller.global_signal_bus import global_signals
from controller.message_service import MessageBoxService
from core.database.update import mark_delete_many
from darkeye_ui import LazyWidget
from darkeye_ui.components.button import Button
from darkeye_ui.components.token_table_view import TokenTableView
from ui.base.SqliteQueryTableModel import SqliteQueryTableModel
from ui.basic import ModelSearch

# 固定色值，不随 QSS / 主题表色变化（仅「选」列复选框格）。
_CHECKED_CELL_BG = QColor(255, 215, 215)
_CHECKED_CELL_SELECTED_BG = QColor(230, 140, 140)

# 用动态属性提高选择器优先级，压过全局 QTableView#DesignTableView::item 背景，便于 delegate 上色。
_WORK_SOFT_DELETE_TABLE_ITEM_QSS = """
QTableView#DesignTableView[softDeleteWorkTable="true"]::item,
QTableView#DesignTableView[softDeleteWorkTable="true"]::item:alternate,
QTableView#DesignTableView[softDeleteWorkTable="true"]::item:hover:!selected {
    background-color: transparent;
}
QTableView#DesignTableView[softDeleteWorkTable="true"]::item:selected {
    background-color: transparent;
}
"""

# dataChanged 传入空列表在 PySide 中可能不触发刷新，显式列出常见绘制相关 role。
_CHECK_VISUAL_DATA_ROLES = [
    Qt.ItemDataRole.DisplayRole,
    Qt.ItemDataRole.DecorationRole,
    Qt.ItemDataRole.ForegroundRole,
    Qt.ItemDataRole.BackgroundRole,
    Qt.ItemDataRole.CheckStateRole,
]


def _is_check_state_checked(value) -> bool:
    if value is None:
        return False
    if value == Qt.CheckState.Checked:
        return True
    return value == Qt.CheckState.Checked.value


class CheckedRowHighlightDelegate(QStyledItemDelegate):
    """仅首列复选框格：打钩时浅红底；选中该格时略深红（非主题色）。"""

    def initStyleOption(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        super().initStyleOption(option, index)
        if index.column() != 0:
            return
        model = index.model()
        if model is None:
            return
        if not _is_check_state_checked(
            model.data(index, Qt.ItemDataRole.CheckStateRole)
        ):
            return
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        bg = _CHECKED_CELL_SELECTED_BG if selected else _CHECKED_CELL_BG
        option.backgroundBrush = QBrush(bg)
        pal = QPalette(option.palette)
        pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Base, bg)
        pal.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.AlternateBase, bg)
        if selected:
            pal.setColor(
                QPalette.ColorGroup.All,
                QPalette.ColorRole.Highlight,
                _CHECKED_CELL_SELECTED_BG,
            )
            pal.setColor(
                QPalette.ColorGroup.All,
                QPalette.ColorRole.HighlightedText,
                QColor(20, 20, 20),
            )
        option.palette = pal

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        opt = QStyleOptionViewItem(option)
        opt.state &= ~QStyle.StateFlag.State_HasFocus
        if index.column() == 0:
            model = index.model()
            if model is not None and _is_check_state_checked(
                model.data(index, Qt.ItemDataRole.CheckStateRole)
            ):
                sel = bool(opt.state & QStyle.StateFlag.State_Selected)
                bg = _CHECKED_CELL_SELECTED_BG if sel else _CHECKED_CELL_BG
                painter.fillRect(option.rect, bg)
        super().paint(painter, opt, index)

    def updateEditorGeometry(
        self,
        editor,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        editor.setGeometry(option.rect)


class WorkListWithCheckboxesModel(SqliteQueryTableModel):
    """在查询结果前插入一列复选框；勾选状态按 work_id 保存（SQL 首列为 work_id）。"""

    def __init__(self, sql: str, database: Union[str, Path], parent=None):
        super().__init__(sql, database, parent)
        self._checked_work_ids: set[int] = set()

    def checked_work_ids(self) -> set[int]:
        return set(self._checked_work_ids)

    def set_all_check_state(self, checked: bool) -> None:
        """将当前表格中所有行的复选框设为勾选或取消。"""
        if not self._data:
            return
        if checked:
            for row in self._data:
                wid = row[0]
                if wid is not None:
                    self._checked_work_ids.add(int(wid))
        else:
            self._checked_work_ids.clear()
        self._emit_check_state_visual_changed(0, len(self._data) - 1)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        n = len(self._headers)
        return n + 1 if n else 0

    def data(self, index: QModelIndex, role: int):
        row, col = index.row(), index.column()
        if col == 0:
            if role == Qt.ItemDataRole.CheckStateRole:
                if 0 <= row < len(self._data):
                    wid = self._data[row][0]
                    if wid is not None and int(wid) in self._checked_work_ids:
                        return Qt.CheckState.Checked
                    return Qt.CheckState.Unchecked
            return None
        inner_col = col - 1
        if role in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.EditRole,
        ):
            if 0 <= row < len(self._data) and 0 <= inner_col < len(self._headers):
                val = self._data[row][inner_col]
                return "" if val is None else str(val)
        return None

    def _emit_check_state_visual_changed(self, row_first: int, row_last: int) -> None:
        """勾选变化后仅刷新首列复选框格的绘制。"""
        if row_first > row_last:
            return
        row_first = max(0, row_first)
        row_last = min(len(self._data) - 1, row_last)
        if row_first > row_last:
            return
        self.dataChanged.emit(
            self.index(row_first, 0),
            self.index(row_last, 0),
            _CHECK_VISUAL_DATA_ROLES,
        )

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.CheckStateRole or index.column() != 0:
            return False
        row = index.row()
        if not (0 <= row < len(self._data)):
            return False
        wid = self._data[row][0]
        if wid is None:
            return False
        work_id = int(wid)
        # PySide6：value 多为 CheckState 枚举，不可用 int(CheckState)；也可能为底层整型 0/2。
        checked = value == Qt.CheckState.Checked or (
            isinstance(value, int) and value == Qt.CheckState.Checked.value
        )
        if checked:
            self._checked_work_ids.add(work_id)
        else:
            self._checked_work_ids.discard(work_id)
        self._emit_check_state_visual_changed(row, row)
        return True

    def flags(self, index: QModelIndex):
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == 0:
            return base | Qt.ItemFlag.ItemIsUserCheckable
        return base

    def headerData(self, section: int, orientation: Qt.Orientation, role: int):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if section == 0:
                    return "选"
                inner = section - 1
                if 0 <= inner < len(self._headers):
                    return self._headers[inner]
            return str(section + 1)
        return None

    def refresh(self) -> bool:
        ok = super().refresh()
        if ok:
            self._checked_work_ids.clear()
        return ok


class WorkSoftDeleteTableView(TokenTableView):
    """多选后点首列复选框时：在按下时快照选区，避免默认行为先把选区收成单行。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("softDeleteWorkTable", True)
        self.setItemDelegate(CheckedRowHighlightDelegate(parent=self))
        self.setStyleSheet((self.styleSheet() or "") + _WORK_SOFT_DELETE_TABLE_ITEM_QSS)
        self._multi_check_rows: list[int] | None = None
        self._multi_check_anchor: int | None = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._multi_check_rows = None
        self._multi_check_anchor = None
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self.indexAt(event.pos())
            if idx.isValid() and idx.column() == 0:
                sm = self.selectionModel()
                if sm is not None:
                    sel = [x.row() for x in sm.selectedRows()]
                    r = idx.row()
                    if len(sel) > 1 and r in sel:
                        self._multi_check_rows = sel
                        self._multi_check_anchor = r
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space:
            sm = self.selectionModel()
            model = self.model()
            if sm is not None and model is not None:
                cur = sm.currentIndex()
                if not cur.isValid():
                    sel_rows = sm.selectedRows()
                    if sel_rows:
                        cur = sel_rows[0]
                if cur.isValid():
                    row = cur.row()
                    idx0 = model.index(row, 0)
                    if idx0.isValid():
                        state = model.data(idx0, Qt.ItemDataRole.CheckStateRole)
                        if state is not None:
                            checked = _is_check_state_checked(state)
                            new_state = (
                                Qt.CheckState.Unchecked
                                if checked
                                else Qt.CheckState.Checked
                            )
                            sel = [x.row() for x in sm.selectedRows()]
                            if len(sel) > 1 and row in sel:
                                model.setData(
                                    idx0,
                                    new_state,
                                    Qt.ItemDataRole.CheckStateRole,
                                )
                                for r in sel:
                                    if r == row:
                                        continue
                                    j = model.index(r, 0)
                                    model.setData(
                                        j,
                                        new_state,
                                        Qt.ItemDataRole.CheckStateRole,
                                    )
                            else:
                                model.setData(
                                    idx0,
                                    new_state,
                                    Qt.ItemDataRole.CheckStateRole,
                                )
                            event.accept()
                            return
        super().keyPressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        rows = self._multi_check_rows
        anchor = self._multi_check_anchor
        super().mouseReleaseEvent(event)
        if (
            rows is not None
            and anchor is not None
            and event.button() == Qt.MouseButton.LeftButton
        ):
            idx = self.indexAt(event.pos())
            if idx.isValid() and idx.column() == 0 and idx.row() == anchor:

                def _sync() -> None:
                    m = self.model()
                    if m is None:
                        return
                    idx0 = m.index(anchor, 0)
                    if not idx0.isValid():
                        return
                    state = m.data(idx0, Qt.ItemDataRole.CheckStateRole)
                    if state is None:
                        return
                    for r in rows:
                        if r == anchor:
                            continue
                        j = m.index(r, 0)
                        m.setData(j, state, Qt.ItemDataRole.CheckStateRole)

                QTimer.singleShot(0, _sync)
        self._multi_check_rows = None
        self._multi_check_anchor = None


class WorkSoftDeletePage(LazyWidget):
    """批量将作品标记为软删除（进入回收站）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.msg = MessageBoxService(self)

    def _lazy_load(self):
        logging.info("----------作品软删除页面----------")
        self.init_ui()
        self.signal_connect()
        self.config()

    def config(self):
        self.model = WorkListWithCheckboxesModel(
            "SELECT * FROM work WHERE IFNULL(is_deleted, 0) = 0",
            DATABASE,
            self,
        )
        if not self.model.refresh():
            self.msg.show_critical("错误", "无法加载数据，请查看日志。")
            return

        self.view.setModel(self.model)
        self.view.setColumnHidden(1, True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.searchWidget.set_model_view(self.model, self.view)

    def init_ui(self):
        self.view = WorkSoftDeleteTableView()
        self.btn_refresh = Button("刷新数据")
        self.btn_soft_delete = Button("软删除选中")
        self.btn_check_all = Button("全选")
        self.btn_uncheck_all = Button("全不选")

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.btn_refresh)
        button_layout.addWidget(self.btn_soft_delete)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_check_all)
        button_layout.addWidget(self.btn_uncheck_all)

        self.searchWidget = ModelSearch()

        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        layout.addWidget(self.searchWidget)
        layout.addLayout(button_layout)

    def signal_connect(self):
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.btn_soft_delete.clicked.connect(self.soft_delete_checked)
        self.btn_check_all.clicked.connect(self.check_all)
        self.btn_uncheck_all.clicked.connect(self.uncheck_all)

    @Slot()
    def check_all(self) -> None:
        self.model.set_all_check_state(True)

    @Slot()
    def uncheck_all(self) -> None:
        self.model.set_all_check_state(False)

    @Slot()
    def refresh_data(self):
        if not self.model.refresh():
            self.msg.show_critical("查询错误", "刷新数据失败，请查看日志。")
            return
        logging.info("数据已刷新")

    @Slot()
    def soft_delete_checked(self):
        ids = self.model.checked_work_ids()
        if not ids:
            self.msg.show_warning("提示", "请先勾选要软删除的作品")
            return

        n = len(ids)
        if not self.msg.ask_yes_no(
            "确认软删除",
            f"确定将选中的 {n} 部作品移入回收站吗？可在回收站恢复。",
        ):
            return

        if not mark_delete_many(ids):
            self.msg.show_critical("错误", "批量软删除失败，请查看日志。")
            return

        global_signals.workDataChanged.emit()
        self.refresh_data()
        self.msg.show_info("成功", f"已将 {n} 部作品移入回收站")
