# darkeye_ui/components/circular_loading.py - 圆形动态加载指示器，由设计令牌驱动
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, QSize, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget

from ..design.theme_context import resolve_theme_manager
from ..design.tokens import ThemeTokens, LIGHT_TOKENS

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


def _parse_border_width(value: str) -> int:
    """解析 border_width 令牌（如 '2px'）为整数像素。"""
    try:
        return int(value.replace("px", "").strip() or "2")
    except (ValueError, AttributeError):
        return 2


class CircularLoading(QWidget):
    """圆形动态加载指示器：轨道与弧线颜色由设计令牌驱动，支持主题切换时刷新。"""

    def __init__(
        self,
        size: int = 32,
        stroke_width: Optional[int] = None,
        theme_manager: Optional["ThemeManager"] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("CircularLoading")
        self.setFixedSize(size, size)
        self._size = size
        self._stroke_width = stroke_width  # None 时从 border_width 解析

        theme_manager = resolve_theme_manager(theme_manager, "CircularLoading")
        self._theme_manager = theme_manager

        self._angle = 0.0  # 弧线起始角度，随时间累加实现旋转
        self._arc_color = QColor("#00aaff")
        self._track_color = QColor("#ccc")
        self._stroke = 2

        self._apply_tokens()

        self._timer = QTimer(self)
        self._timer.setInterval(40)  # ~25 fps
        self._timer.timeout.connect(self._tick)

        if theme_manager is not None:
            theme_manager.themeChanged.connect(self._on_theme_changed)

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _apply_tokens(self) -> None:
        t = self._tokens()
        self._arc_color = QColor(t.color_primary)
        self._track_color = QColor(t.color_text_disabled)
        sw = self._stroke_width
        if sw is None:
            sw = max(
                4, _parse_border_width(t.border_width) * 2
            )  # 令牌值的 2 倍，至少 4px
        self._stroke = max(2, min(sw, self._size // 3))

    def _on_theme_changed(self) -> None:
        self._apply_tokens()
        self.update()

    def _tick(self) -> None:
        self._angle = (self._angle + 8) % 360
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = self.rect()
        # 整体缩进 stroke/2，避免笔刷超出控件被裁剪（左右上下的边缘会被切掉）
        margin = self._stroke / 2
        w = max(0, rect.width() - 2 * margin)
        h = max(0, rect.height() - 2 * margin)
        r = min(w, h) / 2
        if r <= 0:
            painter.end()
            return

        x = margin + (w - 2 * r) / 2
        y = margin + (h - 2 * r) / 2
        rect_f = QRectF(x, y, 2 * r, 2 * r)

        # 轨道（整圆，细线）
        pen = QPen(self._track_color, self._stroke)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(rect_f, 0, 360 * 16)

        # 弧线（约 90 度，随 _angle 旋转）
        pen.setColor(self._arc_color)
        painter.setPen(pen)
        start = int(self._angle * 16)
        span = -90 * 16  # 逆时针 90 度
        painter.drawArc(rect_f, start, span)

        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(self._size, self._size)
