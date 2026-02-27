from PySide6.QtWidgets import QTableView, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox,QAbstractItemView,QDataWidgetMapper,QFormLayout,QLineEdit,QComboBox,QLabel,QFileDialog
from PySide6.QtCore import Slot,Qt
from PySide6.QtSql import QSqlRelation,QSqlRelationalTableModel,QSqlRelationalDelegate,QSqlQueryModel,QSqlQuery,QSqlDatabase
import logging

from config import BASE_DIR,DATABASE,INI_FILE
from ui.basic import ModelSearch
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
        '''配置model与view'''
        # 获取数据库连接
        db_public = QSqlDatabase.database("public")
        if not db_public.isValid():
            QMessageBox.critical(self, "错误", "无法获取数据库连接")
            return

        # 创建模型
        self.model = QSqlQueryModel(self)

        # 创建带有数据库连接的查询（同时保存 SQL，供导出使用）
        self.query_sql = "SELECT * FROM v_work_all_info"
        self.query = QSqlQuery(db_public)  # 使用指定的数据库连接
        self.query.prepare(self.query_sql)
        
        # 执行查询并设置到模型
        if not self.query.exec():
            QMessageBox.critical(self, "查询错误", f"执行查询失败: {self.query.lastError().text()}")
            return
            
        self.model.setQuery(self.query)

        # 设置表头
        self.model.setHeaderData(0, Qt.Horizontal, "ID")
        self.model.setHeaderData(1, Qt.Horizontal, "番号")
        self.model.setHeaderData(2, Qt.Horizontal, "导演")

        # 视图设置
        self.view.setModel(self.model)
        self.view.setColumnHidden(0, True)  # 隐藏 ID 列（主键）
        self.view.setItemDelegate(QSqlRelationalDelegate(self.view))#这样会产生下拉框


        self.searchWidget.set_model_view(self.model,self.view)#搜索框连接功能

    def init_ui(self):
        self.view = TokenTableView()
        # 按钮
        self.btn_refresh=Button("刷新数据")
        export_csv_button = Button("导出为 CSV")
        export_csv_button.clicked.connect(self.export_to_csv)
        # 布局
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.btn_refresh)
        button_layout.addWidget(export_csv_button)

        self.serial_number=LineEdit()
        self.studio=ComboBox()

        self.searchWidget=ModelSearch()

        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        layout.addWidget(self.searchWidget)
        layout.addLayout(button_layout)
        
    def signal_connect(self):
        # 信号连接
        self.btn_refresh.clicked.connect(self.refresh_data)

    @Slot()
    def refresh_data(self):
        """刷新数据方法"""
        if not self.query.exec():
            QMessageBox.critical(self, "查询错误", f"刷新数据失败: {self.query.lastError().text()}")
            return
            
        self.model.setQuery(self.query)
        self.view.setModel(self.model)
        logging.info("数据已刷新")

    @Slot()
    def export_to_csv(self):
        """封装为：传入 SQL，用 sqlite 查询并写入 CSV。"""
        from utils.utils import export_sql_to_csv

        # 1. 选择保存路径
        file_path, _ = QFileDialog.getSaveFileName(self, "保存为 CSV 文件", "", "CSV Files (*.csv)")
        if not file_path:
            return

        # 确保文件名以 .csv 结尾
        if not file_path.endswith('.csv'):
            file_path += '.csv'

        # 2. 使用 config 中的公共数据库文件，配合当前页面的基础 SQL 导出
        base_sql = getattr(self, "query_sql", "SELECT * FROM v_work_all_info")

        from config import DATABASE
        ok = export_sql_to_csv(base_sql, file_path, DATABASE)

        if ok:
            QMessageBox.information(self, "导出成功", f"已根据 SQL 导出所有数据到：\n{file_path}\n用 Excel 打开时请使用 UTF-8 导入，否则会出现乱码。")
        else:
            QMessageBox.critical(self, "导出失败", "导出过程中发生错误，请查看日志。")
