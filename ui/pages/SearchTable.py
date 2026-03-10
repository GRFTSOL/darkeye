from PySide6.QtWidgets import QTableView, QVBoxLayout, QHBoxLayout, QMessageBox, QFileDialog
from PySide6.QtCore import Slot
import logging

from config import BASE_DIR, DATABASE, INI_FILE
from ui.basic import ModelSearch
from ui.base.SqliteQueryTableModel import SqliteQueryTableModel
from darkeye_ui import LazyWidget
from darkeye_ui.components.token_table_view import TokenTableView
from darkeye_ui.components.button import Button
from darkeye_ui.components.input import LineEdit
from darkeye_ui.components.combo_box import ComboBox


class SearchTable(LazyWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

    def _lazy_load(self):
        logging.info("----------汇总查询页面----------")
        self.init_ui()

        self.signal_connect()

        self.config()

    def config(self):
        """配置 model 与 view"""
        self.query_sql = "SELECT * FROM v_work_all_info"
        self.model = SqliteQueryTableModel(self.query_sql, DATABASE, self)

        if not self.model.refresh():
            QMessageBox.critical(self, "错误", "无法加载数据，请查看日志。")
            return

        self.view.setModel(self.model)
        self.view.setColumnHidden(0, True)  # 隐藏 ID 列（主键）

        self.searchWidget.set_model_view(self.model, self.view)

    def init_ui(self):
        self.view = TokenTableView()
        self.btn_refresh = Button("刷新数据")
        export_csv_button = Button("导出为 CSV")
        export_csv_button.clicked.connect(self.export_to_csv)

        button_layout = QHBoxLayout()
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

    @Slot()
    def refresh_data(self):
        """刷新数据"""
        if not self.model.refresh():
            QMessageBox.critical(self, "刷新错误", "刷新数据失败，请查看日志。")
            return
        logging.info("数据已刷新")

    @Slot()
    def export_to_csv(self):
        """封装为：传入 SQL，用 sqlite 查询并写入 CSV。"""
        from utils.utils import export_sql_to_csv

        file_path, _ = QFileDialog.getSaveFileName(self, "保存为 CSV 文件", "", "CSV Files (*.csv)")
        if not file_path:
            return

        if not file_path.endswith(".csv"):
            file_path += ".csv"

        base_sql = getattr(self, "query_sql", "SELECT * FROM v_work_all_info")
        ok = export_sql_to_csv(base_sql, file_path, DATABASE)

        if ok:
            QMessageBox.information(
                self,
                "导出成功",
                f"已根据 SQL 导出所有数据到：\n{file_path}\n用 Excel 打开时请使用 UTF-8 导入，否则会出现乱码。",
            )
        else:
            QMessageBox.critical(self, "导出失败", "导出过程中发生错误，请查看日志。")
