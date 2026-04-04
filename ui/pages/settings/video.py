"""视频相关设置页面。"""

import logging
from collections import defaultdict
from pathlib import Path

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

    _NO_SERIAL_DIALOG_LIMIT = 80

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

        self.btn_update_db_video = Button("扫描本地视频提取番号并录入数据库")
        self.btn_update_db_video.setToolTip(
            "扫描本地视频的路径下的所有视频，并提取视频番号，将没有的番号尝试去抓取信息"
        )
        self.btn_update_db_video.clicked.connect(self.task_update_db_video)
        layout.addWidget(self.btn_update_db_video)

        self.btn_match_video_url = Button("同步作品本地视频路径")
        self.btn_match_video_url.setToolTip(
            "扫描已配置文件夹中的视频，从文件名提取番号并与库中作品匹配，"
            "将匹配到的本地绝对路径写入作品表的 video_url（多条英文逗号分隔、去重）；"
            "以本次扫描结果为准完全覆盖，不保留库中旧路径"
        )
        self.btn_match_video_url.clicked.connect(self.task_match_local_video_to_work)
        layout.addWidget(self.btn_match_video_url)

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

    def _show_no_serial_videos_dialog(self, entries: list[tuple[str, str]]) -> None:
        """entries: (无后缀文件名, 绝对路径)"""
        if not entries:
            return
        cap = self._NO_SERIAL_DIALOG_LIMIT
        lines = [f"{name}\n{path}" for name, path in entries[:cap]]
        suffix = ""
        if len(entries) > cap:
            suffix = (
                f"\n\n… 另有 {len(entries) - cap} 条未列出（共 {len(entries)} 个文件）"
            )
        self.msg.show_warning(
            "无法提取番号",
            "以下视频未能从文件名识别番号：\n\n" + "\n\n".join(lines) + suffix,
        )

    @Slot()
    def task_update_db_video(self):
        """扫描本地视频路径下的所有视频文件名，找出数据库中不存在的番号并弹出 AddQuickWork 供抓取。"""
        from core.database.query import get_serial_number
        from ui.dialogs.AddQuickWork import AddQuickWork
        from utils.utils import get_video_names_from_paths

        video_names, no_serial_files = get_video_names_from_paths(get_video_path())
        self._show_no_serial_videos_dialog(no_serial_files)
        logging.info(f"视频文件名列表: {video_names}，数量: {len(video_names)}")
        db_serials = set(get_serial_number())

        missing_serials = []
        seen = set()
        for name in video_names:
            if name not in db_serials and name not in seen:
                seen.add(name)
                missing_serials.append(name)

        if not missing_serials:
            self.msg.show_info("提示", "本地视频的番号均已存在于数据库中")
            return

        dialog = AddQuickWork()
        dialog.load_serials(missing_serials)
        dialog.exec()

    @Slot()
    def task_match_local_video_to_work(self):
        """扫描本地视频路径，提取番号并匹配作品，以扫描结果完全覆盖写入 work.video_url。"""
        from controller.global_signal_bus import global_signals
        from core.database.query import get_serial_number_map
        from core.database.update import replace_work_video_urls_batch
        from utils.utils import collect_video_paths_with_serial

        paths = []
        for p in get_video_path():
            s = str(p).strip()
            if not s or s == ".":
                continue
            paths.append(p)

        if not paths:
            self.msg.show_info("提示", "请先在上方配置至少一个视频文件夹路径")
            return

        scanned = collect_video_paths_with_serial(paths)
        n_files = len(scanned)
        no_serial_files = [(Path(p).stem, p) for p, ser in scanned if not ser]
        n_no_serial = len(no_serial_files)
        self._show_no_serial_videos_dialog(no_serial_files)

        serial_map = get_serial_number_map()

        by_work: dict[int, list[str]] = defaultdict(list)
        n_no_match = 0
        for path_str, serial in scanned:
            if not serial:
                continue
            wid = serial_map.get(serial)
            if wid is None:
                n_no_match += 1
            else:
                by_work[wid].append(path_str)

        if not by_work:
            self.msg.show_info(
                "完成",
                f"共扫描 {n_files} 个视频文件；"
                f"无法提取番号 {n_no_serial} 个；"
                f"番号在库中无匹配 {n_no_match} 个。\n"
                "没有可写入的作品记录。",
            )
            return

        n_updated = replace_work_video_urls_batch(dict(by_work))
        if n_updated > 0:
            global_signals.workDataChanged.emit()

        self.msg.show_info(
            "完成",
            f"共扫描 {n_files} 个视频文件；"
            f"无法提取番号 {n_no_serial} 个；"
            f"番号在库中无匹配 {n_no_match} 个；"
            f"已更新 {n_updated} 条作品的 video_url。",
        )

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
