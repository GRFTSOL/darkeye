"""设置页面的各子模块。"""

from .common import CommonPage
from .shortcut import ShortCutSettingPage
from .crawler import ClawerSettingPage
from .database import DBSettingPage
from .about import LastPage
from .video import VideoSettingPage

__all__ = [
    "CommonPage",
    "ShortCutSettingPage",
    "ClawerSettingPage",
    "DBSettingPage",
    "LastPage",
    "VideoSettingPage",
]
