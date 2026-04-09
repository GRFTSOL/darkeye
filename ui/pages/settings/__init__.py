"""设置页面的各子模块。"""

from .common import CommonPage
from .shortcut import ShortCutSettingPage
from .crawler import ClawerSettingPage
from .database import DBSettingPage
from .about import LastPage
from .video import VideoSettingPage
from .nfo import NfoSettingPage
from .translation import TranslationSettingPage

__all__ = [
    "CommonPage",
    "ShortCutSettingPage",
    "ClawerSettingPage",
    "DBSettingPage",
    "LastPage",
    "NfoSettingPage",
    "VideoSettingPage",
    "TranslationSettingPage",
]
