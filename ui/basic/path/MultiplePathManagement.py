import sys
from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout,
    QWidget, QTableWidget, QTableWidgetItem,
    QPushButton, QFileDialog, QMessageBox, QStyledItemDelegate,QStyle, QStyleOptionButton,QLabel,QLineEdit
)
from PySide6.QtCore import Qt, QSize,QEvent,Slot
from PySide6.QtGui import QMouseEvent
from pathlib import Path
import logging
from darkeye_ui.components.button import Button
from darkeye_ui.components.label import Label
from darkeye_ui.components.token_table_widget import TokenTableWidget

class ButtonDelegate(QStyledItemDelegate):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.button_visible_rows = set()  # 哪些行显示按钮

    def paint(self, painter, option, index):
        row = index.row()
        if row not in self.button_visible_rows:
            # 不显示按钮时画空白
            return super().paint(painter, option, index)

        # 绘制按钮外观
        button_option = QStyleOptionButton()
        button_option.rect = option.rect
        button_option.text = "..."
        button_option.state = QStyle.State_Enabled
        if option.state & QStyle.State_MouseOver:
            button_option.state |= QStyle.State_MouseOver

        QApplication.style().drawControl(QStyle.CE_PushButton, button_option, painter)

    def editorEvent(self, event, model, option, index):
        row = index.row()
        if row not in self.button_visible_rows:
            return super().editorEvent(event, model, option, index)

        # 完全消费所有鼠标按钮和移动事件
        if event.type() in (QEvent.MouseButtonPress,
                            QEvent.MouseButtonRelease,
                            QEvent.MouseButtonDblClick,
                            QEvent.MouseMove):
            
            # 左键释放时触发按钮点击
            if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self.main_window.on_button_clicked(row)
            
            # 鼠标移动时刷新高亮
            if event.type() == QEvent.MouseMove:
                self.main_window.table.viewport().update()
            
            # 重要：返回 True 表示事件已处理，阻止传播到 QTableWidget
            return True

        return super().editorEvent(event, model, option, index)

    def sizeHint(self, option, index):
        if index.row() in self.button_visible_rows:
            return super().sizeHint(option, index) + QSize(10, 0)  # 紧凑宽度
        return super().sizeHint(option, index)


class MultiplePathManagement(QWidget):
    '''一个多路径管理的表格界面
    封装完成的
    对外使用get_paths()和load_paths()方法即可
    '''
    def __init__(self,label_text="路径管理："):
        super().__init__()

        layout = QVBoxLayout(self)

        
        # 按钮区
        btn_layout = QHBoxLayout()
        self.add_btn = Button("添加地址")
        self.del_btn = Button("删除地址")
        #self.print_btn = QPushButton("打印所选地址")
        btn_layout.addWidget(Label(label_text))
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addStretch()
        #btn_layout.addWidget(self.print_btn)
        layout.addLayout(btn_layout)

        # 表格设置
        self.table = TokenTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["路径（双击输入或选按钮）", "操作"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setRowCount(0)

        # 隐藏水平表头（列标题："路径（双击输入或选按钮）" 和 "操作"）
        self.table.horizontalHeader().hide()
        # 隐藏垂直表头（左侧的行号 0,1,2,3...）
        #self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QTableWidget.SingleSelection)

        # 第1列拉伸填满，第2列固定窄宽度
        from PySide6.QtWidgets import QHeaderView
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 22)

        # 自定义代理：控制按钮显示
        self.delegate = ButtonDelegate(self,self.table)
        self.table.setItemDelegateForColumn(1, self.delegate)

        layout.addWidget(self.table)

        # 信号连接
        self.add_btn.clicked.connect(self.add_row)
        self.del_btn.clicked.connect(self.delete_row)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
