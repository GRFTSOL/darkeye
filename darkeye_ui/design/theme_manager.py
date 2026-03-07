# design/theme_manager.py - 主题切换与 QSS 应用
from enum import Enum
from typing import TYPE_CHECKING
from pathlib import Path
import tempfile

from PySide6.QtCore import QObject, Signal

from .icon import (
    SVG_ARROW_DOWN,
    SVG_CHEVRON_DOWN,
    SVG_CHEVRON_UP,
    render_svg_to_file,
)
from .loader import load_stylesheet
from .tokens import (
    BLUE_TOKENS,
    DARK_TOKENS,
    derive_colors_from_primary,
    GREEN_TOKENS,
    LIGHT_TOKENS,
    PURPLE_TOKENS,
    RED_TOKENS,
    ThemeTokens,
    YELLOW_TOKENS,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


class ThemeId(Enum):
    LIGHT = "light"
    DARK = "dark"
    RED = "red"
    GREEN = "green"
    YELLOW = "yellow"
    BLUE = "blue"
    PURPLE = "purple"


class ThemeManager(QObject):
    """管理当前主题，加载 mymain.qss 并应用到 QApplication。"""

    themeChanged = Signal(ThemeId)

    def __init__(self, qss_filename: str = "mymain.qss", parent: QObject | None = None):
        super().__init__(parent)
        self._current = ThemeId.LIGHT
        self._custom_primary: str | None = None
        self._qss_filename = qss_filename
        self._tokens_map: dict[ThemeId, ThemeTokens] = {
            ThemeId.LIGHT: LIGHT_TOKENS,
            ThemeId.DARK: DARK_TOKENS,
            ThemeId.RED: RED_TOKENS,
            ThemeId.GREEN: GREEN_TOKENS,
            ThemeId.YELLOW: YELLOW_TOKENS,
            ThemeId.BLUE: BLUE_TOKENS,
            ThemeId.PURPLE: PURPLE_TOKENS,
        }

    def current(self) -> ThemeId:
        return self._current

    def set_current(self, theme_id: ThemeId) -> None:
        """仅更新当前主题 ID 并发出信号，不修改 QApplication 样式表。"""
        self._current = theme_id
        self.themeChanged.emit(theme_id)

    def custom_primary(self) -> str | None:
        """当前自定义主色，仅对 LIGHT/DARK 主题生效。"""
        return self._custom_primary

    def set_custom_primary(self, hex_color: str | None) -> None:
        """设置自定义主色，仅对 LIGHT/DARK 主题生效。传入 None 恢复默认。"""
        self._custom_primary = hex_color

    def tokens(self) -> ThemeTokens:
        base = self._tokens_map[self._current]
        if self._custom_primary and self._current in (ThemeId.LIGHT, ThemeId.DARK):
            derived = derive_colors_from_primary(
                self._custom_primary, is_dark=(self._current == ThemeId.DARK)
            )
            d = base.to_dict()
            d.update(derived)
            return ThemeTokens(**d)
        return base

    def set_theme(self, app: "QApplication", theme_id: ThemeId) -> None:
        """切换主题并应用样式表。"""
        self._current = theme_id
        base_dir = Path(__file__).resolve().parent.parent  # darkeye_ui 根目录
        template_path = base_dir / "styles" / self._qss_filename
        tokens = self.tokens()
        # 将内联 SVG 渲染为临时图供 QSS url() 使用
        cache_dir = Path(tempfile.gettempdir()) / "darkeye_ui"
        chevron_path = cache_dir / f"chevron_down_{theme_id.value}.png"
        chevron_path_str = render_svg_to_file(
            SVG_ARROW_DOWN,
            chevron_path,
            size=16,
            color=tokens.color_icon,
        )
        spinbox_up_path = render_svg_to_file(
            SVG_CHEVRON_UP,
            cache_dir / f"spinbox_chevron_up_{theme_id.value}.png",
            size=12,
            color=tokens.color_icon,
        )
        spinbox_down_path = render_svg_to_file(
            SVG_CHEVRON_DOWN,
            cache_dir / f"spinbox_chevron_down_{theme_id.value}.png",
            size=12,
            color=tokens.color_icon,
        )
        tokens_dict = {
            **tokens.to_dict(),
            "chevron_down_arrow_path": chevron_path_str,
            "spinbox_up_arrow_path": spinbox_up_path,
            "spinbox_down_arrow_path": spinbox_down_path,
        }
        qss = load_stylesheet(template_path, tokens_dict)
        app.setStyleSheet(qss)
        self.themeChanged.emit(theme_id)
