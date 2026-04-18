"""作品汇总专用表格模型：完整度列显示方格 bit 串，排序按分值。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Union

from PySide6.QtCore import QModelIndex, Qt

from .SqliteQueryTableModel import SqliteQueryTableModel


class WorkCompletenessQueryTableModel(SqliteQueryTableModel):
    def __init__(
        self,
        sql: str,
        database: Union[str, Path],
        *,
        bits_column: str = "completeness_bits",
        score_column: str = "completeness_score",
        parent=None,
    ) -> None:
        super().__init__(sql, database, parent)
        self._bits_column_name = bits_column
        self._score_column_name = score_column
        self._bits_col_idx = -1
        self._score_col_idx = -1

    def refresh(self) -> bool:
        ok = super().refresh()
        if ok:
            self._bits_col_idx = self._header_index(self._bits_column_name)
            self._score_col_idx = self._header_index(self._score_column_name)
        return ok

    def data(self, index: QModelIndex, role: int):
        if role == Qt.ItemDataRole.UserRole and self._is_bits_col(index.column()):
            score = self._cell_value(index.row(), self._score_col_idx)
            return self._score_value(score)
        return super().data(index, role)

    def sort(
        self,
        column: int,
        order: Qt.SortOrder = Qt.SortOrder.AscendingOrder,
    ) -> None:
        if not self._is_bits_col(column):
            super().sort(column, order)
            return

        reverse = order == Qt.SortOrder.DescendingOrder
        self.layoutAboutToBeChanged.emit()
        self._data.sort(
            key=lambda row: (
                self._score_value(row[self._score_col_idx] if self._score_col_idx >= 0 else None),
                self._build_sort_key(row[self._bits_col_idx] if self._bits_col_idx >= 0 else None),
            ),
            reverse=reverse,
        )
        self.layoutChanged.emit()

    def _header_index(self, name: str) -> int:
        try:
            return self._headers.index(name)
        except ValueError:
            return -1

    def _is_bits_col(self, column: int) -> bool:
        return column >= 0 and column == self._bits_col_idx

    def _cell_value(self, row: int, col: int) -> Any:
        if row < 0 or col < 0:
            return None
        if row >= len(self._data):
            return None
        if col >= len(self._data[row]):
            return None
        return self._data[row][col]

    @staticmethod
    def _score_value(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return -1


class WorkSummaryQueryTableModel(WorkCompletenessQueryTableModel):
    """作品汇总表：在 SQL 结果左侧增加虚拟「编辑」列；其余列与原查询一致。"""

    SERIAL_COLUMN = "serial_number"
    EDIT_HEADER = "编辑"

    def __init__(
        self,
        sql: str,
        database: Union[str, Path],
        *,
        bits_column: str = "completeness_bits",
        score_column: str = "completeness_score",
        parent=None,
    ) -> None:
        super().__init__(
            sql, database, bits_column=bits_column, score_column=score_column, parent=parent
        )
        self._serial_col_idx = -1

    def refresh(self) -> bool:
        ok = super().refresh()
        if ok:
            self._serial_col_idx = self._header_index(self.SERIAL_COLUMN)
        else:
            self._serial_col_idx = -1
        return ok

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return super().columnCount(parent) + 1

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if orientation == Qt.Orientation.Horizontal:
            if section == 0:
                if role == Qt.ItemDataRole.DisplayRole:
                    return self.EDIT_HEADER
                return None
            return super().headerData(section - 1, orientation, role)
        return super().headerData(section, orientation, role)

    def data(self, index: QModelIndex, role: int):
        if index.column() == 0:
            if role == Qt.ItemDataRole.DisplayRole:
                return ""
            if role == Qt.ItemDataRole.UserRole:
                return self._serial_text(index.row())
            if role == Qt.ItemDataRole.ToolTipRole:
                sn = self._serial_text(index.row())
                return f"编辑作品：{sn}" if sn else ""
            return None
        inner = self.index(index.row(), index.column() - 1)
        return super().data(inner, role)

    def flags(self, index: QModelIndex):
        if index.column() == 0:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        return super().flags(self.index(index.row(), index.column() - 1))

    def sort(
        self,
        column: int,
        order: Qt.SortOrder = Qt.SortOrder.AscendingOrder,
    ) -> None:
        if column == 0:
            return
        super().sort(column - 1, order)

    def _serial_text(self, row: int) -> str:
        if self._serial_col_idx < 0:
            return ""
        raw = self._cell_value(row, self._serial_col_idx)
        return "" if raw is None else str(raw).strip()
