"""NFO 导入相关设置页面。"""

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtWidgets import QFileDialog, QProgressDialog, QVBoxLayout, QWidget

from config import BASE_DIR, get_video_path
from darkeye_ui.components import Label, Button
from controller.message_service import MessageBoxService


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


class NfoSettingPage(QWidget):
    """NFO 导入：批量（视频路径）与单文件。"""

    def __init__(self):
        super().__init__()
        self.msg = MessageBoxService(self)
        self._nfo_import_thread: QThread | None = None
        self._nfo_import_worker: _NfoBatchImportWorker | None = None
        self._nfo_progress_dialog: QProgressDialog | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(
            Label(
                "批量导入使用「视频」设置中配置的视频文件夹路径；"
                "请先在那里添加有效路径。"
            )
        )

        self.btn_import_nfo_paths = Button("从视频路径扫描并导入 NFO")
        self.btn_import_nfo_paths.setToolTip(
            "递归查找已配置路径下所有 .nfo，按 Kodi 电影格式导入作品；"
            "若 NFO 内番号已在库中则跳过。"
        )
        self.btn_import_nfo_paths.clicked.connect(self.task_import_nfo_from_video_paths)
        layout.addWidget(self.btn_import_nfo_paths)

        self.btn_import_nfo_folder = Button("从文件夹导入 NFO")
        self.btn_import_nfo_folder.setToolTip(
            "选择任意文件夹，递归查找其中所有 .nfo，导入方式与「视频路径」批量导入相同。"
        )
        self.btn_import_nfo_folder.clicked.connect(self.task_import_nfo_from_folder)
        layout.addWidget(self.btn_import_nfo_folder)

        self.btn_import_nfo_file = Button("从 NFO 导入作品")
        self.btn_import_nfo_file.setToolTip(
            "选择 Kodi 风格的 .nfo 文件导入一条作品（番号已存在则跳过）"
        )
        self.btn_import_nfo_file.clicked.connect(self.import_work_from_nfo_file)
        layout.addWidget(self.btn_import_nfo_file)

        layout.addStretch(1)

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

    def _batch_import_buttons(self) -> list[Button]:
        return [self.btn_import_nfo_paths, self.btn_import_nfo_folder]

    def _set_batch_import_buttons_enabled(self, enabled: bool) -> None:
        for b in self._batch_import_buttons():
            b.setEnabled(enabled)

    def _start_batch_nfo_import(self, nfo_list: list[Path], *, empty_hint: str) -> None:
        """共用：在后台线程中导入已收集的 NFO 列表并显示进度。"""
        if self._nfo_import_busy():
            self.msg.show_info("提示", "批量导入正在进行中，请稍候。")
            return

        if not nfo_list:
            self.msg.show_info("提示", empty_hint)
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

        self._set_batch_import_buttons_enabled(False)
        dialog.show()
        thread.start()

    @Slot()
    def task_import_nfo_from_video_paths(self):
        """在视频目录中查找 .nfo 并导入；番号已存在则由导入逻辑跳过。"""
        roots = [Path(p).expanduser() for p in get_video_path()]
        roots = [r for r in roots if r.is_dir()]
        if not roots:
            self.msg.show_info(
                "提示",
                "请先在「视频」设置中添加至少一个存在本地的视频文件夹路径。",
            )
            return

        nfo_list = self._collect_nfo_files(roots)
        self._start_batch_nfo_import(
            nfo_list,
            empty_hint="在已配置的视频路径下未发现 .nfo 文件。",
        )

    @Slot()
    def task_import_nfo_from_folder(self):
        """选择文件夹后递归扫描 .nfo 并批量导入。"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择包含 NFO 的文件夹",
            str(BASE_DIR),
        )
        if not folder:
            return

        root = Path(folder).expanduser().resolve()
        if not root.is_dir():
            self.msg.show_info("提示", "所选路径不是有效文件夹。")
            return

        nfo_list = self._collect_nfo_files([root])
        self._start_batch_nfo_import(
            nfo_list,
            empty_hint="所选文件夹下未发现 .nfo 文件。",
        )

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
        self._set_batch_import_buttons_enabled(True)
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

    @Slot()
    def import_work_from_nfo_file(self):
        from core.importers import import_work_from_movie_nfo

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 NFO 文件",
            str(BASE_DIR),
            "NFO 文件 (*.nfo);;所有文件 (*.*)",
        )
        if not file_path:
            return

        ok, message = import_work_from_movie_nfo(Path(file_path))
        if ok:
            self.msg.show_info("导入成功", message)
        elif "已在库中" in message:
            self.msg.show_info("未导入", message)
        else:
            self.msg.show_warning("导入失败", message)
