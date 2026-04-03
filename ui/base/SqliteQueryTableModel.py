"""只读表格模型，从 sqlite3 通过 get_connection 加载数据，不依赖 Qt SQL。"""

from datetime import date, datetime
from pathlib import Path
from typing import Any, Union

from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex

from core.database.connection import get_connection

import logging

logger = logging.getLogger(__name__)


class SqliteQueryTableModel(QAbstractTableModel):
    """基于 sqlite3 get_connection 的只读 QAbstractTableModel。"""

    def __init__(self, sql: str, database: Union[str, Path], parent=None):
        super().__init__(parent)
        self._sql = sql
        self._database = database
        self._headers: list[str] = []
        self._data: list[tuple] = []

    def data(self, index: QModelIndex, role: int):
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            row, col = index.row(), index.column()
            if 0 <= row < len(self._data) and 0 <= col < len(self._headers):
                val = self._data[row][col]
                return "" if val is None else str(val)
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if 0 <= section < len(self._headers):
                    return self._headers[section]
            else:
                return str(section + 1)
        return None

    def flags(self, index: QModelIndex):
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def sort(
        self,
        column: int,
        order: Qt.SortOrder = Qt.SortOrder.AscendingOrder,
    ) -> None:
        """按指定列对当前内存数据排序。"""
        if not 0 <= column < len(self._headers):
            return

        reverse = order == Qt.SortOrder.DescendingOrder
        self.layoutAboutToBeChanged.emit()
        self._data.sort(
            key=lambda row: self._build_sort_key(row[column] if column < len(row) else None),
            reverse=reverse,
        )
        self.layoutChanged.emit()

    @staticmethod
    def _build_sort_key(value: Any) -> tuple[int, Any]:
        """构造稳定排序键，尽量保持数字/日期的自然顺序，空值排到最后。"""
        if value is None:
            return (3, "")
        if isinstance(value, (int, float)):
            return (0, value)
        if isinstance(value, (date, datetime)):
            return (1, value)
        return (2, str(value).casefold())

    def refresh(self) -> bool:
        """重新执行 SQL 并刷新数据。成功返回 True，失败返回 False。"""
        try:
            with get_connection(self._database, readonly=True) as conn:
                cur = conn.execute(self._sql)
                rows = cur.fetchall()
                desc = cur.description
                headers = [d[0] for d in (desc or [])]

            self.beginResetModel()
            self._headers = headers
            self._data = rows
            self.endResetModel()
            return True
        except Exception as e:
            logger.exception("SqliteQueryTableModel.refresh 失败: %s", e)
            return False
