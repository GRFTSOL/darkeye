from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import QSize, Qt, QPropertyAnimation, Property, QRectF, QPointF
from PySide6.QtGui import QIcon, QPainter, QPixmap, QIcon, QImage
import logging
from config import ICONS_PATH
from utils.image import create_colored_icon, create_colored_icon_vector, svg_to_qimage


class RotateButton(QPushButton):
    """点击后图片旋转360的按钮"""

    def __init__(
        self,
        iconpath: str = "arrow-up.png",
        iconsize=24,
        outsize=24,
        hoverable=True,
        color="#000000",
    ):
        super().__init__()

        self._pixmap = QPixmap.fromImage(
            svg_to_qimage(str(ICONS_PATH / iconpath), iconsize, iconsize)
        )
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setFixedSize(outsize, outsize)

        if hoverable:
            self.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                border-radius: 6px;   /* 圆角半径 */
            }
            QPushButton:hover {
                background-color: lightgray; /* 悬停时灰色背景 */
            }
            """)
        else:
            self.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                border-radius: 6px;   /* 圆角半径 */
            }
            """)

        self._angle = 0
        self.anim = QPropertyAnimation(self, b"angle", self)

    # --- 角度属性，供动画调用 ---
    @Property(float)
    def angle(self):
        return self._angle

    @angle.setter
    def angle(self, value):
        self._angle = value
        self.update()  # 触发重绘

    def paintEvent(self, event):
        # 1. 先调用父类方法绘制按钮的背景和边框（不带图标）
        super().paintEvent(event)

        # 2. 开始手动绘制旋转的图标
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # 计算中心点
        center = QPointF(self.width() / 2, self.height() / 2)

        # 3. 变换坐标系
        painter.translate(center)  # 平移到中心
        painter.rotate(self._angle)  # 旋转

        # 4. 绘制图标 (图标中心对齐坐标原点)
        w, h = self._pixmap.width(), self._pixmap.height()
        target_rect = QRectF(-w / 2, -h / 2, w, h)
        painter.drawPixmap(target_rect, self._pixmap, QRectF(self._pixmap.rect()))

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 点击触发 180 度顺时针旋转
            self.anim.stop()
            self.anim.setDuration(400)
            self.anim.setStartValue(self._angle)
            self.anim.setEndValue(self._angle + 180)
            self.anim.start()
        super().mousePressEvent(event)
