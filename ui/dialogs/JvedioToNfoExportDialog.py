"""配置并从 Jvedio（app_datas.sqlite）导出 Kodi 风格 NFO。"""

from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from darkeye_ui.components import Button, Label
from darkeye_ui.components.input import LineEdit


class JvedioToNfoExportDialog(QDialog):
    """收集 Jvedio2NFO 导出所需的配置项。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("从 Jvedio 导出 NFO")
        self.setMinimumWidth(580)

        self._db_edit = LineEdit(self)
        self._db_edit.setPlaceholderText("app_datas.sqlite 的完整路径")

        self._out_edit = LineEdit(self)
        self._out_edit.setPlaceholderText("NFO 输出目录，这个一定要选一个文件夹，否则会到软件目录")

        self._chk_write_video = QCheckBox("若影片路径存在，将 NFO 写入视频所在目录")

        self._chk_download = QCheckBox("下载演员与海报图片（需安装 requests）")

        self._image_dir_edit = LineEdit(self)
        self._image_dir_edit.setPlaceholderText(
            "图片保存目录（可留空则使用上面的输出目录）"
        )

        self._sample_edit = LineEdit(self)
        self._sample_edit.setPlaceholderText("留空 = 全部；填数字 = 仅前 N 条（一般不填，除非测试）")

        self._pic_root_edit = LineEdit(self)
        self._pic_root_edit.setPlaceholderText(
            "Jvedio 图片根目录（通常含 BigPic / SmallPic）"
        )

        self._bigpic_edit = LineEdit(self)
        self._bigpic_edit.setText("BigPic")
        self._smallpic_edit = LineEdit(self)
        self._smallpic_edit.setText("SmallPic")

        self._chk_fallback = QCheckBox("本地无图时回退为在线图片 URL")
        self._chk_fallback.setChecked(True)

        form = QFormLayout()
        form.addRow(
            Label("数据库："), self._make_path_row(self._db_edit, file_mode=True)
        )
        form.addRow(
            Label("输出目录："), self._make_path_row(self._out_edit, file_mode=False)
        )
        form.addRow(self._chk_write_video)
        form.addRow(self._chk_download)
        form.addRow(
            Label("图片保存目录："),
            self._make_path_row(self._image_dir_edit, file_mode=False),
        )
        form.addRow(Label("条数限制："), self._sample_edit)
        form.addRow(
            Label("本地图片根目录："),
            self._make_path_row(self._pic_root_edit, file_mode=False),
        )
        form.addRow(Label("BigPic 子目录名："), self._bigpic_edit)
        form.addRow(Label("SmallPic 子目录名："), self._smallpic_edit)
        form.addRow(self._chk_fallback)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._try_accept)
        btns.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(btns)

    def _make_path_row(self, edit: LineEdit, *, file_mode: bool) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(edit, stretch=1)
        btn = Button("浏览…")
        if file_mode:
            btn.clicked.connect(lambda: self._browse_file(edit))
        else:
            btn.clicked.connect(lambda: self._browse_dir(edit))
        h.addWidget(btn)
        return w

    @staticmethod
    def _browse_file(edit: LineEdit):
        path, _ = QFileDialog.getOpenFileName(
            edit.window(),
            "选择 app_datas.sqlite",
            "",
            "SQLite 数据库 (*.sqlite);;所有文件 (*.*)",
        )
        if path:
            edit.setText(path)

    @staticmethod
    def _browse_dir(edit: LineEdit):
        path = QFileDialog.getExistingDirectory(
            edit.window(),
            "选择目录",
            edit.text() or "",
        )
        if path:
            edit.setText(path)

    @Slot()
    def _try_accept(self):
        db = self._db_edit.text().strip()
        if not db:
            QMessageBox.warning(
                self, "提示", "请填写 Jvedio 数据库路径（app_datas.sqlite）。"
            )
            return
        if not Path(db).is_file():
            QMessageBox.warning(
                self,
                "提示",
                f"数据库文件不存在或不是文件：\n{db}",
            )
            return

        raw_sample = self._sample_edit.text().strip()
        if raw_sample:
            try:
                n = int(raw_sample)
            except ValueError:
                QMessageBox.warning(
                    self,
                    "提示",
                    "「条数限制」请留空或填写正整数。",
                )
                return
            if n <= 0:
                QMessageBox.warning(self, "提示", "「条数限制」须为正整数。")
                return

        self.accept()

    def export_kwargs(self) -> dict:
        """传给 `export_jvedio_database_to_nfo` 的关键字参数。"""
        raw_sample = self._sample_edit.text().strip()
        sample_limit = None
        if raw_sample:
            sample_limit = int(raw_sample)
        out = self._out_edit.text().strip()
        return {
            "db_path": self._db_edit.text().strip(),
            "output_dir": out if out else ".",
            "write_nfo_to_video_dir": self._chk_write_video.isChecked(),
            "download_images": self._chk_download.isChecked(),
            "image_save_dir": self._image_dir_edit.text().strip(),
            "sample_limit": sample_limit,
            "pic_root": self._pic_root_edit.text().strip(),
            "bigpic_dir": self._bigpic_edit.text().strip() or "BigPic",
            "smallpic_dir": self._smallpic_edit.text().strip() or "SmallPic",
            "fallback_to_online_image_url": self._chk_fallback.isChecked(),
        }
