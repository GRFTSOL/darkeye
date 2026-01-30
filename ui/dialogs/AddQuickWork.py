from anyio import sleep
from PySide6.QtWidgets import (
    QPushButton, QLabel, QGridLayout, QDialog, QLineEdit,
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Slot, QThreadPool, Qt
from PySide6.QtGui import QIcon
from config import ICONS_PATH, WORKCOVER_PATH
import logging, asyncio, re
from controller import MessageBoxService, TaskManager
from core.database.update import update_work_byhand_
from core.crawler.download import download_image
from core.crawler.Worker import Worker
from utils.utils import translate_text


class AddQuickWork(QDialog):
    # 快速记录作品番号的窗口，能在局外响应
    def __init__(self):
        super().__init__()
        logging.info("----------快速记录作品番号窗口----------")
        self.setWindowTitle("快速记录作品番号(W)")
        self.setWindowIcon(QIcon(str(ICONS_PATH / "film.png")))
        self.setFixedSize(400, 500)
        self.msg = MessageBoxService(self)

        self.init_ui()

    def init_ui(self):
        # 1. 顶部工具栏
        top_layout = QHBoxLayout()
        self.btn_add = QPushButton("添加")
        self.btn_del = QPushButton("删除")
        self.btn_clean = QPushButton("去后缀")
        
        self.btn_add.clicked.connect(self.add_row)
        self.btn_del.clicked.connect(self.delete_rows)
        self.btn_clean.clicked.connect(self.clean_suffix)
        
        top_layout.addWidget(self.btn_add)
        top_layout.addWidget(self.btn_del)
        top_layout.addWidget(self.btn_clean)

        # 2. 中间列表区域
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["选择", "番号"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        # 3. 底部提交按钮
        self.btn_commit = QPushButton("快速添加")
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
        
        if not serial_list:
            self.msg.show_warning("提示", "没有选中任何有效的番号")
            return

        # 使用全局 CrawlerManager 启动后台任务
        from core.crawler.CrawlerManager import crawler_manager2
        crawler_manager2.start_crawl(serial_list)
        
        self.msg.show_info("提示", "已转入后台处理，您可以继续其他操作。")
        self.accept()




