# darkeye_ui/components/color_picker.py - 设计系统颜色选择器，点击弹出色轮
from PySide6.QtCore import Qt, Signal, QPoint, QEvent
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QGraphicsDropShadowEffect

try:
    from cpp_bindings.color_wheel.PyColorWheel import ColorWheelSimple
except ImportError:
    ColorWheelSimple = None


class ColorPicker(QLabel):
    """可复用颜色选择器，通过 objectName=DesignColorPicker 由 QSS 驱动样式。点击显示色轮弹窗。"""

    colorChanged = Signal(str)

    def __init__(self, color: QColor = None, parent=None):
        super().__init__(parent)
        if color is None:
            color = QColor("white")
        self._color = color
        self.setObjectName("DesignColorPicker")
        self.setAlignment(Qt.AlignCenter)
        self._update_color(self._color)
        self.setMaximumHeight(40)
        self.mousePressEvent = self._handle_click
        self._color_wheel = None
        self._set_shadow()

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

    def _update_color(self, new_color: QColor):
        self._color = new_color
        self.setText(self._color.name())
        text_color = "#000000" if new_color.lightness() > 128 else "#FFFFFF"
        self.setStyleSheet(
            f"background-color: {self._color.name()};"
            f"border-radius: 12px;"
            f"color: {text_color};"
            f"font-size: 24px;"
        )
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
        label_width = self.width()
        x = global_pos.x() + (label_width - wheel_width) // 2
        y = global_pos.y() - self._color_wheel.height() - 10
        self._color_wheel.move(x, y)

        self._color_wheel.show()
        self._color_wheel.activateWindow()
        self._color_wheel.setFocus()
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
                return True
        return super().eventFilter(obj, event)
