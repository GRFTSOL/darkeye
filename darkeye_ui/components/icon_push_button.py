# ui/components/icon_push_button.py - 仅图标的按钮，样式由 QSS + 令牌驱动
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QPushButton

from ..design import get_builtin_icon, svg_to_icon
from ..design.tokens import ThemeTokens, LIGHT_TOKENS

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class IconPushButton(QPushButton):
    """仅图标的按钮：图标与样式由设计令牌驱动，支持主题切换时刷新。
    可通过 icon_name 使用内置图标，或通过 icon_path 指定外部 SVG 文件路径。
    inverted=True 时使用 color_text_inverse 显示图标，适用于深色背景上的浅色图标。
    """

    def __init__(
        self,
        icon_name: str = "settings",
        icon_path: Optional[Union[str, Path]] = None,
        icon_size: int = 24,
        out_size: int = 32,
        hoverable: bool = True,
        inverted: bool = False,
        theme_manager: Optional["ThemeManager"] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("DesignIconPushButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self._icon_name = icon_name
        self._icon_path = icon_path
        self._icon_size = icon_size
        self._out_size = out_size
        self._hoverable = hoverable
        self._inverted = inverted
        # 未传入时尝试从应用上下文获取全局 ThemeManager，使主题切换时图标能更新
        if theme_manager is None:
            try:
                from app_context import get_theme_manager
                theme_manager = get_theme_manager()
            except Exception:
                pass
        self._theme_manager = theme_manager

        self.setIconSize(QSize(icon_size, icon_size))
        self.setFixedSize(out_size, out_size)
        self._refresh_icon()

        if theme_manager is not None:
            theme_manager.themeChanged.connect(self._refresh_icon)

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _refresh_icon(self) -> None:
        t = self._tokens()
        color = t.color_text_inverse if self._inverted else t.color_icon
        if self._icon_path is not None:
            self.setIcon(
                svg_to_icon(self._icon_path, size=self._icon_size, color=color)
            )
        else:
            self.setIcon(
                get_builtin_icon(self._icon_name, size=self._icon_size, color=color)
            )

    def set_icon_name(self, icon_name: str) -> None:
        self._icon_name = icon_name
        self._icon_path = None
        self._refresh_icon()

    def set_icon_path(self, icon_path: Optional[Union[str, Path]]) -> None:
        """设置外部 SVG 文件路径；传 None 则恢复使用当前 icon_name 对应的内置图标。"""
        self._icon_path = icon_path
        self._refresh_icon()

    def sizeHint(self) -> QSize:
        return QSize(self._out_size, self._out_size)
