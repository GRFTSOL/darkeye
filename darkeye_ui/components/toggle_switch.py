# ui/components/toggle_switch.py - 开关组件，由设计令牌驱动颜色，支持主题切换
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, QSize, Signal, Property, QPropertyAnimation
from PySide6.QtGui import QPainter, QColor, QBrush
from PySide6.QtWidgets import QWidget

from ..design.tokens import ThemeTokens, LIGHT_TOKENS

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class ToggleSwitch(QWidget):
    """开关：轨道与拇指颜色由设计令牌驱动，支持主题切换时刷新。"""

    toggled = Signal(bool)

    def __init__(
        self,
        parent=None,
        width: int = 48,
        height: int = 24,
        theme_manager: Optional["ThemeManager"] = None,
    ):
        super().__init__(parent)
        self.setObjectName("DesignToggleSwitch")
        self.setFixedSize(width, height)
        self._checked = False
        # 未传入时尝试从应用上下文获取全局 ThemeManager，使主题切换时颜色能更新
        if theme_manager is None:
            try:
                from app_context import get_theme_manager
                theme_manager = get_theme_manager()
            except Exception:
                pass
        self._theme_manager = theme_manager

        # 动画用属性
        self._offset = 2.0
        self._bg_color = QColor("#777")
        self._circle_color = QColor("#DDD")

        # 从令牌初始化颜色（后续由 _apply_tokens 覆盖）
        self._inactive_color = QColor("#777")
        self._active_color = QColor("#00b16a")
        self._apply_tokens()

        # 动画
        self._anim_offset = QPropertyAnimation(self, b"offset", self)
        self._anim_offset.setDuration(200)
        self._anim_bg = QPropertyAnimation(self, b"bgColor", self)
        self._anim_bg.setDuration(200)

        if theme_manager is not None:
            theme_manager.themeChanged.connect(self._on_theme_changed)

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _apply_tokens(self) -> None:
        t = self._tokens()
        self._inactive_color = QColor(t.color_border)
        self._active_color = QColor(t.color_success)
        self._circle_color = QColor(t.color_bg)
        # 同步当前显示背景色与状态一致，避免主题切换后色差
        self._bg_color = self._active_color if self._checked else self._inactive_color

    def _on_theme_changed(self) -> None:
        self._apply_tokens()
        # 若正在动画，将偏移设到当前状态对应的终点，避免主题切换后位置错位
        end = self._end_offset_for_checked(self._checked)
        self._anim_offset.stop()
        self._anim_bg.stop()
        self._offset = end
        self._bg_color = self._active_color if self._checked else self._inactive_color
        self.update()

    def _end_offset_for_checked(self, checked: bool) -> float:
        if checked:
            return float(self.width() - self.height() + 2)
        return 2.0

    # ----------------- 属性：圆点偏移 -----------------
    def get_offset(self) -> float:
        return self._offset

    def set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, get_offset, set_offset)

    # ----------------- 属性：背景颜色 -----------------
    def get_bgColor(self) -> QColor:
        return self._bg_color

    def set_bgColor(self, value: QColor) -> None:
        self._bg_color = value
        self.update()

    bgColor = Property(QColor, get_bgColor, set_bgColor)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        radius = rect.height() / 2.0

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._bg_color))
        painter.drawRoundedRect(rect, radius, radius)

        # 拇指：直径 = height - 4，上下各留 2px
        circle_diameter = rect.height() - 4
        painter.setBrush(QBrush(self._circle_color))
        painter.drawEllipse(
            int(self._offset), 2, circle_diameter, circle_diameter
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        if self._checked == checked:
            return
        self._checked = checked
        self.toggled.emit(self._checked)

        end = self._end_offset_for_checked(self._checked)
        self._anim_offset.stop()
        self._anim_offset.setStartValue(self._offset)
        self._anim_offset.setEndValue(end)
        self._anim_offset.start()

        self._anim_bg.stop()
        self._anim_bg.setStartValue(self._bg_color)
        self._anim_bg.setEndValue(
            self._active_color if self._checked else self._inactive_color
        )
        self._anim_bg.start()

    checked = Property(bool, isChecked, setChecked)

    def sizeHint(self) -> QSize:
        return QSize(48, 24)
