from PySide6.QtWidgets import QDialog, QGridLayout, QSizePolicy
from PySide6.QtCore import Qt, QDateTime, QTime, Slot

from darkeye_ui.components import HeartRatingWidget
from core.database.db_queue import submit_db_raw
from core.database.query import (
    get_unique_tools_from_masturbation,
    get_workid_by_serialnumber,
)
import logging
from config import ICONS_PATH
from PySide6.QtGui import QIcon
from controller.message_service import MessageBoxService
from darkeye_ui.components.label import Label
from darkeye_ui.components.button import Button
from darkeye_ui.components.input import TextEdit
from darkeye_ui.components import TokenDateTimeEdit
from darkeye_ui.design.icon import get_builtin_icon

class AddMasturbationDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("添加自慰记录")
        self.setWindowIcon(get_builtin_icon(name="note_pen"))
        self.resize(300, 300)
        self.msg = MessageBoxService(self)  # 消息服务

        self.label_serial_number = Label("番号")
        from core.database.query import get_serial_number
        from ui.widgets import CompleterLineEdit

        self.input_serial_number = CompleterLineEdit(
            lambda: submit_db_raw(get_serial_number).result()
        )

        self.label_rating = Label("评分")
        self.input_rating = HeartRatingWidget()

        self.label_tool = Label("使用工具")
        self.input_tool = CompleterLineEdit(
            lambda: submit_db_raw(get_unique_tools_from_masturbation).result()
        )  # 设置撸管工具的读取
        self.input_tool.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self.label_comment = Label("事后评价")
        self.input_comment = TextEdit()

        self.label_time = Label("时间")
        self.datetime_edit = TokenDateTimeEdit(self)
        self.datetime_edit.setDisplayFormat("yy-MM-dd HH:mm")  # 设置显示格式
        self.datetime_edit.setDateTime(QDateTime.currentDateTime())  # 设置初始时间
        self.datetime_edit.setCalendarPopup(True)  # 启用日历下拉
        self.datetime_edit.setMinimumTime(
            QTime(0, 0)
        )  # 设置最小时间为 00:00        # 限定精度为分钟
        self.datetime_edit.setMaximumTime(QTime(23, 59))  # 设置最大时间为 23:59
        self.datetime_edit.setTimeSpec(Qt.LocalTime)

        # 提交按钮
        self.btn_commit = Button("提交记录")
        self.btn_commit.clicked.connect(self.commit)

        # 分布
        main_layout = QGridLayout(self)
        main_layout.addWidget(
            self.label_serial_number, 0, 0, Qt.AlignmentFlag.AlignRight
        )
        main_layout.addWidget(self.input_serial_number, 0, 1)
        main_layout.addWidget(self.label_rating, 1, 0, Qt.AlignmentFlag.AlignRight)
        main_layout.addWidget(self.input_rating, 1, 1)
        main_layout.addWidget(self.label_tool, 2, 0, Qt.AlignmentFlag.AlignRight)
        main_layout.addWidget(self.input_tool, 2, 1)
        main_layout.addWidget(self.label_time, 3, 0, Qt.AlignmentFlag.AlignRight)
        main_layout.addWidget(self.datetime_edit, 3, 1)
        main_layout.addWidget(self.label_comment, 4, 0, Qt.AlignmentFlag.AlignRight)
        main_layout.addWidget(self.input_comment, 4, 1)
        main_layout.addWidget(self.btn_commit, 5, 1)

    @Slot()
    def commit(self):
        # 提交数据，写入数据库内
        serial_number = self.input_serial_number.text().strip()
        work_id = submit_db_raw(
            lambda: get_workid_by_serialnumber(serial_number)
        ).result()

        time = self.datetime_edit.dateTime().toString("yyyy-MM-dd HH:mm")
        rating = self.input_rating.get_rating()
        tool = self.input_tool.text()
        comment = self.input_comment.toPlainText()

        # 非空检测
        if work_id == None and self.input_serial_number.text() != "":
            if self.msg.ask_yes_no("提示", "库内没有该番号，是否添加新作品？"):
                logging.info("用户选择了：是，添加新作品")
                # 新命令
            else:
                logging.info("用户选择了：否，不添加")
            return

        if rating == 0:
            self.msg.show_info("提示", "请打分")
            return

        if tool == "":
            self.msg.show_info("提示", "请输入一个自慰工具")
            return

        # 非空检测后插入数据
        from core.database.insert import insert_masturbation_record

        if insert_masturbation_record(
            work_id, serial_number, time, rating, tool, comment
        ):
            self.msg.show_info("提示", "成功提交一次自慰记录")
            from controller.global_signal_bus import global_signals

            global_signals.masterbationChanged.emit()
            self.accept()  # 关闭对话框
        else:
            self.msg.show_warning("提示", "提交失败")
