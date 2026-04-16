"""爬虫相关设置页面。"""

from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QVBoxLayout, QWidget

from config import (
    DEFAULT_ACTRESS_API_BASE_URL,
    DEFAULT_WORK_API_BASE_URL,
    get_actress_api_base_url,
    get_work_api_base_url,
    set_actress_api_base_url,
    set_work_api_base_url,
)
from darkeye_ui.components import Button
from darkeye_ui.components.input import LineEdit
from darkeye_ui.components.label import Label


class ClawerSettingPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(Label("<h3>爬虫相关设置</h3>"))
        self._loading_settings = False

        form = QFormLayout()
        self.work_api_base_url_edit = LineEdit(self)
        self.work_api_base_url_edit.setPlaceholderText(DEFAULT_WORK_API_BASE_URL)
        self.work_reset_btn = Button("还原默认")
        work_row = QHBoxLayout()
        work_row.addWidget(self.work_api_base_url_edit)
        work_row.addWidget(self.work_reset_btn)
        form.addRow(Label("作品 API 前缀"), work_row)

        self.actress_api_base_url_edit = LineEdit(self)
        self.actress_api_base_url_edit.setPlaceholderText(DEFAULT_ACTRESS_API_BASE_URL)
        self.actress_reset_btn = Button("还原默认")
        actress_row = QHBoxLayout()
        actress_row.addWidget(self.actress_api_base_url_edit)
        actress_row.addWidget(self.actress_reset_btn)
        form.addRow(Label("女优 API 前缀"), actress_row)

        form.addRow(
            Label(
                "请直接填写完整前缀，例如 .../api/v1/work 与 .../api/v1/actress；"
                "代码会在其后追加 /{serial} 或 /{name}。其余接口仍固定默认地址。"
            )
        )
        layout.addLayout(form)

        self._load_settings()
        self.work_api_base_url_edit.editingFinished.connect(self._on_setting_changed)
        self.actress_api_base_url_edit.editingFinished.connect(self._on_setting_changed)
        self.work_reset_btn.clicked.connect(self._reset_work_api_to_default)
        self.actress_reset_btn.clicked.connect(self._reset_actress_api_to_default)

    def _load_settings(self) -> None:
        self._loading_settings = True
        self.work_api_base_url_edit.setText(get_work_api_base_url())
        self.actress_api_base_url_edit.setText(get_actress_api_base_url())
        self._loading_settings = False

    def _on_setting_changed(self) -> None:
        if self._loading_settings:
            return
        set_work_api_base_url(self.work_api_base_url_edit.text())
        set_actress_api_base_url(self.actress_api_base_url_edit.text())
        self.work_api_base_url_edit.setText(get_work_api_base_url())
        self.actress_api_base_url_edit.setText(get_actress_api_base_url())

    def _reset_work_api_to_default(self) -> None:
        set_work_api_base_url(DEFAULT_WORK_API_BASE_URL)
        self.work_api_base_url_edit.setText(get_work_api_base_url())

    def _reset_actress_api_to_default(self) -> None:
        set_actress_api_base_url(DEFAULT_ACTRESS_API_BASE_URL)
        self.actress_api_base_url_edit.setText(get_actress_api_base_url())
