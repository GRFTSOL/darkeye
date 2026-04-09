"""设置页总入口：组装各子设置页面。"""

from PySide6.QtWidgets import QVBoxLayout

from darkeye_ui import LazyWidget
from darkeye_ui.components import ModernScrollMenu

from .settings import (
    CommonPage,
    ShortCutSettingPage,
    ClawerSettingPage,
    DBSettingPage,
    LastPage,
    NfoSettingPage,
    TranslationSettingPage,
    VideoSettingPage,
)


class SettingPage(LazyWidget):
    def __init__(self):
        super().__init__()

    def _lazy_load(self):
        page_video = VideoSettingPage()
        page_nfo = NfoSettingPage()
        page_clawer = ClawerSettingPage()
        page_db = DBSettingPage()
        page_first = LastPage()
        page_short_cut = ShortCutSettingPage()
        page_common = CommonPage()
        page_translation = TranslationSettingPage()

        my_content = {
            "常规": page_common,
            "视频": page_video,
            "NFO": page_nfo,
            "爬虫": page_clawer,
            "翻译": page_translation,
            "数据库": page_db,
            "快捷键": page_short_cut,
            "关于软件": page_first,
        }
        mainlayout = QVBoxLayout(self)
        window = ModernScrollMenu(my_content)
        mainlayout.addWidget(window)
