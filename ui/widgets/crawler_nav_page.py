import json
import logging
from pathlib import Path
from typing import Callable
from webbrowser import open as open_browser

from PySide6.QtWidgets import QGridLayout, QWidget
from darkeye_ui.components.token_check_box import TokenCheckBox
from darkeye_ui.components.icon_push_button import IconPushButton
from darkeye_ui.components.button import Button

from config import CRAWLER_NAV_BUTTONS_PATH
from utils.reveal_in_file_manager import reveal_file_in_os_file_manager
from utils.utils import convert_fanza


def _apply_serial_transform(serial: str, transform: str | None) -> str:
    """应用番号转换（如 fanza 格式、supjav 的 FC2 处理）。"""
    if not transform:
        return serial
    if transform == "fanza":
        return convert_fanza(serial)
    if transform == "supjav":
        return (
            serial.split("-")[-1]
            if serial.strip().upper().startswith("FC2-")
            else serial
        )
    return serial


class CrawlerManualNavPage(QWidget):
    """手动导航页面，由外部 JSON 配置驱动（按钮名、跳转 URL、可选番号转换、说明）。"""

    def __init__(self):
        super().__init__()
        self._serial_provider: Callable[[], str] | None = None
        self._button_configs: list[dict] = []
        linklayout = QGridLayout(self)
        self._load_buttons(linklayout)

    def _load_buttons(self, layout: QGridLayout) -> None:
        path = Path(CRAWLER_NAV_BUTTONS_PATH)
        if not path.exists():
            logging.warning("手动导航按钮配置不存在: %s", path)
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._button_configs = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logging.warning("加载手动导航按钮配置失败: %s", e)
            return
        columns = 2
        for i, cfg in enumerate(self._button_configs):
            name = cfg.get("name", "")
            description = cfg.get("description", "")
            row, col = i // columns, i % columns
            btn = Button(name)
            btn.setToolTip(description)
            layout.addWidget(btn, row, col)
            btn.clicked.connect(self._make_click_handler(cfg))

        row = (len(self._button_configs) + columns - 1) // columns
        btn_reveal_json = Button("定位 JSON 配置文件")
        btn_reveal_json.setToolTip(
            "在文件管理器中选中 crawler_nav_buttons.json（Windows/macOS）；"
            "其他系统则打开其所在文件夹"
        )

        def _reveal_nav_config() -> None:
            reveal_file_in_os_file_manager(path)

        btn_reveal_json.clicked.connect(_reveal_nav_config)
        layout.addWidget(btn_reveal_json, row, 0, 1, 2)

    def _make_click_handler(self, cfg: dict):
        def _on_click():
            self._open_nav_url(cfg)

        return _on_click

    def _open_nav_url(self, cfg: dict) -> None:
        url_template = cfg.get("url", "")
        serial_transform = cfg.get("serial_transform")
        if "{serial}" not in url_template:
            open_browser(url_template)
            return
        if not self._serial_provider:
            logging.warning("未设置番号提供者，无法打开带番号的链接")
            return
        serial = self._serial_provider().strip()
        serial = _apply_serial_transform(serial, serial_transform)
        url = url_template.replace("{serial}", serial)
        open_browser(url)

    def set_serial_number_provider(self, provider: Callable[[], str]) -> None:
        """设置获取当前番号的回调，用于带 {serial} 的链接。"""
        self._serial_provider = provider