# 新增：监听选中变化，自动隐藏其他行的按钮
        self.table.selectionModel().selectionChanged.connect(self.on_selection_changed)
        #self.print_btn.clicked.connect(self.print_first_column)

    def on_selection_changed(self):
        """当选中行变化时，隐藏所有按钮（或只保留当前选中行）"""
        current_rows = set(index.row() for index in self.table.selectedIndexes())

        # 方案1：全部隐藏（推荐，更干净）
        self.delegate.button_visible_rows.clear()

        # 方案2：只保留当前选中行的按钮（如果你想保留）
        # self.delegate.button_visible_rows &= current_rows

        self.table.viewport().update()

    def add_row(self):
        self.delegate.button_visible_rows.clear()
        row = self.table.rowCount()
        self.table.insertRow(row)

        # 第1列：路径文本项（可编辑）
        path_item = QTableWidgetItem("")
        path_item.setFlags(path_item.flags() | Qt.ItemIsEditable)
        self.table.setItem(row, 0, path_item)

        # 第2列：空项（按钮由 delegate 控制）
        self.table.setItem(row, 1, QTableWidgetItem(""))  # 占位
        self.table.setCurrentCell(row, 0)
        self.on_cell_double_clicked(row, 0)

    def delete_row(self):
        selected_rows = set(idx.row() for idx in self.table.selectedIndexes())
        if not selected_rows:
            QMessageBox.information(self, "提示", "请先选中要删除的行")
            return
        '''
        reply = QMessageBox.question(self, "确认", f"删除 {len(selected_rows)} 行？")
        if reply == QMessageBox.Yes:
        '''
        for r in sorted(selected_rows, reverse=True):
            self.table.removeRow(r)
        # 删除后清除该行的按钮可见标记
        for r in list(self.delegate.button_visible_rows):
            if r >= self.table.rowCount():
                self.delegate.button_visible_rows.discard(r)

    def on_cell_double_clicked(self, row, column):
        """双击路径列（第0列）时，显示该行的选择按钮"""
        # 显示按钮（第二列）
        self.delegate.button_visible_rows.add(row)
        self.table.viewport().update()  # 刷新绘制按钮

        # 如果双击的是第一列 → 立即进入编辑模式（光标在输入框）
        if column == 0:
            self.table.editItem(self.table.item(row, 0))

    def on_button_clicked(self, row):
        """点击“选择文件夹”按钮"""
        from pathlib import Path
        if Path(self.table.item(row, 0).text()).is_dir():
            folder = QFileDialog.getExistingDirectory(
                self,
                "选择文件夹",
                self.table.item(row, 0).text()
            )
        else:
            folder = QFileDialog.getExistingDirectory(
                self,
                "选择文件夹",
                 ""  # 以当前路径作为初始目录
            )
        if folder:
            self.table.item(row, 0).setText(folder)
    

    @Slot()
    def print_first_column(self):
        data = self.get_paths()
        print("第一列数据：", data)


    def get_paths(self)->list[Path]:
        """返回第一列所有数据的列表（忽略空行可自行过滤）"""
        data = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            text = item.text().strip() if item else ""
            data.append(Path(text))
        return data
    
    def load_paths(self, paths: list[Path]):
        """加载路径列表到表格"""
        logging.info(f"加载路径列表到表格: {paths}")
        self.table.setRowCount(0)
        self.delegate.button_visible_rows.clear()
        for path in paths:
            path=str(path)
            row = self.table.rowCount()
            self.table.insertRow(row)

            # 第1列：路径文本项（可编辑）
            path_item = QTableWidgetItem(path)
            path_item.setFlags(path_item.flags() | Qt.ItemIsEditable)
            self.table.setItem(row, 0, path_item)

            # 第2列：空项（按钮由 delegate 控制）
            self.table.setItem(row, 1, QTableWidgetItem(""))  # 占位




# 下面的用于单次测试，看个界面没什么用
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MultiplePathManagement("路径列表管理：")
    window.show()
    window.load_paths(["C:/Path/One", "D:/Another/Path", "E:/More/Paths","C:/"])
    sys.exit(app.exec())
    