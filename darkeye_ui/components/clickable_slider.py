# ui/components/clickable_slider.py - 可点击跳转的滑块，由设计令牌驱动样式，支持主题切换
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSlider

from ..design.theme_context import resolve_theme_manager
from ..design.tokens import ThemeTokens, LIGHT_TOKENS

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


def _slider_style_from_tokens(tokens: ThemeTokens) -> str:
    """根据主题令牌生成滑块样式表。"""
    groove = tokens.color_bg_page if hasattr(tokens, "color_bg_page") else "#d0d0d0"
    handle = tokens.color_primary
    return f"""
    QSlider::groove:horizontal {{
        height: 4px;
        background: {groove};
        margin: 0px;
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {handle};
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}
    QSlider::groove:vertical {{
        width: 4px;
        background: {groove};
        margin: 0px;
        border-radius: 2px;
    }}
    QSlider::handle:vertical {{
        background: {handle};
        width: 14px;
        height: 14px;
        margin: 0 -5px;
        border-radius: 7px;
    }}
    """


class ClickableSlider(QSlider):
    """可点击跳转的滑块，由设计令牌驱动颜色，支持主题切换。"""

    def __init__(
        self,
        orientation=Qt.Orientation.Horizontal,
        parent=None,
        theme_manager: Optional["ThemeManager"] = None,
    ):  # type: ignore[arg-type]
        super().__init__(orientation, parent)
        theme_manager = resolve_theme_manager(theme_manager, "ClickableSlider")
        self._theme_manager = theme_manager

        # 为高 DPI / 不同屏幕缩放预留足够空间，避免手柄在某些缩放下被裁剪
        if self.orientation() == Qt.Orientation.Horizontal:
            # 轨道 4px，高度至少 22px，确保 14px 圆形手柄有富余空间
            self.setMinimumHeight(22)
        else:
            self.setMinimumWidth(22)

        self.setStyleFromTokens(LIGHT_TOKENS)
        if theme_manager is not None:
            theme_manager.themeChanged.connect(self._on_theme_changed)

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _on_theme_changed(self) -> None:
        self.setStyleFromTokens(self._tokens())

    def setStyleFromTokens(self, tokens: ThemeTokens) -> None:
        """根据主题令牌更新滑块样式。"""
        self.setStyleSheet(_slider_style_from_tokens(tokens))

    def mousePressEvent(self, event):
        """Handle mouse press to jump to clicked position."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.orientation() == Qt.Orientation.Horizontal:
                ratio = event.position().x() / max(1, self.width())
            else:
                ratio = 1.0 - event.position().y() / max(1, self.height())
            ratio = float(max(0.0, min(1.0, ratio)))
            value = self.minimum() + int(
                round(ratio * (self.maximum() - self.minimum()))
            )
            self.setValue(value)
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        """Disable wheel scroll from changing the slider value; pass event to parent."""
        event.ignore()
