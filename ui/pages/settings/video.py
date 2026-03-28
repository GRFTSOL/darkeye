"""视频相关设置页面。"""

import logging
from pathlib import Path

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

        self.btn_import_nfo = Button("从视频路径扫描并导入 NFO")
        self.btn_import_nfo.setToolTip(
            "递归查找已配置路径下所有 .nfo，按 Kodi 电影格式导入作品；"
            "若 NFO 内番号已在库中则跳过。"
        )
        self.btn_import_nfo.clicked.connect(self.task_import_nfo_from_video_paths)
        layout.addWidget(self.btn_import_nfo)

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

    @staticmethod
    def _collect_nfo_files(video_roots: list[Path]) -> list[Path]:
        found: list[Path] = []
        for root in video_roots:
            if not root.is_dir():
                continue
            try:
                for nfo in root.rglob("*.nfo"):
                    if nfo.is_file():
                        found.append(nfo.resolve())
            except OSError as e:
                logging.warning("扫描 NFO 时无法访问 %s：%s", root, e)
        return sorted(set(found))

    @Slot()
    def task_import_nfo_from_video_paths(self):
        """在视频目录中查找 .nfo 并导入；番号已存在则由导入逻辑跳过。"""
        from core.importers import import_work_from_movie_nfo

        roots = [Path(p).expanduser() for p in get_video_path()]
        roots = [r for r in roots if r.is_dir()]
        if not roots:
            self.msg.show_info(
                "提示", "请先在上方添加至少一个存在本地的视频文件夹路径。"
            )
            return

        nfo_list = self._collect_nfo_files(roots)
        if not nfo_list:
            self.msg.show_info("提示", "在已配置的视频路径下未发现 .nfo 文件。")
            return

        imported = skipped = failed = 0
        error_lines: list[str] = []
        for nfo_path in nfo_list:
            ok, message = import_work_from_movie_nfo(nfo_path)
            if ok:
                imported += 1
                logging.info("NFO 导入成功：%s — %s", nfo_path, message)
            elif "已在库中" in message:
                skipped += 1
            else:
                failed += 1
                if len(error_lines) < 8:
                    error_lines.append(f"{nfo_path.name}: {message}")

        parts = [
            f"共扫描 {len(nfo_list)} 个 NFO。",
            f"新导入：{imported}",
            f"跳过（番号已存在）：{skipped}",
            f"失败：{failed}",
        ]
        if error_lines:
            parts.append("")
            parts.extend(error_lines)
        body = "\n".join(parts)

        if failed:
            self.msg.show_warning("NFO 批量导入完成", body)
        else:
            self.msg.show_info("NFO 批量导入完成", body)

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
