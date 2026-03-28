# darkeye_ui/components/color_picker.py - 设计系统颜色选择器，点击弹出色轮
import logging

from PySide6.QtCore import Qt, Signal, QPoint, QEvent, QRectF
from PySide6.QtGui import QColor, QPainter, QBrush, QRegion
from PySide6.QtWidgets import QLabel, QGraphicsDropShadowEffect

try:
    from cpp_bindings.color_wheel.PyColorWheel import ColorWheelSimple
except ImportError:
    ColorWheelSimple = None


class ColorPicker(QLabel):
    """可复用颜色选择器，通过 objectName=DesignColorPicker 由 QSS 驱动样式。点击显示色轮弹窗。
    支持设置是否显示文字、及形状（矩形/圆形）。圆形时不显示文字。"""

    ShapeRectangle = "rectangle"
    ShapeCircle = "circle"

    colorChanged = Signal(str)
    colorConfirmed = Signal(str)

    def __init__(self, color: QColor = None, parent=None, *, show_text: bool = True, shape: str = ShapeRectangle):
        super().__init__(parent)
        if color is None:
            color = QColor("#cccccc")
        self._color = color
        self._show_text = show_text
        self._shape = shape
        self.setObjectName("DesignColorPicker")
        self.setAlignment(Qt.AlignCenter)
        self._apply_shape_and_size()
        self._update_color(self._color)
        self.mousePressEvent = self._handle_click
        self._color_wheel = None
        #self._set_shadow()

    def _set_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.setGraphicsEffect(shadow)

    def get_color(self) -> str:
        return self._color.name()

    def set_color(self, color: str):
        self._update_color(QColor(color))

    def set_show_text(self, show: bool):
        """设置是否显示十六进制颜色文字。圆形时始终不显示。"""
        self._show_text = show
        self._update_display()

    def set_shape(self, shape: str):
        """设置形状：ColorPicker.ShapeRectangle 或 ColorPicker.ShapeCircle。圆形时不显示文字。"""
        self._shape = shape
        self._apply_shape_and_size()
        self._update_display()

    def _apply_shape_and_size(self):
        if self._shape == self.ShapeCircle:
            size = 32
            self.setFixedSize(size, size)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        else:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            self.setMask(QRegion())
            self.setMaximumHeight(32)
            self.setMinimumSize(0, 0)
            self.setMaximumSize(32, 32)

    def _update_display(self):
        """根据 show_text 和 shape 更新文字与样式。"""
        if self._shape == self.ShapeCircle:
            self.setText("")
        else:
            self.setText(self._color.name() if self._show_text else "")
        self._apply_style()

    def _apply_style(self):
        if self._shape == self.ShapeCircle:
            self.setStyleSheet("")  # 圆形由 paintEvent 绘制，不使用 QSS 背景
        else:
            text_color = "#000000" if self._color.lightness() > 128 else "#FFFFFF"
            self.setStyleSheet(
                f"background-color: {self._color.name()};"
                f"border-radius: 12px;"
                f"color: {text_color};"
                f"font-size: 24px;"
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def paintEvent(self, event):
        if self._shape == self.ShapeCircle:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            # 使用浮点坐标 + 0.5 像素内缩，使边缘对齐像素中心，减少锯齿
            rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self._color))
            painter.drawEllipse(rect)
            painter.end()
            return
        super().paintEvent(event)

    def _update_color(self, new_color: QColor):
        self._color = new_color
        self._update_display()
        self.update()  # 确保立即重绘（尤其是圆形模式由 paintEvent 绘制）
        self.colorChanged.emit(new_color.name())

    def _handle_click(self, event):
        if self._color_wheel and self._color_wheel.isVisible():
            global_pos = self.mapToGlobal(event.pos())
            if not self._color_wheel.geometry().contains(global_pos):
                self._color_wheel.hide()
                self._color_wheel.removeEventFilter(self)
                return
        self._show_color_wheel(event)

    def _show_color_wheel(self, event):
        if ColorWheelSimple is None:
            return
        if self._color_wheel is None:
            self._color_wheel = ColorWheelSimple()
            self._color_wheel.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Popup
            )
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(20)
            shadow.setColor(QColor(0, 0, 0, 180))
            shadow.setOffset(0, 8)
            self._color_wheel.setGraphicsEffect(shadow)

        self._color_wheel.adjustSize()
        self._color_wheel.show()
        self._color_wheel.hide()

        global_pos = self.mapToGlobal(QPoint(0, 0))
        wheel_width = self._color_wheel.width()
        wheel_height = self._color_wheel.height()
        label_width = self.width()
        x = global_pos.x() + (label_width - wheel_width) // 2

        screen_rect = self.screen().availableGeometry()
        space_above = global_pos.y() - screen_rect.top()
        gap = 10
        if space_above >= wheel_height + gap:
            y = global_pos.y() - wheel_height - gap
        else:
            y = global_pos.y() + self.height() + gap
        self._color_wheel.move(x, y)

        self._color_wheel.show()
        self._color_wheel.activateWindow()
        self._color_wheel.setFocus()
        # 先断开再连接，避免重复连接；确保拖动时实时更新
        try:
            self._color_wheel.colorChanged.disconnect()
        except RuntimeError as e:
            logging.debug(
                "ColorPicker: colorChanged 断开失败（可能未连接）: %s",
                e,
                exc_info=True,
            )
        self._color_wheel.colorChanged.connect(
            lambda: self._update_color(QColor(self._color_wheel.getHexColor()))
        )
        self._color_wheel.installEventFilter(self)
        if hasattr(self._color_wheel, "setInitialColor"):
            self._color_wheel.setInitialColor(self._color.name())

    def eventFilter(self, obj, event):
        if obj == self._color_wheel and self._color_wheel is not None:
            if event.type() == QEvent.Type.MouseButtonPress:
                global_pos = event.globalPosition().toPoint()
                if self._color_wheel.rect().contains(
                    self._color_wheel.mapFromGlobal(global_pos)
                ):
                    return False
                self._color_wheel.hide()
                self._color_wheel.removeEventFilter(self)
                hex_color = self._color_wheel.getHexColor()
                if hex_color:
                    self._update_color(QColor(hex_color))
                    self.colorConfirmed.emit(hex_color)
                return True
        return super().eventFilter(obj, event)
