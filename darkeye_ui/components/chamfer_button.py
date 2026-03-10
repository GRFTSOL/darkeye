# darkeye_ui/components/chamfer_button.py - 斜角按钮，令牌驱动，可配置斜角比例
"""斜角按钮：0=正方形，1=菱形，支持图标与选中/hover 状态，由设计令牌驱动。"""
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QAbstractButton, QWidget

from ..design import get_builtin_icon, svg_to_icon
from ..design.theme_context import resolve_theme_manager
from ..design.tokens import ThemeTokens, LIGHT_TOKENS

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


def _render_icon_pixmap(
    icon_name: Optional[str] = None,
    icon_path: Optional[Union[str, Path]] = None,
    size: int = 24,
    color: str = "#333333",
) -> QPixmap:
    """将图标渲染为 QPixmap，用于自定义绘制。"""
    if icon_path is not None:
        icon = svg_to_icon(icon_path, size=size, color=color)
    elif icon_name:
        icon = get_builtin_icon(icon_name, size=size, color=color)
    else:
        return QPixmap()
    return icon.pixmap(QSize(size, size))


class ChamferButton(QAbstractButton):
    """
    斜角按钮（可演变为八边形/菱形）
    - 斜角比例 chamfer_ratio 0~1：0=正方形，1=菱形，由 out_size 决定范围
    - 令牌驱动：填充色、图标色随主题变化
    - 可选图标（icon_name 内置 / icon_path 外部 SVG）
    - 支持 hover、选中状态
    - tooltip 显示文本
    """

    def __init__(
        self,
        text: str = "",
        icon_name: Optional[str] = None,
        icon_path: Optional[Union[str, Path]] = None,
        icon_size: Optional[int] = None,
        out_size: int = 40,
        chamfer_ratio: float = 0.22,
        hoverable: bool = True,
        theme_manager: Optional["ThemeManager"] = None,
        menu_id: Optional[str] = None,
        use_native_tooltip: bool = True,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("DesignChamferButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._text = text
        self._icon_name = icon_name
        self._icon_path = icon_path
        self._out_size = out_size
        self._chamfer_ratio = max(0.0, min(1.0, chamfer_ratio))
        self._hoverable = hoverable
        self._menu_id = menu_id

        if icon_size is None:
            icon_size = int(out_size * 0.55)
        self._icon_size = icon_size

        theme_manager = resolve_theme_manager(theme_manager, "ChamferButton")
        self._theme_manager = theme_manager

        if use_native_tooltip:
            self.setToolTip(text)
        self.setFixedSize(out_size, out_size)
        self.setMouseTracking(True)

        self._is_selected = False
        self._is_hovered = False

        if theme_manager is not None:
            theme_manager.themeChanged.connect(self._refresh_and_repaint)

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _refresh_and_repaint(self) -> None:
        self.update()

    def set_chamfer_ratio(self, ratio: float) -> None:
        """设置斜角比例 0~1，0=正方形，1=菱形。"""
        r = max(0.0, min(1.0, ratio))
        if self._chamfer_ratio != r:
            self._chamfer_ratio = r
            self.update()

    def chamfer_ratio(self) -> float:
        return self._chamfer_ratio

    def set_selected(self, selected: bool) -> None:
        if self._is_selected != selected:
            self._is_selected = selected
            self.update()

    def is_selected(self) -> bool:
        return self._is_selected

    def set_icon_name(self, icon_name: Optional[str]) -> None:
        self._icon_name = icon_name
        self._icon_path = None
        self.update()

    def set_icon_path(self, icon_path: Optional[Union[str, Path]]) -> None:
        self._icon_path = icon_path
        self.update()

    def enterEvent(self, event) -> None:  # type: ignore[override]
        if self._hoverable:
            self._is_hovered = True
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        t = self._tokens()
        rect = self.rect()
        w, h = rect.width(), rect.height()
        x, y = rect.x(), rect.y()

        # 斜角：0=正方形，1=菱形；由 out_size 决定范围，dx/dy 最大为 w/2、h/2
        dx = w * self._chamfer_ratio * 0.5
        dy = h * self._chamfer_ratio * 0.5

        path = QPainterPath()
        path.moveTo(x + dx, y)
        path.lineTo(x + w - dx, y)
        path.lineTo(x + w, y + dy)
        path.lineTo(x + w, y + h - dy)
        path.lineTo(x + w - dx, y + h)
        path.lineTo(x + dx, y + h)
        path.lineTo(x, y + h - dy)
        path.lineTo(x, y + dy)
        path.closeSubpath()

        if self._is_selected:
            fill_color = QColor(t.color_primary)
        elif self._is_hovered and self._hoverable:
            fill_color = QColor(t.color_bg_input)
        else:
            fill_color = QColor(t.color_bg)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(fill_color))
        painter.drawPath(path)

        if self._icon_name or self._icon_path is not None:
            icon_color = t.color_text_inverse if self._is_selected else t.color_icon
            pix = _render_icon_pixmap(
                icon_name=self._icon_name,
                icon_path=self._icon_path,
                size=self._icon_size,
                color=icon_color,
            )
            if not pix.isNull():
                ix = x + (w - self._icon_size) / 2
                iy = y + (h - self._icon_size) / 2
                painter.drawPixmap(int(ix), int(iy), pix)
        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(self._out_size, self._out_size)
