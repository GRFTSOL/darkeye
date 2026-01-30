from PySide6.QtWidgets import QStatusBar
from PySide6.QtCore import QTimer

from .GlobalSignalBus import global_signals

class StatusManager():
    '''状态栏消息管理类'''
    def __init__(self, status_bar:QStatusBar):
        self.status_bar = status_bar
        self.timer = QTimer()
        self.timer.timeout.connect(self.show_ready)
        self.status_bar.showMessage("就绪", 0)  # 0 表示永久显示
        global_signals.status_msg_changed.connect(lambda msg:self.show_temporary_message(msg))
        
    def show_temporary_message(self, message, duration=3000):
        """显示临时消息，然后恢复就绪"""
        self.status_bar.showMessage(message, duration)
        self.timer.start(duration + 50)  # 稍晚一点触发
        
    def show_ready(self):
        """显示就绪状态"""
        self.status_bar.showMessage("就绪", 0)
        self.timer.stop()
