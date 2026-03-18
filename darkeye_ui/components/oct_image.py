# darkeye_ui/components/oct_image.py - 正八边形图片展示组件，设计系统组件库
from pathlib import Path
from typing import Optional, Union

from PySide6.QtCore import Qt, Signal, QPointF, QThreadPool, QRunnable
from PySide6.QtGui import QPixmap, QPolygonF, QRegion, QImage, QColor
from PySide6.QtWidgets import QLabel
import math


def _set_shadow_on_widget(widget: QLabel, blur_radius=10, x_offset=0, y_offset=2, color=None):
    """为控件设置投影，仅依赖 PySide6"""
    from PySide6.QtWidgets import QGraphicsDropShadowEffect
    if color is None:
        color = QColor(0, 0, 0, 80)
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur_radius)
    effect.setXOffset(x_offset)
    effect.setYOffset(y_offset)
    effect.setColor(color)
    widget.setGraphicsEffect(effect)


class ImageLoaderRunnable(QRunnable):
    """QImage 异步加载并缩放，通过信号回 UI 线程显示。"""

    def __init__(self, path: Path, target_size, callback_signal: Signal):
        super().__init__()
        self.path = path
        self.target_size = target_size
        self.callback_signal = callback_signal

    def run(self):
        img = QImage(str(self.path))
        if not img.isNull():
            img = img.scaled(
                self.target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self.callback_signal.emit(img)


class OctImage(QLabel):
    """正八边形图片展示组件，支持异步加载与可选投影。不绑定业务路径，适合放入组件库。"""

    image_ready = Signal(QImage)

    def __init__(
        self,
        image_path: Optional[str] = None,
        base_path: Optional[Union[str, Path]] = None,
        diameter: int = 150,
        shadow: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._d = diameter
        self._base_path = Path(base_path) if base_path is not None else None
        if shadow:
            _set_shadow_on_widget(self)
        self.setFixedSize(self._d, self._d)
        self.setAlignment(Qt.AlignCenter)
        # 背景透明
        self.setStyleSheet("background-color: transparent;")
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        if image_path is None or image_path == "":
            self._path = None
        else:
            p = Path(image_path)
            if p.is_absolute():
                self._path = p
            else:
                self._path = (self._base_path / image_path) if self._base_path else p

        self.image_ready.connect(self._set_pixmap)
        self._show_image_async()

    def _show_image_async(self):
        if not self._path or not self._path.exists():
            self.setText("无图片")
            return
        runnable = ImageLoaderRunnable(self._path, self.size(), self.image_ready)
        QThreadPool.globalInstance().start(runnable)

    def _set_pixmap(self, img: QImage):
        if img.isNull():
            self.setText("无图片")
            return
        d = self._d
        c = d / (2 + math.sqrt(2))
        polygon = QPolygonF()
        for x, y in [
            (c, 0), (d - c, 0), (d, c), (d, d - c),
            (d - c, d), (c, d), (0, d - c), (0, c),
        ]:
            polygon.append(QPointF(x, y))
        self.setPixmap(QPixmap.fromImage(img))
        self.setMask(QRegion(polygon.toPolygon()))

    def update_image(self, image_path: Optional[str]):
        """更新图片并重绘。"""
        if image_path is None or image_path == "":
            self._path = None
            self.setText("无图片")
            self.clearMask()
            return
        p = Path(image_path)
        self._path = (self._base_path / image_path) if self._base_path and not p.is_absolute() else p
        self._show_image_async()
