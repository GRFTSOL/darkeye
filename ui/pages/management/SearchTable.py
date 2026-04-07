from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QMessageBox, QFileDialog
import logging

from config import DATABASE, SQLPATH
from ui.basic import ModelSearch
from ui.base.SqliteQueryTableModel import SqliteQueryTableModel
from darkeye_ui import LazyWidget
from darkeye_ui.components.token_table_view import TokenTableView
from darkeye_ui.components.button import Button
from darkeye_ui.components.input import LineEdit
from darkeye_ui.components.combo_box import ComboBox
from darkeye_ui.components.label import Label


class SearchTable(LazyWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

    def _lazy_load(self):
        logging.info("----------汇总查询页面----------")
        self.init_ui()

        self.signal_connect()

        self.config()

    def config(self):
        """配置 model 与 view（按当前查询类型加载 SQL）"""
        rel = self.query_combo.currentData()
        if rel:
            self._load_query_from_file(rel)

    def _load_query_from_file(self, rel_name: str) -> bool:
        """读取 SQLPATH 下的查询文件，重建只读 model 并绑定 view / 搜索。"""
        path = Path(SQLPATH) / rel_name
        try:
            self.query_sql = path.read_text(encoding="utf-8")
        except OSError:
            logging.exception("读取 SQL 失败: %s", path)
            QMessageBox.critical(self, "错误", f"无法读取查询文件：\n{path}")
            return False

        model = SqliteQueryTableModel(self.query_sql, DATABASE, self)
        if not model.refresh():
            QMessageBox.critical(self, "错误", "无法加载数据，请查看日志。")
            return False

        self.model = model
        self.view.setModel(self.model)
        self.searchWidget.set_model_view(self.model, self.view)
        return True

    @Slot()
    def _on_query_type_changed(self, _text: str):
        rel = self.query_combo.currentData()
        if rel:
            self._load_query_from_file(rel)

    def init_ui(self):
        self.view = TokenTableView()
        self.view.setSortingEnabled(True)
        self.view.horizontalHeader().setSortIndicatorShown(True)
        self.view.horizontalHeader().setSectionsClickable(True)
        self.btn_refresh = Button("刷新数据")
        export_csv_button = Button("导出为 CSV")
        export_csv_button.clicked.connect(self.export_to_csv)

        self.query_combo = ComboBox()
        self.query_combo.addItem("作品汇总", "work_all_info.sql")
        self.query_combo.addItem("女优汇总", "actress_all_info.sql")
        self.query_combo.addItem("男优汇总", "actor_all_info.sql")

        button_layout = QHBoxLayout()
        button_layout.addWidget(Label("查询类型:"))
        button_layout.addWidget(self.query_combo)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_refresh)
        button_layout.addWidget(export_csv_button)

        self.serial_number = LineEdit()
        self.studio = ComboBox()

        self.searchWidget = ModelSearch()

        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        layout.addWidget(self.searchWidget)
        layout.addLayout(button_layout)

    def signal_connect(self):
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.query_combo.currentTextChanged.connect(self._on_query_type_changed)

    @Slot()
    def refresh_data(self):
        """刷新数据"""
        if not getattr(self, "model", None):
            return
        if not self.model.refresh():
            QMessageBox.critical(self, "刷新错误", "刷新数据失败，请查看日志。")
            return
        self.view.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        logging.info("数据已刷新")

    @Slot()
    def export_to_csv(self):
        """封装为：传入 SQL，用 sqlite 查询并写入 CSV。"""
        from utils.utils import export_sql_to_csv

        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存为 CSV 文件", "", "CSV Files (*.csv)"
        )
        if not file_path:
            return

        if not file_path.endswith(".csv"):
            file_path += ".csv"

        base_sql = self.query_sql
        ok = export_sql_to_csv(base_sql, file_path, DATABASE)

        if ok:
            QMessageBox.information(
                self,
                "导出成功",
                f"已根据 SQL 导出所有数据到：\n{file_path}\n用 Excel 打开时请使用 UTF-8 导入，否则会出现乱码。",
            )
        else:
            QMessageBox.critical(self, "导出失败", "导出过程中发生错误，请查看日志。")
