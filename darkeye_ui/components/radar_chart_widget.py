import math
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QBrush, QColor, QPen, QPolygonF, QPainter
from PySide6.QtWidgets import QFrame, QGraphicsLineItem, QGraphicsPolygonItem, QGraphicsScene, QGraphicsTextItem, QGraphicsView

from ..design.theme_context import resolve_theme_manager
from ..design.tokens import LIGHT_TOKENS, ThemeTokens

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class RadarChartWidget(QGraphicsView):
    """自绘雷达图，网格、轴线、数据区颜色由设计令牌驱动，支持主题切换。
    传进来的值一定是[0,1]归一化后的数据。
    categories: 标签列表
    values: 归一化后的列表
    show_values: 原始列表，可能会有""
    """
    def __init__(
        self,
        categories=None,
        values=None,
        show_values=None,
        num_layers=5,
        theme_manager: Optional["ThemeManager"] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.categories = categories
        self.values = values
        self.show_values = show_values if show_values is not None else values

        theme_manager = resolve_theme_manager(theme_manager, "RadarChartWidget")
        self._theme_manager = theme_manager
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._on_theme_changed)

        self.setFrameStyle(QFrame.NoFrame)
        self.num_layers = num_layers
        self.max_value = 1

        self.myscene = QGraphicsScene(self)
        self.setScene(self.myscene)
        self.setRenderHints(QPainter.Antialiasing)
        self.setStyleSheet("background: transparent; border: none;")
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.myscene.setBackgroundBrush(QBrush(Qt.transparent))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.center_x, self.center_y = 100, 100
        self.max_radius = 80
        self.angle_offset = math.pi / 2

        self._apply_token_colors()

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _apply_token_colors(self) -> None:
        t = self._tokens()
        self.pen_grid = QPen(QColor(t.color_border), 1)
        self.pen_axis = QPen(QColor(t.color_border), 1)
        self.pen_data = QPen(QColor(t.color_primary), 2)
        c = QColor(t.color_primary)
        c.setAlpha(100)
        self.brush_data = QBrush(c)
        self._color_label = t.color_text
        self._color_data_label = t.color_primary

    def _on_theme_changed(self) -> None:
        self._apply_token_colors()
        if self.categories and self.values is not None:
            self.update_chart()


    def draw_grid(self):
        num_categories = len(self.categories)
        for i in range(1, self.num_layers + 1):
            radius = self.max_radius * i / self.num_layers
            points = []
            for j in range(num_categories):
                angle = -2 * math.pi * j / num_categories + self.angle_offset
                x = self.center_x + radius * math.cos(angle)
                y = self.center_y - radius * math.sin(angle)
                points.append(QPointF(x, y))
            points.append(points[0])
            polygon = QPolygonF(points)
            poly_item = QGraphicsPolygonItem(polygon)
            poly_item.setPen(self.pen_grid)
            poly_item.setBrush(Qt.NoBrush)
            self.myscene.addItem(poly_item)

    def draw_axes(self):
        num_categories = len(self.categories)
        for i in range(num_categories):
            angle = -2 * math.pi * i / num_categories + self.angle_offset
            x = self.center_x + self.max_radius * math.cos(angle)
            y = self.center_y - self.max_radius * math.sin(angle)
            line = QGraphicsLineItem(self.center_x, self.center_y, x, y)
            line.setPen(self.pen_axis)
            self.myscene.addItem(line)

    def draw_labels(self):
        num_categories = len(self.categories)
        for i, label in enumerate(self.categories):
            angle = -2 * math.pi * i / num_categories + self.angle_offset
            x = self.center_x + (self.max_radius + 20) * math.cos(angle)
            y = self.center_y - (self.max_radius + 20) * math.sin(angle)
            text_item = QGraphicsTextItem(label)
            text_item.setDefaultTextColor(QColor(getattr(self, "_color_label", "#333333")))
            text_item.setPos(x - text_item.boundingRect().width() / 2,
                             y - text_item.boundingRect().height() / 2)
            self.myscene.addItem(text_item)

    def draw_data(self):
        num_categories = len(self.categories)
        points = []
        for i, value in enumerate(self.values):
            angle = -2 * math.pi * i / num_categories + self.angle_offset
            radius = self.max_radius * value / self.max_value
            x = self.center_x + radius * math.cos(angle)
            y = self.center_y - radius * math.sin(angle)
            points.append(QPointF(x, y))

            label_text = QGraphicsTextItem(str(self.show_values[i]))
            label_text.setPos(x + 10 * math.cos(angle) - label_text.boundingRect().width() / 2,
                              y - 10 * math.sin(angle) - label_text.boundingRect().height() / 2)
            self.myscene.addItem(label_text)
            label_text.setDefaultTextColor(QColor(getattr(self, "_color_data_label", "#00aaff")))

        points.append(points[0])  # 闭合
        polygon = QPolygonF(points)
        poly_item = QGraphicsPolygonItem(polygon)
        poly_item.setPen(self.pen_data)
        poly_item.setBrush(self.brush_data)
        self.myscene.addItem(poly_item)

    def update_chart(self, categories=None, values=None, show_values=None):
        """更新数据并重绘"""
        if categories is not None:
            self.categories = categories
        if values is not None:
            self.values = values
        if show_values is not None:
            self.show_values = show_values
        else:
            self.show_values = self.values

        # 清空场景
        self.myscene.clear()

        # 重新绘制
        self.draw_grid()
        self.draw_axes()
        self.draw_labels()
        self.draw_data()
