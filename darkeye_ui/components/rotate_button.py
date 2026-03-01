# darkeye_ui/components/rotate_button.py - 基于 IconPushButton 的点击旋转动画按钮
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from PySide6.QtCore import Property, QPointF, QPropertyAnimation, Qt, QRectF
from PySide6.QtGui import QIcon, QPainter
from PySide6.QtWidgets import QStyle, QStyleOptionButton

from .icon_push_button import IconPushButton

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class RotateButton(IconPushButton):
    """基于 IconPushButton：点击后图标旋转 180° 的动画按钮。"""

    def __init__(
        self,
        icon_name: str = "settings",
        icon_path: Optional[Union[str, Path]] = None,
        icon_size: int = 24,
        out_size: int = 32,
        hoverable: bool = True,
        theme_manager: Optional["ThemeManager"] = None,
        parent=None,
    ):
        super().__init__(
            icon_name=icon_name,
            icon_path=icon_path,
            icon_size=icon_size,
            out_size=out_size,
            hoverable=hoverable,
            theme_manager=theme_manager,
            parent=parent,
        )
        self._angle = 0.0
        self._anim = QPropertyAnimation(self, b"angle", self)

    @Property(float)
    def angle(self) -> float:
        return self._angle

    @angle.setter
    def angle(self, value: float) -> None:
        self._angle = value
        self.update()

    def paintEvent(self, event):
        # 只绘制按钮背景（不绘制默认图标），再由本类绘制旋转后的图标
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        opt.icon = QIcon()
        painter = QPainter(self)
        self.style().drawControl(QStyle.CE_PushButton, opt, painter, self)

        pixmap = self.icon().pixmap(self.iconSize())
        if pixmap.isNull():
            painter.end()
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        center = QPointF(self.width() / 2, self.height() / 2)
        painter.translate(center)
        painter.rotate(self._angle)
        w, h = pixmap.width(), pixmap.height()
        target = QRectF(-w / 2, -h / 2, w, h)
        painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._anim.stop()
            self._anim.setDuration(400)
            self._anim.setStartValue(self._angle)
            self._anim.setEndValue(self._angle + 180.0)
            self._anim.start()
        super().mousePressEvent(event)
