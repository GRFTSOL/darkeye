
from PySide6.QtWidgets import QPushButton, QHBoxLayout,QLabel,QVBoxLayout,QDialog,QFormLayout, QWidget
from PySide6.QtCore import Signal,Qt
from config import ICONS_PATH
from PySide6.QtGui import QIcon
from controller.ShortcutRegistry import ShortcutRegistry
from darkeye_ui.components.label import Label

class HelpPage(QWidget):
    #帮助窗口
    success=Signal(bool)#定义信号
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle("帮助")
        self.setWindowIcon(QIcon(str(ICONS_PATH / "circle-question-mark.png")))

        datas=[
        {"shortcut":"C","text":"特定区域截图(部分反应)"},
        {"shortcut":"Shift+C","text":"全软件截图"},
        {"shortcut":"M","text":"快速添加自慰记录"},
        {"shortcut":"W","text":"快速添加作品"},
        {"shortcut":"A","text":"快速添加晨勃记录"},
        {"shortcut":"L","text":"快速添加做爱记录"}
        ]

        mainlayout=QFormLayout(self)
        for data in datas:
            mainlayout.addRow(Label(data["shortcut"]),Label(data["text"]))
        mainlayout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)  
