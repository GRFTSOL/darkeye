"""ComboBox 委托，用于 maker_id 列与 studio 控件。显示 cn_name，存储 maker_id。"""

from pathlib import Path
from typing import Union

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from ui.base.SqliteQueryTableModel import SqliteQueryTableModel

from darkeye_ui.components.combo_box import ComboBox
from darkeye_ui.components.input import LineEdit


class MakerComboDelegate(QStyledItemDelegate):
    """用于 maker_id 列的委托：表格中显示 ComboBox 编辑，表单中正确读写 maker_id。"""

    def __init__(self, parent: QWidget, database: Union[str, Path], maker_col_index: int = 2):
        super().__init__(parent)
        self._database = database
        self._maker_col_index = maker_col_index
        self._maker_model: SqliteQueryTableModel | None = None

    def _get_maker_model(self) -> SqliteQueryTableModel:
        if self._maker_model is None:
            self._maker_model = SqliteQueryTableModel(
                "SELECT maker_id, cn_name FROM maker", self._database
            )
            self._maker_model.refresh()
        return self._maker_model

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        if index.column() == self._maker_col_index:
            editor = ComboBox(parent)
            model = self._get_maker_model()
            editor.setModel(model)
            editor.setModelColumn(1)  # 显示 cn_name
            return editor
        return LineEdit(parent)

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        if isinstance(editor, QComboBox):
            maker_id = index.data(Qt.ItemDataRole.EditRole)
            if maker_id is not None and maker_id != "":
                maker_id_str = str(maker_id).strip()
            else:
                maker_id_str = None
            combo_model = editor.model()
            if combo_model and maker_id_str is not None:
                for row in range(combo_model.rowCount()):
                    row_val = combo_model.data(combo_model.index(row, 0), Qt.ItemDataRole.EditRole)
                    if row_val is not None and str(row_val).strip() == maker_id_str:
                        editor.setCurrentIndex(row)
                        return
            editor.setCurrentIndex(-1)
        elif isinstance(editor, QLineEdit):
            editor.setText(str(index.data(Qt.ItemDataRole.EditRole) or ""))

    def setModelData(self, editor: QWidget, model, index: QModelIndex) -> None:
        if isinstance(editor, QComboBox):
            combo_model = editor.model()
            if combo_model and editor.currentIndex() >= 0:
                row_idx = editor.currentIndex()
                maker_id = combo_model.data(combo_model.index(row_idx, 0), Qt.ItemDataRole.EditRole)
                model.setData(index, maker_id, Qt.ItemDataRole.EditRole)
        elif isinstance(editor, QLineEdit):
            model.setData(index, editor.text(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        margin = 0
        rect = option.rect.adjusted(margin, margin, -margin, -margin)
        editor.setGeometry(rect)

    def refresh_maker_model(self) -> None:
        """刷新 maker 下拉数据，供外部在刷新时调用。"""
        if self._maker_model:
            self._maker_model.refresh()
