"""视频相关设置页面。"""

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QProgressDialog,
    QVBoxLayout,
    QWidget,
)

from config import (
    get_local_video_player_exe,
    get_video_path,
    set_local_video_player_exe,
)
from darkeye_ui.components import Label, Button
from controller.message_service import MessageBoxService
from ui.basic import MultiplePathManagement
from darkeye_ui.components.input import LineEdit


class _NfoBatchImportWorker(QObject):
    """在后台线程中批量导入 NFO；通过信号报告进度与结果。"""

    progress = Signal(int, int, str)
    finished = Signal(int, int, int, object, bool)

    def __init__(self, nfo_list: list[Path]):
        super().__init__()
        self._nfo_list = list(nfo_list)
        self._cancel = False

    @Slot()
    def run(self):
        from core.importers import (
            emit_after_nfo_batch_import,
            import_work_from_movie_nfo,
        )

        imported = skipped = failed = 0
        error_lines: list[str] = []
        total = len(self._nfo_list)
        stopped_early = False

        for i, nfo_path in enumerate(self._nfo_list):
            if self._cancel:
                stopped_early = True
                break
            self.progress.emit(i + 1, total, nfo_path.name)
            ok, message = import_work_from_movie_nfo(nfo_path, emit_ui_signals=False)
            if ok:
                imported += 1
                logging.info("NFO 导入成功：%s — %s", nfo_path, message)
            elif "已在库中" in message:
                skipped += 1
            else:
                failed += 1
                if len(error_lines) < 8:
                    error_lines.append(f"{nfo_path.name}: {message}")

        if imported > 0:
            emit_after_nfo_batch_import()

        self.finished.emit(imported, skipped, failed, error_lines, stopped_early)

    @Slot()
    def request_cancel(self):
        self._cancel = True


class VideoSettingPage(QWidget):
    """视频相关设置页面"""

    def __init__(self):
        super().__init__()
        self.msg = MessageBoxService(self)
        self._nfo_import_thread: QThread | None = None
        self._nfo_import_worker: _NfoBatchImportWorker | None = None
        self._nfo_progress_dialog: QProgressDialog | None = None

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

    def _nfo_import_busy(self) -> bool:
        t = self._nfo_import_thread
        return t is not None and t.isRunning()

    @Slot()
    def task_import_nfo_from_video_paths(self):
        """在视频目录中查找 .nfo 并导入；番号已存在则由导入逻辑跳过。"""
        if self._nfo_import_busy():
            self.msg.show_info("提示", "批量导入正在进行中，请稍候。")
            return

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

        total = len(nfo_list)
        dialog = QProgressDialog(
            "",
            "取消",
            0,
            total,
            self,
        )
        dialog.setWindowTitle("批量导入 NFO")
        dialog.setWindowModality(Qt.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setMinimumWidth(420)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setValue(0)
        dialog.setLabelText(f"准备导入（共 {total} 个）…")

        worker = _NfoBatchImportWorker(nfo_list)
        thread = QThread(self)
        worker.moveToThread(thread)

        worker.progress.connect(self._on_nfo_batch_progress)
        dialog.canceled.connect(worker.request_cancel)
        worker.finished.connect(self._on_nfo_batch_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_nfo_batch_thread_cleared)
        thread.started.connect(worker.run)

        self._nfo_batch_total = total
        self._nfo_progress_dialog = dialog
        self._nfo_import_worker = worker
        self._nfo_import_thread = thread

        self.btn_import_nfo.setEnabled(False)
        dialog.show()
        thread.start()

    @Slot(int, int, str)
    def _on_nfo_batch_progress(self, current: int, total: int, name: str):
        d = self._nfo_progress_dialog
        if d is not None:
            d.setMaximum(max(1, total))
            d.setValue(current)
            d.setLabelText(f"正在导入 ({current}/{total})：{name}")

    @Slot(int, int, int, object, bool)
    def _on_nfo_batch_finished(
        self,
        imported: int,
        skipped: int,
        failed: int,
        error_lines: object,
        stopped_early: bool,
    ):
        self.btn_import_nfo.setEnabled(True)
        lines = error_lines if isinstance(error_lines, list) else []
        str_lines = [str(x) for x in lines]

        d = self._nfo_progress_dialog
        if d is not None:
            d.close()
            self._nfo_progress_dialog = None

        n_total = getattr(self, "_nfo_batch_total", imported + skipped + failed)
        parts: list[str] = []
        if stopped_early:
            parts.append("已取消。以下为已处理部分的结果。\n")
        parts.extend(
            [
                f"共扫描 {n_total} 个 NFO。",
                f"新导入：{imported}",
                f"跳过（番号已存在）：{skipped}",
                f"失败：{failed}",
            ]
        )
        if str_lines:
            parts.append("")
            parts.extend(str_lines)
        body = "\n".join(parts)

        if failed:
            self.msg.show_warning("NFO 批量导入完成", body)
        else:
            self.msg.show_info("NFO 批量导入完成", body)

    @Slot()
    def _on_nfo_batch_thread_cleared(self):
        self._nfo_import_thread = None
        self._nfo_import_worker = None

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
