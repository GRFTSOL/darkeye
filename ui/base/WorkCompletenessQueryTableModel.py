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
