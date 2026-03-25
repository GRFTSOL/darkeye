from PySide6.QtWidgets import QGridLayout, QWidget
from darkeye_ui.components.token_check_box import TokenCheckBox
from darkeye_ui.components.icon_push_button import IconPushButton
from darkeye_ui.components.button import Button
import json
import logging
from webbrowser import open as open_browser
from pathlib import Path
from typing import Callable

from config import CRAWLER_NAV_BUTTONS_PATH
from utils.utils import covert_fanza


class CrawlerAutoPage(QWidget):
    """自动爬虫抓取信息页面"""
    def __init__(self):
        super().__init__()
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.cb_release_date = TokenCheckBox("发布日期")
        self.cb_director = TokenCheckBox("导演")
        self.cb_cover = TokenCheckBox("封面")
        self.cb_cn_title = TokenCheckBox("中文标题")
        self.cb_jp_title = TokenCheckBox("日文标题")
        self.cb_cn_story = TokenCheckBox("中文故事")
        self.cb_jp_story = TokenCheckBox("日文故事")
        self.cb_actress = TokenCheckBox("女优")
        self.cb_actor = TokenCheckBox("男优")
        self.cb_tag = TokenCheckBox("标签")
        self.cb_runtime = TokenCheckBox("时长")
        self.cb_maker = TokenCheckBox("片商")
        self.cb_series = TokenCheckBox("系列")
        self.cb_label = TokenCheckBox("厂牌")
        self.btn_get_crawler = IconPushButton(icon_name="arrow_down_to_line", icon_size=24, out_size=32)

        #self.cb_release_date.setChecked(True)
        #self.cb_director.setChecked(True)
        #self.cb_cn_title.setChecked(True)
        #self.cb_jp_title.setChecked(True)
        #self.cb_cn_story.setChecked(True)
        #self.cb_jp_story.setChecked(True)
        #self.cb_actress.setChecked(True)
        #self.cb_actor.setChecked(True)
        #self.cb_cover.setChecked(True)
        #self.cb_tag.setChecked(True)
        #self.cb_runtime.setChecked(True)


        layout.addWidget(self.cb_release_date, 0, 0)
        layout.addWidget(self.cb_director, 0, 1)
        layout.addWidget(self.cb_cover, 0, 2)
        layout.addWidget(self.cb_cn_title, 1, 0)
        layout.addWidget(self.cb_jp_title, 1, 1)
        layout.addWidget(self.cb_actress, 1, 2)
        layout.addWidget(self.cb_cn_story, 2, 0)
        layout.addWidget(self.cb_jp_story, 2, 1)
        layout.addWidget(self.cb_actor, 2, 2)
        layout.addWidget(self.cb_tag, 3, 0)
        layout.addWidget(self.cb_runtime, 3, 1)
        layout.addWidget(self.cb_maker, 3, 2)
        layout.addWidget(self.cb_series, 4, 0)
        layout.addWidget(self.cb_label, 4, 1)
        layout.addWidget(self.btn_get_crawler, 4, 2)


def _apply_serial_transform(serial: str, transform: str | None) -> str:
    """应用番号转换（如 fanza 格式、supjav 的 FC2 处理）。"""
    if not transform:
        return serial
    if transform == "fanza":
        return covert_fanza(serial)
    if transform == "supjav":
        return serial.split("-")[-1] if serial.strip().upper().startswith("FC2-") else serial
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
