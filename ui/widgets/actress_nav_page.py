import json
import logging
import re
from pathlib import Path
from typing import Callable
from urllib.parse import quote
from webbrowser import open as open_browser

from PySide6.QtWidgets import QGridLayout, QWidget

from config import ACTRESS_NAV_BUTTONS_PATH
from darkeye_ui.components.button import Button
from utils.reveal_in_file_manager import reveal_file_in_os_file_manager

_TOKEN_PATTERN = re.compile(r"\{([^{}]+)\}")
_SUPPORTED_TOKENS = {"jp_name", "cn_name"}


class ActressNavPage(QWidget):
    """女优外部链接页，由 JSON 配置驱动，仅支持 jp/cn 名称占位符。"""

    def __init__(self, config_path: Path | None = None):
        super().__init__()
        self._button_configs: list[dict] = []
        self._jp_name_provider: Callable[[], str] | None = None
        self._cn_name_provider: Callable[[], str] | None = None
        self._config_path = Path(config_path) if config_path else Path(ACTRESS_NAV_BUTTONS_PATH)
        linklayout = QGridLayout(self)
        self._load_buttons(linklayout)

    def _load_buttons(self, layout: QGridLayout) -> None:
        if not self._config_path.exists():
            logging.warning("女优外部链接配置不存在: %s", self._config_path)
            return
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._button_configs = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logging.warning("加载女优外部链接配置失败: %s", e)
            return
        columns = 2
        for i, cfg in enumerate(self._button_configs):
            name = str(cfg.get("name", "") or "")
            description = str(cfg.get("description", "") or "")
            row, col = i // columns, i % columns
            btn = Button(name)
            btn.setToolTip(description)
            layout.addWidget(btn, row, col)
            btn.clicked.connect(self._make_click_handler(cfg))

        row = (len(self._button_configs) + columns - 1) // columns
        btn_reveal_json = Button("定位 JSON 配置文件")
        btn_reveal_json.setToolTip(
            "在文件管理器中选中 actress_nav_buttons.json（Windows/macOS）；"
            "其他系统则打开其所在文件夹"
        )

        def _reveal_nav_config() -> None:
            reveal_file_in_os_file_manager(self._config_path)

        btn_reveal_json.clicked.connect(_reveal_nav_config)
        layout.addWidget(btn_reveal_json, row, 0, 1, 2)

    def _make_click_handler(self, cfg: dict):
        def _on_click():
            self._open_nav_url(cfg)

        return _on_click

    def _get_provider_value(self, token: str) -> str | None:
        provider_map = {
            "jp_name": self._jp_name_provider,
            "cn_name": self._cn_name_provider,
        }
        provider = provider_map.get(token)
        if provider is None:
            return None
        return (provider() or "").strip()

    def _open_nav_url(self, cfg: dict) -> None:
        url_template = str(cfg.get("url", "") or "").strip()
        if not url_template:
            logging.warning("女优外部链接配置缺少 url: %s", cfg)
            return

        found_tokens = set(_TOKEN_PATTERN.findall(url_template))
        unsupported = [t for t in found_tokens if t not in _SUPPORTED_TOKENS]
        if unsupported:
            logging.warning("发现不支持的占位符 %s，已跳过: %s", unsupported, url_template)
            return

        quote_tokens_raw = cfg.get("quote", [])
        if not isinstance(quote_tokens_raw, list):
            quote_tokens_raw = []
        quote_tokens = {str(t) for t in quote_tokens_raw if str(t) in _SUPPORTED_TOKENS}

        url = url_template
        for token in found_tokens:
            value = self._get_provider_value(token)
            if not value:
                logging.warning("占位符 %s 无可用值，已跳过: %s", token, url_template)
                return
            if token in quote_tokens:
                value = quote(value, safe="")
            url = url.replace(f"{{{token}}}", value)

        if _TOKEN_PATTERN.search(url):
            logging.warning("链接仍包含未替换占位符，已跳过: %s", url)
            return

        open_browser(url)

    def set_jp_name_provider(self, provider: Callable[[], str]) -> None:
        self._jp_name_provider = provider

    def set_cn_name_provider(self, provider: Callable[[], str]) -> None:
        self._cn_name_provider = provider

    def set_name_providers(
        self, jp_name_provider: Callable[[], str], cn_name_provider: Callable[[], str]
    ) -> None:
        self._jp_name_provider = jp_name_provider
        self._cn_name_provider = cn_name_provider
