"""可编辑表格模型，基于 sqlite3 get_connection，支持 CRUD，不依赖 Qt SQL。"""

from datetime import datetime
from pathlib import Path
from typing import Union

from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex

from core.database.connection import get_connection

import logging

logger = logging.getLogger(__name__)


class SqliteEditableTableModel(QAbstractTableModel):
    """基于 sqlite3 get_connection 的可编辑 QAbstractTableModel，支持增删改查。"""

    def __init__(self, table_name: str, database: Union[str, Path], parent=None):
        super().__init__(parent)
        self._table = table_name
        self._database = database
        self._headers: list[str] = []
        self._data: list[list] = []  # 可变行，便于 setData
        self._pk_col_index = 0
        self._pending_deletes: set = set()  # PK 值
        self._pending_insert_indices: set = set()  # 新行的行索引
        self._dirty_rows: set = set()  # 已修改的既有行索引
        self._last_error: str = ""

    def _load_schema(self) -> bool:
        """通过 PRAGMA table_info 加载表结构，返回是否成功。"""
        try:
            with get_connection(self._database, readonly=True) as conn:
                cur = conn.execute(f"PRAGMA table_info({self._table})")
                rows = cur.fetchall()
            if not rows:
                logger.warning("表 %s 无列信息", self._table)
                return False
            self._headers = [r[1] for r in rows]
            # 主键列：第一列（通常为 *_id）
            self._pk_col_index = 0
            return True
        except Exception as e:
            logger.exception("加载表结构失败 %s: %s", self._table, e)
            return False

    def _get_default_for_column(self, col_index: int) -> object:
        """根据列名返回合理的默认值（用于新行）。"""
        if col_index >= len(self._headers):
            return None
        name = self._headers[col_index].lower()
        if name.endswith("_id") and "id" in name:
            return None  # 主键由 DB 生成
        if "rating" in name:
            return 1
        if "create_time" in name or "update_time" in name:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return None

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
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == self._pk_col_index:
            return base
        return base | Qt.ItemFlag.ItemIsEditable

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if role != Qt.ItemDataRole.EditRole:
            return False
        row, col = index.row(), index.column()
        if 0 <= row < len(self._data) and 0 <= col < len(self._headers):
            if col == self._pk_col_index:
                return False
            self._data[row][col] = value
            if row not in self._pending_insert_indices:
                self._dirty_rows.add(row)
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def insertRow(self, row: int, parent: QModelIndex = QModelIndex()) -> bool:
        if row < 0 or row > len(self._data):
            return False
        new_row = [self._get_default_for_column(c) for c in range(len(self._headers))]
        self.beginInsertRows(parent, row, row)
        self._data.insert(row, new_row)
        self._pending_insert_indices.add(row)
        self.endInsertRows()
        return True

    def removeRow(self, row: int, parent: QModelIndex = QModelIndex()) -> bool:
        if row < 0 or row >= len(self._data):
            return False
        pk_val = self._data[row][self._pk_col_index]
        if pk_val is not None and pk_val != "":
            self._pending_deletes.add(pk_val)
        self._pending_insert_indices.discard(row)
        self._dirty_rows.discard(row)
        self.beginRemoveRows(parent, row, row)
        del self._data[row]
        self.endRemoveRows()
        # 删除后，后续行的索引变化，需更新追踪集合
        self._pending_insert_indices = {i if i < row else i - 1 for i in self._pending_insert_indices}
        self._dirty_rows = {i if i < row else i - 1 for i in self._dirty_rows}
        return True

    def refresh(self) -> bool:
        """从数据库重新加载数据，清空待提交状态。"""
        if not self._load_schema():
            return False
        try:
            with get_connection(self._database, readonly=True) as conn:
                cur = conn.execute(f"SELECT * FROM {self._table}")
                rows = cur.fetchall()
            self.beginResetModel()
            self._data = [list(r) for r in rows]
            self._pending_deletes.clear()
            self._pending_insert_indices.clear()
            self._dirty_rows.clear()
            self.endResetModel()
            self._last_error = ""
            return True
        except Exception as e:
            self._last_error = str(e)
            logger.exception("SqliteEditableTableModel.refresh 失败: %s", e)
            return False

    def submitAll(self) -> bool:
        """将待提交的增删改写入数据库，在单一事务中执行。"""
        if not self._pending_deletes and not self._dirty_rows and not self._pending_insert_indices:
            return True
        try:
            with get_connection(self._database, readonly=False) as conn:
                cur = conn.cursor()
                pk_col = self._headers[self._pk_col_index]

                # 1. DELETE
                for pk in self._pending_deletes:
                    cur.execute(f"DELETE FROM {self._table} WHERE {pk_col}=?", (pk,))

                # 2. UPDATE
                for row_idx in self._dirty_rows:
                    if row_idx >= len(self._data):
                        continue
                    row = self._data[row_idx]
                    pk_val = row[self._pk_col_index]
                    if pk_val is None:
                        continue
                    set_parts = []
                    params = []
                    for c, col in enumerate(self._headers):
                        if c == self._pk_col_index:
                            continue
                        set_parts.append(f"{col}=?")
                        params.append(row[c])
                    params.append(pk_val)
                    cur.execute(
                        f"UPDATE {self._table} SET {', '.join(set_parts)} WHERE {pk_col}=?",
                        params,
                    )

                # 3. INSERT（排除主键列，由 DB 生成）
                non_pk_cols = [c for i, c in enumerate(self._headers) if i != self._pk_col_index]
                placeholders = ", ".join("?" * len(non_pk_cols))
                cols_str = ", ".join(non_pk_cols)
                for row_idx in sorted(self._pending_insert_indices):
                    if row_idx >= len(self._data):
                        continue
                    row = self._data[row_idx]
                    vals = [row[i] for i in range(len(self._headers)) if i != self._pk_col_index]
                    cur.execute(
                        f"INSERT INTO {self._table} ({cols_str}) VALUES ({placeholders})",
                        vals,
                    )

                conn.commit()
            self._pending_deletes.clear()
            self._dirty_rows.clear()
            self._pending_insert_indices.clear()
            self._last_error = ""
            self.refresh()
            return True
        except Exception as e:
            self._last_error = str(e)
            logger.exception("SqliteEditableTableModel.submitAll 失败: %s", e)
            return False

    def lastError(self):
        """兼容 QSqlTableModel 的 lastError 接口，返回带 text() 方法的对象。"""
        class Err:
            def __init__(self, msg):
                self._msg = msg

            def text(self):
                return self._msg

        return Err(self._last_error)

    def revertAll(self) -> None:
        """丢弃未保存的修改，重新从数据库加载。"""
        self.refresh()
