from anyio import sleep
from PySide6.QtWidgets import (
    QDialog,QVBoxLayout, QHBoxLayout, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import  Qt
from PySide6.QtGui import QIcon
from config import ICONS_PATH
import logging, re
from controller.MessageService import MessageBoxService
from darkeye_ui.components.button import Button
from darkeye_ui.components.token_table_widget import TokenTableWidget
class AddQuickWork(QDialog):
    # 快速记录作品番号的窗口，能在局外响应
    def __init__(self):
        super().__init__()
        logging.info("----------快速记录作品番号窗口----------")
        self.setWindowTitle("快速记录作品番号(W)")
        self.setWindowIcon(QIcon(str(ICONS_PATH / "film.png")))
        self.setFixedSize(400, 500)
        self.msg = MessageBoxService(self)
        self._sort_ascending = True

        self.init_ui()

    def init_ui(self):
        # 1. 顶部工具栏
        top_layout = QHBoxLayout()
        self.btn_add = Button("添加")
        self.btn_del = Button("删除")
        self.btn_clean = Button("去后缀")
        self.btn_sort = Button("排序")
        
        self.btn_add.clicked.connect(self.add_row)
        self.btn_del.clicked.connect(self.delete_rows)
        self.btn_clean.clicked.connect(self.clean_suffix)
        self.btn_sort.clicked.connect(self.sort_rows)
        
        top_layout.addWidget(self.btn_add)
        top_layout.addWidget(self.btn_del)
        top_layout.addWidget(self.btn_clean)
        top_layout.addWidget(self.btn_sort)

        # 2. 中间列表区域
        self.table = TokenTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["选择", "番号"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        # 3. 底部提交按钮
        self.btn_commit = Button("快速添加")
        self.btn_commit.clicked.connect(self.submit)
        self.btn_commit.setMinimumHeight(40)

        # 总体布局
        main_layout = QVBoxLayout(self)
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.table)
        main_layout.addWidget(self.btn_commit)
        
        # 初始化添加一行
        self.add_row()

    def add_row(self):
        """在表格末尾插入一个空行"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # 第一列：复选框
        chk_item = QTableWidgetItem()
        chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        chk_item.setCheckState(Qt.Checked)
        self.table.setItem(row, 0, chk_item)
        
        # 第二列：文本输入
        text_item = QTableWidgetItem("")
        self.table.setItem(row, 1, text_item)
        
        # 自动聚焦到新行的文本列
        self.table.editItem(text_item)
        self.table.setCurrentItem(text_item)

    def delete_rows(self):
        """删除选中的行（高亮行）"""
        # 获取所有选中的范围
        selected_ranges = self.table.selectedRanges()
        # 倒序删除，避免索引错乱
        rows_to_delete = set()
        for ranges in selected_ranges:
            for row in range(ranges.topRow(), ranges.bottomRow() + 1):
                rows_to_delete.add(row)
        
        for row in sorted(rows_to_delete, reverse=True):
            self.table.removeRow(row)

    def clean_suffix(self):
        """去后缀：处理所有复选框选中的行"""
        # 常见的需要去除的后缀正则，不区分大小写
        suffix_pattern = re.compile(r'(-C|-h|_uncensored|ch|pl)$', re.IGNORECASE)
        
        for row in range(self.table.rowCount()):
            chk_item = self.table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.Checked:
                text_item = self.table.item(row, 1)
                if text_item:
                    original_text = text_item.text().strip()
                    # 正则替换
                    new_text = suffix_pattern.sub('', original_text)
                    if new_text != original_text:
                        text_item.setText(new_text)

    def sort_rows(self):
        """按番号列排序当前所有行（点击在升序/降序间切换）。"""
        rows = []
        for row in range(self.table.rowCount()):
            chk_item = self.table.item(row, 0)
            text_item = self.table.item(row, 1)
            if chk_item is None or text_item is None:
                continue
            rows.append(
                {
                    "checked": chk_item.checkState(),
                    "text": text_item.text(),
                }
            )
        rows.sort(key=lambda r: r["text"].strip().lower(), reverse=not self._sort_ascending)
        self._sort_ascending = not self._sort_ascending

        self.table.setRowCount(0)
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk_item.setCheckState(r["checked"])
            self.table.setItem(row, 0, chk_item)
            text_item = QTableWidgetItem(r["text"])
            self.table.setItem(row, 1, text_item)

    def load_serials(self, serial_list):
        """加载番号列表到表格中"""
        self.table.setRowCount(0)  # 清空现有行
        for serial in serial_list:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # 第一列：复选框
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk_item.setCheckState(Qt.Checked)
            self.table.setItem(row, 0, chk_item)
            
            # 第二列：文本输入
            text_item = QTableWidgetItem(serial)
            self.table.setItem(row, 1, text_item)

    def submit(self):
        """提交：收集所有复选框选中的番号"""
        serial_list = []
        for row in range(self.table.rowCount()):
            chk_item = self.table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.Checked:
                text_item = self.table.item(row, 1)
                if text_item:
                    serial = text_item.text().strip()
                    if serial:
                        serial_list.append(serial)
        logging.info(serial_list)
        if not serial_list:
            self.msg.show_warning("提示", "没有选中任何有效的番号")
            return

        # 通过惰性单例获取 CrawlerManager 启动后台任务
        from core.crawler.CrawlerManager import get_manager
        get_manager().start_crawl(serial_list)
        
        self.msg.show_info("提示", "已转入后台处理，您可以继续其他操作。")
        self.accept()




