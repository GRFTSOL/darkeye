from PySide6.QtWidgets import QTableView, QVBoxLayout, QHBoxLayout, QAbstractItemView
from PySide6.QtCore import Slot, Qt
import logging

from config import DATABASE
from ui.basic import ModelSearch
from ui.base.SqliteQueryTableModel import SqliteQueryTableModel
from darkeye_ui import LazyWidget
from controller.MessageService import MessageBoxService
from darkeye_ui.components.token_table_view import TokenTableView
from darkeye_ui.components.button import Button
from darkeye_ui.components.input import LineEdit
from darkeye_ui.components.combo_box import ComboBox

class RecycleBinPage(LazyWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.msg=MessageBoxService(self)


    def _lazy_load(self):
        logging.info("----------作品回收站页面----------")
        self.init_ui()

        self.signal_connect()

        self.config()

    def config(self):
        """配置 model 与 view"""
        self.model = SqliteQueryTableModel("SELECT * FROM work WHERE is_deleted=1", DATABASE, self)
        if not self.model.refresh():
            self.msg.show_critical("错误", "无法加载数据，请查看日志。")
            return

        self.view.setModel(self.model)
        self.view.setColumnHidden(0, True)  # 隐藏 ID 列（主键）
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)  # 整行选择
        self.searchWidget.set_model_view(self.model, self.view)

    def init_ui(self):
        self.view = TokenTableView()
        # 按钮
        self.btn_refresh=Button("刷新数据")
        self.btn_delete=Button("彻底删除")
        self.btn_restore=Button("恢复数据")


        # 布局
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.btn_refresh)
        button_layout.addWidget(self.btn_delete)
        button_layout.addWidget(self.btn_restore)


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
        self.btn_delete.clicked.connect(self.delete)
        self.btn_restore.clicked.connect(self.recover)

    @Slot()
    def refresh_data(self):
        """刷新数据方法"""
        if not self.model.refresh():
            self.msg.show_critical("查询错误", "刷新数据失败，请查看日志。")
            return
        logging.info("数据已刷新")



    @Slot()
    def delete(self):
        """彻底删除数据"""
        selected_indexes = self.view.selectionModel().selectedRows()
        if not selected_indexes:
            self.msg.show_warning("警告", "请先选择要删除的行")
            return

        if not self.msg.ask_yes_no("确认删除", f"确定要彻底删除选中的 {len(selected_indexes)} 行吗？此操作不可撤销。"):
            return

        from core.database.delete import delete_work
        for index in selected_indexes:
            work_id = self.model.data(self.model.index(index.row(), 0), Qt.ItemDataRole.DisplayRole)
            if not delete_work(work_id):
                self.msg.show_critical("错误", f"删除失败:")
                return
        self.refresh_data()
        self.msg.show_info("成功", f"已删除 {len(selected_indexes)} 行数据")

    @Slot()
    def recover(self):
        '''恢复数据'''
        selected_indexes = self.view.selectionModel().selectedRows()
        if not selected_indexes:
            self.msg.show_critical("警告", "请先选择要恢复的行")
            return
        if not self.msg.ask_yes_no("确认恢复", f"确定要恢复选中的 {len(selected_indexes)} 行吗？"):
            return
        from core.database.update import mark_undelete
        for index in selected_indexes:
            work_id = self.model.data(self.model.index(index.row(), 0), Qt.ItemDataRole.DisplayRole)
            if not mark_undelete(work_id):
                self.msg.show_critical("错误", "恢复失败，请查看日志。")
                return
        # 更新模型，刷新界面
        self.refresh_data()
        self.msg.show_info("成功", f"已恢复 {len(selected_indexes)} 行数据")