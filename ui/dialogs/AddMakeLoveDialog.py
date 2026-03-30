from PySide6.QtWidgets import QGridLayout, QDialog
from PySide6.QtCore import Qt, QDateTime, QTime
from PySide6.QtGui import QIcon

from config import ICONS_PATH
from core.database.insert import insert_lovemaking_record
from darkeye_ui.components import HeartRatingWidget
from controller.message_service import MessageBoxService
from darkeye_ui.components.label import Label
from darkeye_ui.components.input import TextEdit
from darkeye_ui.components import TokenDateTimeEdit
from darkeye_ui.components.button import Button
from darkeye_ui.design.icon import get_builtin_icon

class AddMakeLoveDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("添加做爱记录")
        self.setWindowIcon(get_builtin_icon(name="note_pen"))
        self.resize(300, 300)
        self.msg = MessageBoxService(self)

        self.label_rating = Label("评分")
        self.input_rating = HeartRatingWidget()

        self.label_comment = Label("事后评价")
        self.input_comment = TextEdit()

        self.label_time = Label("时间")
        self.datetime_edit = TokenDateTimeEdit(self)
        self.datetime_edit.setDisplayFormat("yy-MM-dd HH:mm")  # 设置显示格式
        self.datetime_edit.setDateTime(QDateTime.currentDateTime())  # 设置初始时间
        self.datetime_edit.setCalendarPopup(True)  # 启用日历下拉
        self.datetime_edit.setMinimumTime(QTime(0, 0))  # 设置最小时间为 00:00
        self.datetime_edit.setMaximumTime(QTime(23, 59))  # 设置最大时间为 23:59
        self.datetime_edit.setTimeSpec(Qt.LocalTime)

        # 提交
        self.btn_commit = Button("提交记录")
        self.btn_commit.clicked.connect(self.commit)

        # 分布
        main_layout = QGridLayout(self)
        main_layout.addWidget(self.label_rating, 0, 0, Qt.AlignmentFlag.AlignRight)
        main_layout.addWidget(self.input_rating, 0, 1)
        main_layout.addWidget(self.label_time, 1, 0, Qt.AlignmentFlag.AlignRight)
        main_layout.addWidget(self.datetime_edit, 1, 1)
        main_layout.addWidget(self.label_comment, 2, 0, Qt.AlignmentFlag.AlignRight)
        main_layout.addWidget(self.input_comment, 2, 1)
        main_layout.addWidget(self.btn_commit, 3, 1)

    def commit(self):
        # 提交数据，写入数据库内
        time = self.datetime_edit.dateTime().toString("yyyy-MM-dd HH:mm")
        rating = self.input_rating.get_rating()
        comment = self.input_comment.toPlainText()

        if rating == 0:
            self.msg.show_info("提示", "请打分")
            return

        # 非空检测后插入数据
        if insert_lovemaking_record(time, rating, comment):
            self.msg.show_info("提示", "成功提交一次做爱记录")
            from controller.global_signal_bus import global_signals

            global_signals.lovemakingChanged.emit()
            self.accept()  # 关闭对话框
        else:
            self.msg.show_warning("提示", "提交失败")
