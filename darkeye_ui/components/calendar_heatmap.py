# darkeye_ui/components/calendar_heatmap.py - 日历热力图，由设计令牌驱动
"""标准日历热力图（仿 GitHub 风格），背景、边框、文字由设计令牌驱动。"""
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QDate, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..design.theme_context import resolve_theme_manager
from ..design.tokens import LIGHT_TOKENS, ThemeTokens

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class CalendarHeatmap(QWidget):
    """日历热力图：背景、边框、文字颜色由设计令牌驱动，随主题切换。"""

    def __init__(
        self,
        year: int = 2025,
        data: Optional[dict] = None,
        parent=None,
        theme_manager: Optional["ThemeManager"] = None,
    ):
        super().__init__(parent)
        self.setFixedSize(750, 155)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.year = year
        self.data = data or {}

        theme_manager = resolve_theme_manager(theme_manager, "CalendarHeatmap")
        self._theme_manager = theme_manager
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._on_theme_changed)

        self.cell_width = 10
        self.cell_height = 10
        self.cell_spacing = 3
        self.margin_top = 40
        self.margin_left = 40
        self._compute_basic()

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _on_theme_changed(self) -> None:
        self.update()

    def _compute_basic(self) -> None:
        self.first_date = QDate(self.year, 1, 1)
        self.last_date = QDate(self.year, 12, 31)
        self.week_days = ["一", "二", "三", "四", "五", "六", "日"]
        self.days_count = self.first_date.daysTo(self.last_date) + 1
        self.day_positions = {}
        self._compute_positions()
        self.columns = max(col for col, row in self.day_positions.values()) + 1

    def sizeHint(self) -> QSize:
        total_width = self.columns * self.cell_width + (self.columns - 1) * self.cell_spacing
        total_height = 7 * self.cell_height + 6 * self.cell_spacing
        return QSize(total_width, total_height)

    def _compute_positions(self) -> None:
        current = self.first_date
        col = 0
        while current <= self.last_date:
            weekday = current.dayOfWeek() - 1
            self.day_positions[current] = (col, weekday)
            if weekday == 6:
                col += 1
            current = current.addDays(1)

    def paintEvent(self, event):
        t = self._tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(t.color_bg))

        margin = 10
        border_radius = 12
        border_rect = self.rect().adjusted(margin, margin, -margin, -margin)
        pen = QPen(QColor(t.color_border), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(border_rect, border_radius, border_radius)

        painter.setPen(QColor(t.color_text))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        for i, wd in enumerate(self.week_days):
            y = self.margin_top + i * (self.cell_height + self.cell_spacing) + self.cell_height * 0.8
            painter.drawText(15, y, wd)

        self._draw_month_labels(painter)

        for date, (col, row) in self.day_positions.items():
            x = self.margin_left + col * (self.cell_width + self.cell_spacing)
            y = self.margin_top + row * (self.cell_height + self.cell_spacing)
            rect = QRectF(x, y, self.cell_width, self.cell_height)
            value = self.data.get(date, 0)
            match value:
                case 1:
                    color = QColor(100, 255, 100)
                case 2:
                    color = QColor(150, 200, 50)
                case 3:
                    color = QColor(255, 200, 0)
                case 4:
                    color = QColor(255, 100, 100)
                case _:
                    color = QColor(230, 230, 230)
            radius = 2
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, radius, radius)
        painter.end()

    def _draw_month_labels(self, painter: QPainter) -> None:
        t = self._tokens()
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(t.color_text))
        current_month = 1
        first_col_of_month = None
        sorted_dates = sorted(self.day_positions.keys())
        for i, date in enumerate(sorted_dates):
            col, row = self.day_positions[date]
            if date.month() != current_month:
                if first_col_of_month is not None:
                    last_col = col - 1
                    self._draw_month_text(painter, current_month, first_col_of_month, last_col)
                current_month = date.month()
                first_col_of_month = col
            if i == len(sorted_dates) - 1:
                self._draw_month_text(painter, current_month, first_col_of_month, col)
            elif first_col_of_month is None:
                first_col_of_month = col

    def _draw_month_text(self, painter: QPainter, month: int, first_col: int, last_col: int) -> None:
        x = self.margin_left + ((first_col + last_col + 1) / 2) * (self.cell_width + self.cell_spacing)
        y = self.margin_top - 10
        month_names = ["一月", "二月", "三月", "四月", "五月", "六月",
                      "七月", "八月", "九月", "十月", "十一月", "十二月"]
        text = month_names[month - 1]
        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(text)
        painter.drawText(x - text_w / 2, y, text)

    def update_data(self, year: int, data: dict) -> None:
        """更新热力图数据，data: QDate -> int (0~4) 表示不同强度。"""
        self.year = year
        self.data = data or {}
        self._compute_basic()
        self.update()
