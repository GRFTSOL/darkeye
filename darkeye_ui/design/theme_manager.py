# design/theme_manager.py - 主题切换与 QSS 应用
from enum import Enum
from typing import TYPE_CHECKING
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .loader import load_stylesheet
from .tokens import DARK_TOKENS, LIGHT_TOKENS, RED_TOKENS, ThemeTokens

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


class ThemeId(Enum):
    LIGHT = "light"
    DARK = "dark"
    RED = "red"


class ThemeManager(QObject):
    """管理当前主题，加载 mymain.qss 并应用到 QApplication。"""

    themeChanged = Signal(ThemeId)

    def __init__(self, qss_filename: str = "mymain.qss", parent: QObject | None = None):
        super().__init__(parent)
        self._current = ThemeId.LIGHT
        self._qss_filename = qss_filename
        self._tokens_map: dict[ThemeId, ThemeTokens] = {
            ThemeId.LIGHT: LIGHT_TOKENS,
            ThemeId.DARK: DARK_TOKENS,
            ThemeId.RED: RED_TOKENS,
        }

    def current(self) -> ThemeId:
        return self._current

    def set_current(self, theme_id: ThemeId) -> None:
        """仅更新当前主题 ID 并发出信号，不修改 QApplication 样式表。"""
        self._current = theme_id
        self.themeChanged.emit(theme_id)

    def tokens(self) -> ThemeTokens:
        return self._tokens_map[self._current]

    def set_theme(self, app: "QApplication", theme_id: ThemeId) -> None:
        """切换主题并应用样式表。"""
        self._current = theme_id
        base_dir = Path(__file__).resolve().parent.parent  # darkeye_ui 根目录
        template_path = base_dir / "styles" / self._qss_filename
        qss = load_stylesheet(template_path, self.tokens())
        app.setStyleSheet(qss)
        self.themeChanged.emit(theme_id)
