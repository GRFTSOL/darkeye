from PySide6.QtWidgets import QWidget, QApplication, QVBoxLayout, QLabel
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QBrush, QPolygonF, QPen,QPainterPath
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
import sys


class AlphaSliderCustom(QWidget):
    """
    完全手写的透明度滑条
    - 轨道：圆角矩形 + 棋盘格 + 颜色渐变
    - 滑块：45°旋转的斜方形（菱形）
    值范围：0 ~ 255
    """
    valueChanged = Signal(int)  # 输出 0~255 的 Alpha 值

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(40)
        self.setMinimumWidth(200)

        self._value = 0          # 当前 Alpha 值 (0~255)
        self._current_color = QColor(255, 100, 180)  # 当前主颜色（不带 alpha）

        self._dragging = False     # 是否正在拖拽

    def setValue(self, value: int):
        """外部设置值"""
        value = max(0, min(255, value))
        if value != self._value:
            self._value = value
            self.update()
            self.valueChanged.emit(value)

    def setColor(self, color: QColor):
        """设置当前主颜色（不带 alpha）"""
        self._current_color = QColor(color)
        self.update()

    def value(self) -> int:
        return self._value

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        margin = 16
        margin2=4 #用于二次缩进，避免滑块看起来突到外面去
        track_height = 32
        track_y = (h - track_height) // 2
        r=12 #圆角半径

        
        # 1. 绘制棋盘格背景（透明指示）
        painter.save()
        path = QPainterPath()
        path.addRoundedRect(QRectF(margin, track_y, w - 2*margin, track_height), r, r)
        painter.setClipPath(path)
        checker_size = 8
        for x in range(0, w, checker_size * 2):
            for y in range(track_y, track_y + track_height, checker_size * 2):
                painter.fillRect(x, y, checker_size, checker_size, QColor(180, 180, 180))
                painter.fillRect(x + checker_size, y + checker_size, checker_size, checker_size, QColor(180, 180, 180))
                painter.fillRect(x + checker_size, y, checker_size, checker_size, QColor(240, 240, 240))
                painter.fillRect(x, y + checker_size, checker_size, checker_size, QColor(240, 240, 240))
        painter.restore()

        
        # 2. 绘制当前颜色的半透明渐变层（左不透明 → 右透明）
        painter.save()
        gradient = QLinearGradient(0, 0, w, 0)
        left_color = QColor(self._current_color)
        left_color.setAlpha(255)
        right_color = QColor(self._current_color)
        right_color.setAlpha(0)

        gradient.setColorAt(0, left_color)
        gradient.setColorAt(1, right_color)

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(QRectF(margin, track_y, w - 2*margin, track_height), r, r)
        painter.restore()

        # 3. 计算滑块位置（进度条风格）
        progress = self._value / 255.0
        handle_center_x = margin+margin2 + progress * (w - 2*(margin+margin2))
        handle_size = 32  # 菱形边长
                # 菱形四个顶点（以中心为原点）
        half = handle_size / 2
        points = [
            QPointF(0, -half),   # 上
            QPointF(half, 0),    # 右
            QPointF(0, half),    # 下
            QPointF(-half, 0)    # 左
        ]

        # 先画深色阴影（底部）
        '''
        painter.save()
        painter.translate(handle_center_x + 2, track_y + track_height/2 + 2)

        pen_shadow = QPen(QColor(0, 0, 0, 180), 3)
        pen_shadow.setJoinStyle(Qt.MiterJoin)
        painter.setPen(pen_shadow)
        painter.setBrush(Qt.NoBrush)
        painter.drawPolygon(QPolygonF(points))
        painter.restore()
        '''

        # 4. 绘制斜方形滑块（45°旋转的正方形）
        painter.save()
        painter.translate(handle_center_x, track_y + track_height/2)
        #painter.rotate(45)  # 旋转45度变成菱形



        # 绘制填充（白色 + 轻微阴影）
        pen=QPen(QColor(255, 255, 255), 4)
        pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        #painter.setBrush(QColor(255, 255, 255,120))
        painter.drawPolygon(QPolygonF(points))

        '''
        # 加高光（左上方向）
        highlight_gradient = QLinearGradient(-half, -half, half, half)
        highlight_gradient.setColorAt(0, QColor(255, 255, 255, 220))
        highlight_gradient.setColorAt(0.5, QColor(255, 255, 255, 80))
        highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(highlight_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(QPolygonF(points))
        '''

        painter.restore()

    def draw_checker(self,painter:QPainter):
        '''绘制透明背景'''
        

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._update_value_from_pos(event.position().x())
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._update_value_from_pos(event.position().x())
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            event.accept()

    def _update_value_from_pos(self, x_pos):
        """根据鼠标 x 坐标计算新值"""
        margin = 8
        max_width = self.width() - 2 * margin
        progress = max(0, min(1.0, (x_pos - margin) / max_width))
        new_value = round(progress * 255)
        if new_value != self._value:
            self._value = new_value
            self.update()
            self.valueChanged.emit(new_value)


# 测试窗口
class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("自定义斜方形透明度滑块")
        self.resize(500, 180)

        layout = QVBoxLayout(self)

        self.slider = AlphaSliderCustom()
        self.slider.valueChanged.connect(self.on_value_changed)
        layout.addWidget(self.slider)

        self.label = QLabel("Alpha: 255 / 255 (1.00)")
        layout.addWidget(self.label)

        # 模拟从颜色选择器来的颜色
        self.slider.setColor(QColor(255, 80, 180))

    def on_value_changed(self, value):
        self.label.setText(f"Alpha: {value} / 255 ({value/255:.2f})")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())