"""视频相关设置页面。"""

import logging
from PySide6.QtWidgets import QVBoxLayout, QWidget
from PySide6.QtCore import Slot

from config import get_video_path
from darkeye_ui.components import Label, Button
from controller.MessageService import MessageBoxService
from ui.basic import MultiplePathManagement


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
        logging.info(f"保存的视频路径设置写入.ini: {paths}")
