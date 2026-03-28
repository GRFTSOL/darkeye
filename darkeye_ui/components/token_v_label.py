# darkeye_ui/components/token_v_label.py - 竖排标签，由设计令牌驱动
"""竖排标签（带孔、倒角、中英混排），颜色可由令牌驱动或显式传入。"""

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QDateTime, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath
from PySide6.QtWidgets import QLabel

from ..design.theme_context import resolve_theme_manager
from ..design.tokens import LIGHT_TOKENS, ThemeTokens

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class TokenVLabel(QLabel):
    """竖排标签：背景、文字、边框、悬浮色由设计令牌驱动；显式传入时优先使用传入值。
    支持主题切换时自动刷新。
    """

    def __init__(
        self,
        text: str = "",
        background_color: Optional[str] = None,
        text_color: Optional[str] = None,
        fixed_width: Optional[int] = None,
        fixed_height: Optional[int] = None,
        border_color: Optional[str] = None,
        hover_color: Optional[str] = None,
        theme_manager: Optional["ThemeManager"] = None,
        parent=None,
    ):
        super().__init__(text, parent)
        self.setWordWrap(False)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self._hovered = False

        self.chinese_font = QFont("KaiTi", 12)
        self.chinese_font.setBold(True)
        self.english_font = QFont("Courier New", 14)
        self.english_font.setBold(True)
        self.setFont(self.english_font)

        self.corner_cut_ratio = 0.2
        self.hole_radius_ratio = 0.1

        theme_manager = resolve_theme_manager(theme_manager, "TokenVLabel")
        self._theme_manager = theme_manager
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._on_theme_changed)

        self._explicit_bg = background_color
        self._explicit_text = text_color
        self._explicit_border = border_color
        self._explicit_hover = hover_color
        t = self._tokens()
        self.background_color = QColor(background_color or t.color_bg_page)
        self.text_color = QColor(text_color or t.color_text)
        self.border_color = QColor(border_color or t.color_border)
        self.hover_color = QColor(hover_color or t.color_primary)

        self._fixed_size = self._calculate_size(fixed_width, fixed_height)
        self.setFixedSize(self._fixed_size)

        self._flash_timer = QTimer(self)
        self._flash_timer.timeout.connect(self._flash_toggle)
        self._flash_running = False
        self._flash_end_time = None
        self._flash_interval = 300
        self._flash_inverted = False

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _on_theme_changed(self) -> None:
        """主题切换时，仅更新未显式传入的颜色。"""
        t = self._tokens()
        if self._explicit_bg is None:
            self.background_color = QColor(t.color_bg_page)
        if self._explicit_text is None:
            self.text_color = QColor(t.color_text)
        if self._explicit_border is None:
            self.border_color = QColor(t.color_border)
        if self._explicit_hover is None:
            self.hover_color = QColor(t.color_primary)
        self.update()

    def setTextDynamic(self, new_text: str) -> None:
        new_text = new_text or ""
        super().setText(new_text)
        self._fixed_size = self._calculate_size(None, None)
        self.setFixedSize(self._fixed_size)
        self.update()

    def setColors(
        self, background_color: str, text_color: str, hover_color: Optional[str] = None
    ) -> None:
        self.background_color = QColor(background_color)
        self.text_color = QColor(text_color)
        if hover_color:
            self.hover_color = QColor(hover_color)
        self.update()

    def _calculate_size(self, fixed_width, fixed_height):
        if fixed_width and fixed_height:
            return QSize(fixed_width, fixed_height)
        metrics_cn = QFontMetrics(self.chinese_font)
        standard_char_width = metrics_cn.horizontalAdvance("中")
        width = int(standard_char_width * 1.7)
        if self.text() == "":
            return QSize(width, width * 2)
        total_height = 0
        for ch in self.text():
            if ch == "\n":
                continue
            fm = QFontMetrics(self._select_font(ch))
            if self.is_chinese(ch):
                char_height = fm.height()
            else:
                char_height = fm.ascent() + fm.descent() * 0.3
            total_height += char_height
        font = self._select_font(self.text()[0])
        fm = QFontMetrics(font)
        char_width = fm.horizontalAdvance(self.text()[0])
        fmodify = (
            char_width * 0.1 if self.is_chinese(self.text()[0]) else char_width * 0.4
        )
        height = (
            total_height
            + width * self.corner_cut_ratio * 3
            + width * self.hole_radius_ratio * 2
            - fm.descent() * 0.3
            - fmodify
        )
        return QSize(width, int(height))

    def is_chinese(self, char: str) -> bool:
        return 0x4E00 <= ord(char) <= 0x9FFF or "\u3040" <= char <= "\u30ff"

    def _select_font(self, char: str) -> QFont:
        if "\u4e00" <= char <= "\u9fff" or "\u3040" <= char <= "\u30ff":
            return self.chinese_font
        return self.english_font

    def sizeHint(self) -> QSize:
        return self._fixed_size

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        cut = rect.width() * self.corner_cut_ratio
        hole_radius = rect.width() * self.hole_radius_ratio

        outer_path = QPainterPath()
        outer_path.moveTo(cut, 0)
        outer_path.lineTo(rect.width() - cut, 0)
        outer_path.lineTo(rect.width(), cut)
        outer_path.lineTo(rect.width(), rect.height() - cut)
        outer_path.lineTo(rect.width() - cut, rect.height())
        outer_path.lineTo(cut, rect.height())
        outer_path.lineTo(0, rect.height() - cut)
        outer_path.lineTo(0, cut)
        outer_path.closeSubpath()

        hole_path = QPainterPath()
        hole_center_x = rect.width() // 2
        hole_center_y = cut + hole_radius
        hole_path.addEllipse(
            hole_center_x - hole_radius,
            hole_center_y - hole_radius,
            hole_radius * 2,
            hole_radius * 2,
        )
        outer_path2 = outer_path.subtracted(hole_path)

        painter.setClipPath(outer_path2)
        painter.fillRect(rect, self.background_color)
        painter.setClipping(False)

        t = self._tokens()
        out_color = QColor(t.color_primary) if self._hovered else self.border_color

        painter.setPen(self.border_color)
        painter.drawPath(outer_path)
        painter.setPen(out_color)
        painter.drawPath(hole_path)

        metrics_cn = QFontMetrics(self.chinese_font)
        max_char_width = metrics_cn.horizontalAdvance("中")
        fmodify = 0
        if self.text() != "":
            font = self._select_font(self.text()[0])
            fm = QFontMetrics(font)
            char_width = fm.horizontalAdvance(self.text()[0])
            fmodify = (
                char_width * 0.1
                if self.is_chinese(self.text()[0])
                else char_width * 0.4
            )
        y = cut * 2 + hole_radius * 2 - fmodify

        for char in self.text():
            if char == "\n":
                continue
            font = self._select_font(char)
            painter.setFont(font)
            painter.setPen(self.hover_color if self._hovered else self.text_color)
            fm = QFontMetrics(font)
            char_width = fm.horizontalAdvance(char)
            if self.is_chinese(char):
                char_height = fm.height()
            else:
                char_height = fm.ascent() + fm.descent() * 0.3
            char_x = (rect.width() - max_char_width) // 2 + (
                max_char_width - char_width
            ) // 2
            painter.drawText(char_x, y + fm.ascent(), char)
            y += char_height
        painter.end()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def flash_invert(
        self, duration=3000, interval=300, flash_bg_color=None, flash_text_color=None
    ):
        from utils.utils import invert_color

        if not hasattr(self, "_original_bg"):
            self._original_bg = self.background_color
            self._original_text = self.text_color
        self._flash_bg_color = flash_bg_color or invert_color(self._original_bg)
        self._flash_text_color = flash_text_color or invert_color(self._original_text)
        self._flash_interval = interval
        now = QDateTime.currentMSecsSinceEpoch()
        self._flash_end_time = now + duration
        if not self._flash_timer.isActive():
            self._flash_timer.start(self._flash_interval)
        self._flash_running = True

    def _flash_toggle(self):
        now = QDateTime.currentMSecsSinceEpoch()
        if now >= self._flash_end_time:
            self.background_color = self._original_bg
            self.text_color = self._original_text
            self.update()
            self._flash_timer.stop()
            self._flash_running = False
            self._flash_inverted = False
            return
        if self._flash_inverted:
            self.background_color = self._original_bg
            self.text_color = self._original_text
        else:
            self.background_color = self._flash_bg_color
            self.text_color = self._flash_text_color
        self._flash_inverted = not self._flash_inverted
        self.update()
