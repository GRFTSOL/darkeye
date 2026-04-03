"""视频相关设置页面。"""

import logging

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget

from config import (
    get_local_video_player_exe,
    get_video_path,
    set_local_video_player_exe,
)
from darkeye_ui.components import Label, Button
from controller.message_service import MessageBoxService
from ui.basic import MultiplePathManagement
from darkeye_ui.components.input import LineEdit


class VideoSettingPage(QWidget):
    """视频相关设置页面"""

    def __init__(self):
        super().__init__()
        self.msg = MessageBoxService(self)

        self.init_ui()
        self.pathManagement.load_paths(get_video_path())
        self._install_auto_save()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.pathManagement = MultiplePathManagement(label_text="视频文件夹路径管理：")
        self.pathManagement.setMinimumHeight(300)
        layout.addWidget(self.pathManagement)

        player_row = QHBoxLayout()
        player_row.addWidget(Label("本地播放器（可选）："))
        self.local_player_edit = LineEdit(self)
        self.local_player_edit.setPlaceholderText(
            "留空则使用系统默认程序；书架/DVD 与作品页播放本地文件时生效"
        )
        self.local_player_edit.setClearButtonEnabled(True)
        self.local_player_edit.setText(get_local_video_player_exe())
        self.local_player_edit.editingFinished.connect(self._persist_local_player_exe)
        player_row.addWidget(self.local_player_edit, stretch=1)
        self.btn_browse_player = Button("浏览…")
        self.btn_browse_player.setToolTip("选择播放器可执行文件（如 VLC、MPC-HC 等）")
        self.btn_browse_player.clicked.connect(self._browse_local_player_exe)
        player_row.addWidget(self.btn_browse_player)
        layout.addLayout(player_row)

        self.btn_update_db_video = Button("查找本地的视频录入数据库")
        self.btn_update_db_video.setToolTip(
            "扫描本地视频的路径下的所有视频，并提取视频番号，将没有的番号尝试去抓取信息"
        )
        self.btn_update_db_video.clicked.connect(self.task_update_db_video)
        layout.addWidget(self.btn_update_db_video)

    def _install_auto_save(self):
        self.pathManagement.table.itemChanged.connect(self._auto_save_paths)
        self.pathManagement.add_btn.clicked.connect(self._auto_save_paths)
        self.pathManagement.del_btn.clicked.connect(self._auto_save_paths)

    @Slot()
    def _auto_save_paths(self):
        self.accept()

    @Slot()
    def _persist_local_player_exe(self):
        set_local_video_player_exe(self.local_player_edit.text())
        logging.info(
            "本地播放器路径已写入 .ini: %s",
            get_local_video_player_exe() or "(系统默认)",
        )

    @Slot()
    def _browse_local_player_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择播放器可执行文件",
            "",
            "可执行文件 (*.exe);;所有文件 (*.*)",
        )
        if path:
            self.local_player_edit.setText(path)
            self._persist_local_player_exe()

    @Slot()
    def task_update_db_video(self):
        """扫描本地视频路径下的所有视频文件名，找出数据库中不存在的番号并弹出 AddQuickWork 供抓取。"""
        from core.database.query import get_serial_number
        from ui.dialogs.AddQuickWork import AddQuickWork
        from utils.utils import get_video_names_from_paths

        def _norm(s: str) -> str:
            return s.upper().replace("-", "")

        video_names = get_video_names_from_paths(get_video_path())
        logging.info(f"视频文件名列表: {video_names}，数量: {len(video_names)}")
        db_serials = get_serial_number()
        db_normalized = {_norm(s) for s in db_serials}

        missing_serials = []
        seen_normalized = set()
        for name in video_names:
            norm = _norm(name)
            if norm not in db_normalized and norm not in seen_normalized:
                seen_normalized.add(norm)
                missing_serials.append(name)

        if not missing_serials:
            self.msg.show_info("提示", "本地视频的番号均已存在于数据库中")
            return

        dialog = AddQuickWork()
        dialog.load_serials(missing_serials)
        dialog.exec()

    def accept(self):
        paths = []
        for p in self.pathManagement.get_paths():
            s = str(p).strip()
            if not s or s == ".":
                continue
            paths.append(p)
        from config import update_video_path

        update_video_path(paths)
        logging.info("保存的视频路径设置写入.ini: %s", paths)
