# darkeye_ui/components/callout_tooltip.py - 自绘尖角提示框
"""呼出式提示框：圆角矩形 + 左侧指向目标控件的三角形尖角，由设计令牌驱动。"""
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .._logging import get_logger, warn_once
from ..design.theme_context import resolve_theme_manager
from ..design.tokens import ThemeTokens, LIGHT_TOKENS

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


def _parse_radius(radius_str: str) -> int:
    """从 '8px' 等字符串解析出数值。"""
    s = str(radius_str).strip().rstrip("px")
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 8


class CalloutTooltip(QWidget):
    """
    自绘尖角提示框：在目标控件右侧弹出，左侧有指向目标的三角形尖角。
    - 使用 ThemeTokens 驱动颜色与字体
    - show_for(widget, text) 根据 widget 全局几何定位
    """

    PADDING_LEFT = 12   # 尖角已占 6px，6+6=12 与右侧对齐
    PADDING_RIGHT = 18
    PADDING_V = 6
    GAP = 0
    ARROW_SIZE = 6

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        theme_manager: Optional["ThemeManager"] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._text = ""
        self._tokens: Optional[ThemeTokens] = None
        self._logger = get_logger(__name__)
        self._theme_manager = resolve_theme_manager(theme_manager, "CalloutTooltip")

    def _get_tokens(self) -> ThemeTokens:
        if self._tokens is not None:
            return self._tokens
        mgr = self._theme_manager
        if mgr is not None:
            try:
                return mgr.tokens()
            except (AttributeError, RuntimeError, TypeError) as exc:
                warn_once(
                    self._logger,
                    "CalloutTooltip:theme_tokens_failed",
                    "CalloutTooltip: failed to read theme tokens, fallback to LIGHT_TOKENS.",
                    exc_info=exc,
                )
        return LIGHT_TOKENS

    def set_tokens(self, tokens: ThemeTokens) -> None:
        self._tokens = tokens
        self.update()

    def show_for(self, widget: QWidget, text: str) -> None:
        if not text:
            self.hide()
            return
        self._text = text
        t = self._get_tokens()
        font = QFont(t.font_family_base)
        px = _parse_radius(t.font_size_base) if "px" in str(t.font_size_base) else 12
        font.setPixelSize(px)
        self.setFont(font)
        fm = self.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        w = tw + self.PADDING_LEFT + self.PADDING_RIGHT + self.ARROW_SIZE
        h = th + self.PADDING_V * 2
        self.setFixedSize(int(w), int(h))
        self.update()

        top_right = widget.mapToGlobal(widget.rect().topRight())
        x = top_right.x() + self.GAP
        y = top_right.y() + (widget.height() - h) // 2
        self.move(int(x), int(y))
        self.show()
        self.raise_()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        t = self._get_tokens()
        arr = self.ARROW_SIZE
        rect_w = self.width() - arr
        rect_h = self.height()
        x, y = 0.0, 0.0

        path = QPainterPath()
        path.moveTo(x + arr, y)
        path.lineTo(x + rect_w, y)
        path.lineTo(x + rect_w, y + rect_h)
        path.lineTo(x + arr, y + rect_h)
        path.lineTo(x + arr, y + rect_h // 2 + arr)
        path.lineTo(x, y + rect_h // 2)
        path.lineTo(x + arr, y + rect_h // 2 - arr)
        path.lineTo(x + arr, y)
        path.closeSubpath()

        bg = QColor(t.color_bg_input)
        border = QColor(t.color_border)
        painter.setPen(QPen(border, 1))
        painter.setBrush(QBrush(bg))
        painter.drawPath(path)

        text_color = QColor(t.color_text)
        painter.setPen(text_color)
        tx = x + arr + self.PADDING_LEFT
        ty = y + self.PADDING_V + self.fontMetrics().ascent()
        painter.drawText(int(tx), int(ty), self._text)
