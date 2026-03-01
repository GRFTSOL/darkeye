
#关于后台任务与通知相关的组件这个基本不可复用
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton,QMainWindow,QVBoxLayout,QListWidget,QSizePolicy
from PySide6.QtCore import Slot, Qt,QObject,QTimer,QPoint
from ui.basic import IconPushButton
from datetime import datetime
from controller.GlobalSignalBus import global_signals
from darkeye_ui.components.label import Label

class TaskListWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("任务列表")
        self.resize(300, 300)


        # 关键：窗口标志设置
        self.setWindowFlags(
            Qt.Tool             # 工具窗口（无任务栏图标，适合浮动面板）
            #| Qt.WindowStaysOnTopHint   # 始终在最上层（即使主窗口失焦）
            | Qt.FramelessWindowHint    # 可选：无边框，更像浮动面板
            # | Qt.WindowTitleHint      # 如果想保留标题栏，可加这个
        )

        # 可选：半透明背景，美观
        self.setAttribute(Qt.WA_TranslucentBackground)

        title=Label("后台任务列表")
        title.setStyleSheet("""
            background: rgba(255, 255, 255, 200);
            border-radius: 6px;
            color: black;
            font-size: 14px;
            padding: 4px 8px;
        """)
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(3)
        layout.addWidget(title)
        self.task_list = QListWidget()
        self.task_list.setStyleSheet("""
            background: rgba(255, 255, 255, 200);
            border-radius: 10px;
            color: white;
        """)
        layout.addWidget(self.task_list)

        # 定时器：每 100ms 检查主窗口位置并跟随
        self.follow_timer = QTimer(self)
        self.follow_timer.timeout.connect(self.follow_parent)
    
    def follow_parent(self):
        if not self.parent():
            return

        # 获取主窗口（父窗口）位置
        parent_rect = self.parent().geometry()

        # 计算右下角位置（留出边距）
        margin = 24
        x = parent_rect.right() - self.width()
        y = parent_rect.bottom() - self.height() - margin
        #print(f"{x},{y}")

        # 移动到新位置
        #self.move(self.parent().mapToGlobal(QPoint(x, y)))
        self.setGeometry(x,y,self.width(),self.height())
        self.raise_()

    def show(self):
        super().show()
        self.follow_timer.start()  # 显示时开始跟随

    def hide(self):
        super().hide()
        self.follow_timer.stop()   # 隐藏时停止跟随

class StatusBarNotification(QWidget):
    """状态栏专用：包含计数器和按钮的组合控件"""
    def __init__(self, taskwindow:TaskListWindow=None,parent=None):
        super().__init__(parent)
        self.taskwindow=taskwindow
        self.showflag=False#标记

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(3)

        # 2. 消息计数器 (小红点风格或括号风格)
        self.count_label = Label("(0)")
        self.count_label.setStyleSheet("color: #d93025; font-weight: bold;font-size:14px")
        self.msg_count = 0

        # 3. 功能按钮
        self.action_btn = IconPushButton("bell.svg",16,16)

        layout.addWidget(self.action_btn)
        layout.addWidget(self.count_label)
        self.action_btn.clicked.connect(self.clickedbutton)


    def update_info(self, text, count_increment=True):
        """更新显示内容"""
        self.msg_label.setText(text)
        if count_increment:
            self.msg_count += 1
            self.count_label.setText(f"({self.msg_count})")


    def clickedbutton(self):

        if not self.showflag:#显示
            self.taskwindow.show()
            self.showflag=True
        else:
            self.taskwindow.hide()
            self.showflag=False
