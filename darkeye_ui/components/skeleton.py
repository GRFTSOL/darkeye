from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from ..design.theme_context import resolve_theme_manager
from ..design.tokens import LIGHT_TOKENS, ThemeTokens

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class Skeleton(QWidget):
    """Animated skeleton placeholder for loading state."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        height: int = 14,
        radius: int = 6,
        theme_manager: Optional["ThemeManager"] = None,
        animated: bool = True,
        interval_ms: int = 35,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DesignSkeleton")
        self.setMinimumHeight(max(6, height))
        self.setMaximumHeight(max(6, height))
        self._radius = max(0, radius)
        self._offset = 0

        self._theme_manager = resolve_theme_manager(theme_manager, "Skeleton")
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._on_theme_changed)

        self._timer = QTimer(self)
        self._timer.setInterval(max(16, interval_ms))
        self._timer.timeout.connect(self._tick)
        if animated:
            self.start()

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        if self._timer.isActive():
            self._timer.stop()

    def set_animated(self, value: bool) -> None:
        if value:
            self.start()
        else:
            self.stop()

    def _tick(self) -> None:
        self._offset = (self._offset + 6) % 240
        self.update()

    def _base_colors(self) -> tuple[QColor, QColor]:
        t = self._tokens()
        base = QColor(t.color_bg_input)
        hilite = QColor(t.color_border)
        if base.lightness() > hilite.lightness():
            hilite = base.darker(106)
        else:
            hilite = base.lighter(112)
        return base, hilite

    def paintEvent(self, event: QPaintEvent) -> None:
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(0, 0, -1, -1)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        base, hilite = self._base_colors()
        gradient = QLinearGradient(
            float(rect.left() - rect.width() + self._offset),
            float(rect.top()),
            float(rect.left() + self._offset),
            float(rect.bottom()),
        )
        gradient.setColorAt(0.0, base)
        gradient.setColorAt(0.5, hilite)
        gradient.setColorAt(1.0, base)
        painter.setPen(QColor(base))
        painter.setBrush(gradient)
        painter.drawRoundedRect(rect, self._radius, self._radius)

    def _on_theme_changed(self, *_args) -> None:
        self.update()
