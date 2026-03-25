from PySide6.QtWidgets import QTableView, QVBoxLayout, QHBoxLayout, QMessageBox, QAbstractItemView, QFileDialog
from PySide6.QtCore import Slot
import logging

from config import DATABASE, PRIVATE_DATABASE
from ui.basic import ModelSearch
from ui.base.SqliteEditableTableModel import SqliteEditableTableModel
from darkeye_ui import LazyWidget
from darkeye_ui.components.token_table_view import TokenTableView
from darkeye_ui.components.button import Button
from darkeye_ui.components.input import LineEdit
from darkeye_ui.components.combo_box import ComboBox
from darkeye_ui.components.label import Label

class ManagementTable(LazyWidget):
    """综合管理表格的页面"""
    def __init__(self, parent=None):
        super().__init__(parent)

    def _lazy_load(self):
        logging.info("----------综合管理页面----------")
        self.init_ui()

        self.signal_connect()

        self.config()

    def config(self):
        """配置 model 与 view"""
        table_name = self.tableCombo.currentText()
        db_path = DATABASE if table_name == "label" else PRIVATE_DATABASE
        self.model = SqliteEditableTableModel(table_name, db_path, self)
        if not self.model.refresh():
            QMessageBox.critical(self, "错误", f"加载表 {table_name} 失败: {self.model.lastError().text()}")
            return

        self.view.setModel(self.model)
        self.view.setColumnHidden(0, True)  # 隐藏 ID 列（主键）
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.view.setSelectionBehavior(QTableView.SelectRows)
        self.searchWidget.set_model_view(self.model, self.view)

    def init_ui(self):
        self.view = TokenTableView()
        self.tableCombo=ComboBox()
        self.tableCombo.addItems(["love_making","masturbation","sexual_arousal"])
        self.tableCombo.currentTextChanged.connect(self.on_table_changed)

        # 按钮
        self.btn_add = Button("新增行")
        self.btn_delete = Button("删除行")
        self.btn_save = Button("保存修改")
        self.btn_revert = Button("撤销修改")
        self.btn_refresh=Button("刷新数据")
        self.export_csv_button = Button("导出为 CSV")

        # 布局
        button_layout = QHBoxLayout()
        button_layout.addWidget(Label("选择表:"))
        button_layout.addWidget(self.tableCombo)
        button_layout.addWidget(self.btn_add)
        button_layout.addWidget(self.btn_delete)
        button_layout.addWidget(self.btn_save)
        button_layout.addWidget(self.btn_revert)
        button_layout.addWidget(self.btn_refresh)
        button_layout.addWidget(self.export_csv_button)
        button_layout.addStretch()

        self.serial_number=LineEdit()
        self.studio=ComboBox()

        self.searchWidget=ModelSearch()

        layout = QVBoxLayout(self)
        layout.addLayout(button_layout)
        layout.addWidget(self.view)
        layout.addWidget(self.searchWidget)
        

    def on_table_changed(self, table_name):
        """切换表"""
        logging.debug(f"切换到表: {table_name}")
        db_path = DATABASE if table_name == "label" else PRIVATE_DATABASE
        self.model = SqliteEditableTableModel(table_name, db_path, self)
        if not self.model.refresh():
            QMessageBox.critical(self, "错误", f"加载表 {table_name} 失败: {self.model.lastError().text()}")
            return

        self.view.setModel(self.model)
        self.view.setColumnHidden(0, True)  # 隐藏 ID 列（主键）
        self.searchWidget.set_model_view(self.model, self.view)

    def signal_connect(self):
        # 信号连接
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.export_csv_button.clicked.connect(self.export_to_csv)
        self.btn_add.clicked.connect(self.add_row)
        self.btn_delete.clicked.connect(self.delete_row)
        self.btn_save.clicked.connect(self.save_changes)
        self.btn_revert.clicked.connect(self.revert_changes)


    def get_current_model_and_view(self):
        """获取当前活动的模型和视图"""
        return self.model, self.view

    
    @Slot()
    def refresh_data(self):
        """刷新数据"""
        model, view = self.get_current_model_and_view()
        if model and view:
            if not model.refresh():
                QMessageBox.critical(self, "刷新错误", f"刷新数据失败: {model.lastError().text()}")
                return
            view.setModel(model)
            logging.info("数据已刷新")

    @Slot()
    def export_to_csv(self):
        # 弹出文件对话框，让用户选择保存位置
        model, view = self.get_current_model_and_view()
        from utils.utils import export_view_to_csv
        file_path, _ = QFileDialog.getSaveFileName(self, "保存为 CSV 文件", "", "CSV Files (*.csv)")
        
        if file_path:
            # 确保文件名以 .csv 结尾
            if not file_path.endswith('.csv'):
                file_path += '.csv'
            
            # 调用导出函数
            export_view_to_csv(view, file_path)

    @Slot()
    def add_row(self):
        """新增一行"""
        model, view = self.get_current_model_and_view()

        if model and view:
            row = model.rowCount()
            model.insertRow(row)
            # 可选：初始化部分字段
            #for i, value in enumerate(default):
            #    model.setData(model.index(row, i+1), value)
            view.selectRow(row)
            # 滚动到最后一行
            view.scrollToBottom()  # 滚动到底

    @Slot()
    def delete_row(self):
        """删除选中的行"""
        model, view = self.get_current_model_and_view()
        if model and view:
            selected = view.selectionModel().selectedRows()
            if not selected:
                QMessageBox.warning(self, "提示", "请先选择要删除的行")
                return
            for index in selected:
                model.removeRow(index.row())

    @Slot()
    def save_changes(self):
        """保存修改到数据库"""
        model, view = self.get_current_model_and_view()
        if model and view:
            if not model.submitAll():
                QMessageBox.critical(self, "错误", f"保存失败: {model.lastError().text()}")
            else:
                QMessageBox.information(self, "提示", "保存成功")

    @Slot()
    def revert_changes(self):
        """撤销未保存的修改"""
        model, view = self.get_current_model_and_view()
        if model and view:
            model.revertAll()
            QMessageBox.information(self, "提示", "已撤销修改")
