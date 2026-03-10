import sys
from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout,
    QWidget,QPushButton, QFileDialog, QMessageBox,QLabel,QLineEdit
)
from PySide6.QtCore import Qt, QSize,QEvent,Slot
from PySide6.QtGui import QMouseEvent

class SinglePathManagement(QWidget):
    '''一个单路径管理的界面
    封装完成的
    对外使用get_paths()和load_paths()方法即可
    '''
    def __init__(self,label_text="路径管理："):
        super().__init__()
        self.resize(400, 100)

        self.filepath=QLineEdit()
        self.filepath.setMinimumWidth(300)
        self.btn_browse=QPushButton("...")
        self.btn_browse.setMaximumWidth(30)
        layout = QHBoxLayout(self)

        layout.addWidget(QLabel(label_text))
        layout.addWidget(self.filepath)
        layout.addWidget(self.btn_browse)

        self.btn_browse.clicked.connect(self.on_button_clicked)

    def on_button_clicked(self, row):
        """点击“选择文件夹”按钮"""
        from pathlib import Path
        if Path(self.filepath.text()).is_dir():
            folder = QFileDialog.getExistingDirectory(
                self,
                "选择文件夹",
                self.filepath.text()
            )
        else:
            folder = QFileDialog.getExistingDirectory(
                self,
                "选择文件夹",
                 ""  # 以当前路径作为初始目录
            )
        if folder:
            self.filepath.setText(folder)

    def get_path(self):
        """返回第一列所有数据的列表（忽略空行可自行过滤）"""
        return self.filepath.text()
    
    def load_path(self, path:str):
        """加载路径列表到表格"""
        self.filepath.setText(path)


# 下面的用于单次测试，看个界面没什么意义
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SinglePathManagement()
    window.show()
    window.load_path("C:/")
    sys.exit(app.exec())
    