# 单个爱心控件，用来表示喜欢或不喜欢；图标使用内联 SVG，无外部文件依赖

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, QPropertyAnimation, Property, Signal, QByteArray
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

# 内联 SVG：空心爱心（未选中）
SVG_LOVE_OFF = """<svg version="1.1" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
 <path d="m9.268 2.994a8.476 8.476 0 0 0-5.256 2.451 8.476 8.476 0 0 0 0 11.99l11.99 11.99 11.99-11.99a8.476 8.476 0 0 0 0-11.99 8.476 8.476 0 0 0-11.99 0.001953 8.476 8.476 0 0 0-6.734-2.453zm0.8496 1.99c0.3742 0.004111 0.7479 0.03777 1.115 0.1172 1.95 0.2866 3.333 1.769 4.77 2.975 0.579-0.4938 1.158-0.9882 1.736-1.482 2.325-2.155 6.262-2.135 8.566 0.04297 2.612 2.16 2.886 6.457 0.6406 8.979-3.607 3.699-7.302 7.315-10.94 10.98l-9.947-9.947c-1.617-1.419-2.715-3.536-2.48-5.723 0.1633-2.909 2.554-5.447 5.422-5.879 0.3716-0.04244 0.7469-0.06856 1.121-0.06445z" fill="#ccc"/>
</svg>"""

# 内联 SVG：实心爱心（选中）
SVG_LOVE_ON = """<svg version="1.1" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
 <path d="m4.012 5.446a8.476 8.476 0 0 0 2.6e-6 11.99l11.99 11.99 11.99-11.99a8.476 8.476 0 0 0 0-11.99 8.476 8.476 0 0 0-11.99 0.0021 8.476 8.476 0 0 0-11.99-0.0021z" fill="#ff2a2a" stroke-width="0"/>
</svg>"""


def _svg_to_qimage(svg_data: str, width: int, height: int) -> QImage:
    """将 SVG 字符串渲染为 QImage。"""
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(0)
    renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return image


class HeartLabel(QLabel):
    """单个爱心控件，用来表示喜欢或者不喜欢。"""

    clicked = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

        self._img_off = _svg_to_qimage(SVG_LOVE_OFF, 32, 32)
        self._img_on = _svg_to_qimage(SVG_LOVE_ON, 32, 32)

        self._checked = False
        self.setAlignment(Qt.AlignCenter)

        self._scale = 1.0
        self._anim = QPropertyAnimation(self, b"scale", self)

    def get_scale(self):
        return self._scale

    def set_scale(self, value: float):
        self._scale = value
        self.update()

    scale = Property(float, get_scale, set_scale)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        img = self._img_on if self._checked else self._img_off
        scaled_img = img.scaled(
            int(img.width() * self._scale),
            int(img.height() * self._scale),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        draw_x = (self.width() - scaled_img.width()) / 2
        draw_y = (self.height() - scaled_img.height()) / 2
        painter.drawImage(int(draw_x), int(draw_y), scaled_img)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self._playAnimation()
            self.clicked.emit(self._checked)

    def _playAnimation(self):
        self._anim.stop()
        self._anim.setDuration(350)
        self._anim.setKeyValueAt(0, 1.0)
        self._anim.setKeyValueAt(0.3, 0.7)
        self._anim.setKeyValueAt(0.6, 1.1)
        self._anim.setKeyValueAt(1, 1.0)
        self._anim.start()

    def is_checked(self):
        return self._checked

    def get_state(self):
        return self._checked

    def set_state(self, state):
        self._checked = state
        self.update()
