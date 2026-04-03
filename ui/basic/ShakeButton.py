from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import (
    QSize,
    Qt,
    QPropertyAnimation,
    Property,
    QRectF,
    QPointF,
    QEasingCurve,
)
from PySide6.QtGui import QIcon, QPainter, QPixmap, QIcon, QImage
import logging
from config import ICONS_PATH
from utils.image import create_colored_icon, create_colored_icon_vector, svg_to_qimage


class ShakeButton(QPushButton):
    """点击后图片左右移动的按钮"""

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
            self.setStyleSheet(
                """
            QPushButton {
                border: none;
                background: transparent;
                border-radius: 6px;   /* 圆角半径 */
            }
            QPushButton:hover {
                background-color: lightgray; /* 悬停时灰色背景 */
            }
            """
            )
        else:
            self.setStyleSheet(
                """
            QPushButton {
                border: none;
                background: transparent;
                border-radius: 6px;   /* 圆角半径 */
            }
            """
            )

        # 1. 初始化偏移属性
        self._offset = 0
        self.anim = QPropertyAnimation(self, b"offset", self)

    # --- 定义 offset 属性 ---
    @Property(float)
    def offset(self):
        return self._offset

    @offset.setter
    def offset(self, value):
        self._offset = value
        self.update()  # 必须调用以触发重绘

    def paintEvent(self, event):
        # 1. 画按钮背景
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 2. 计算中心点并应用偏移
        # 我们只在 X 轴上叠加 self._offset
        center_x = self.width() / 2 + self._offset
        center_y = self.height() / 2

        # 3. 绘制图标
        w, h = self._pixmap.width(), self._pixmap.height()
        target_rect = QRectF(center_x - w / 2, center_y - h / 2, w, h)
        painter.drawPixmap(target_rect, self._pixmap, QRectF(self._pixmap.rect()))

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 4. 设置左右晃动的关键帧
            self.anim.stop()
            self.anim.setDuration(400)
            self.anim.setStartValue(0)
            self.anim.setKeyValueAt(0.25, -7)  # 向左移 10px
            self.anim.setKeyValueAt(0.5, 5)  # 向右移 10px
            self.anim.setKeyValueAt(0.75, -3)  # 逐渐减弱
            self.anim.setEndValue(0)  # 回到原点

            # 使用弹性曲线让动作更自然
            self.anim.setEasingCurve(QEasingCurve.OutQuad)
            self.anim.start()

        super().mousePressEvent(event)
