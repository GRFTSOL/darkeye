# coding:utf-8
import sys

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QPixmap, QIcon, QPainter, QPen
from PySide6.QtWidgets import QApplication, QLabel, QWidget, QStackedWidget

from qframelesswindow import FramelessWindow
from qframelesswindow.utils import startSystemMove, toggleMaxState


class CustomTabBar(QWidget):
    """自定义 TabBar：左侧 tabs，中间空白可拖拽，右侧窗口控制按钮"""

    tabChanged = Signal(int)  # 切换 tab 时发射，参数为 tab 索引

    TAB_HEIGHT = 36
    TAB_WIDTH = 80
    BUTTON_SIZE = 46
    BUTTON_HEIGHT = 32

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.TAB_HEIGHT)
        self.setMouseTracking(True)
        self._tabs = ["Tab 1", "Tab 2", "Tab 3"]
        self._current_index = 0
        self._hover_tab = -1
        self._hover_btn = -1  # 0=min, 1=max, 2=close
        self._pressed_btn = -1
        self._pressed_tab = -1  # 按下时的 tab，用于 release 时判断是否在同一 tab 上释放

    def _tabs_rect(self) -> QRect:
        """tabs 区域"""
        return QRect(0, 0, len(self._tabs) * self.TAB_WIDTH, self.TAB_HEIGHT)

    def _blank_rect(self) -> QRect:
        """空白可拖拽区域"""
        left = self._tabs_rect().right()
        right = self.width() - 3 * self.BUTTON_SIZE
        return QRect(left, 0, right - left, self.TAB_HEIGHT)

    def _button_rect(self, index: int) -> QRect:
        """窗口按钮区域 (0=min, 1=max, 2=close)"""
        x = self.width() - (3 - index) * self.BUTTON_SIZE
        return QRect(
            x,
            (self.TAB_HEIGHT - self.BUTTON_HEIGHT) // 2,
            self.BUTTON_SIZE,
            self.BUTTON_HEIGHT,
        )

    def _hit_test(self, pos) -> tuple[str, int]:
        """返回 ('tab', index) 或 ('blank', -1) 或 ('btn', 0=min/1=max/2=close)"""
        if self._tabs_rect().contains(pos):
            idx = pos.x() // self.TAB_WIDTH
            return ("tab", min(idx, len(self._tabs) - 1))
        for i in range(3):
            if self._button_rect(i).contains(pos):
                return ("btn", i)
        if self._blank_rect().contains(pos):
            return ("blank", -1)
        return ("none", -1)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # 背景
        painter.fillRect(self.rect(), QColor(240, 240, 240))

        # 底部分割线
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawLine(0, self.TAB_HEIGHT - 1, self.width(), self.TAB_HEIGHT - 1)

        # 绘制 tabs
        for i, text in enumerate(self._tabs):
            r = QRect(i * self.TAB_WIDTH, 0, self.TAB_WIDTH, self.TAB_HEIGHT)
            is_current = i == self._current_index
            is_hover = i == self._hover_tab
            if is_current:
                painter.fillRect(r, QColor(255, 255, 255))
                painter.setPen(QColor(0, 120, 215))
                painter.drawLine(r.left(), r.bottom() - 2, r.right(), r.bottom() - 2)
            elif is_hover:
                painter.fillRect(r, QColor(230, 230, 230))
            painter.setPen(QColor(50, 50, 50))
            painter.drawText(r, Qt.AlignCenter, text)

        # 绘制窗口控制按钮
        win = self.window()
        is_max = win.isMaximized() if win else False
        for i in range(3):
            r = self._button_rect(i)
            is_hover = i == self._hover_btn
            is_pressed = i == self._pressed_btn
            if is_hover or is_pressed:
                bg = QColor(0, 100, 182) if i == 2 and is_hover else QColor(0, 0, 0, 26)
                if i == 2 and is_hover:
                    bg = QColor(232, 17, 35)
                if is_pressed:
                    bg = QColor(54, 57, 65)
                painter.fillRect(r, bg)
            painter.setPen(QColor(50, 50, 50) if i != 2 else QColor(100, 100, 100))
            self._draw_button_icon(painter, r, i, is_max)

    def _draw_button_icon(self, painter: QPainter, r: QRect, btn: int, is_max: bool):
        """绘制 min/max/close 图标"""
        cx, cy = r.center().x(), r.center().y()
        if btn == 0:  # min
            painter.drawLine(cx - 6, cy, cx + 6, cy)
        elif btn == 1:  # max
            if is_max:
                painter.drawRect(cx - 5, cy - 4, 6, 6)
                painter.drawRect(cx - 2, cy - 7, 6, 6)
            else:
                painter.drawRect(cx - 6, cy - 5, 10, 10)
        else:  # close
            painter.drawLine(cx - 4, cy - 4, cx + 4, cy + 4)
            painter.drawLine(cx + 4, cy - 4, cx - 4, cy + 4)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        kind, idx = self._hit_test(event.position().toPoint())
        if kind == "blank":
            startSystemMove(self.window(), event.globalPosition().toPoint())
        elif kind == "btn":
            self._pressed_btn = idx
            self.update()
        elif kind == "tab":
            self._pressed_tab = idx
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            super().mouseReleaseEvent(event)
            return
        kind, idx = self._hit_test(event.position().toPoint())
        if kind == "tab" and idx == self._pressed_tab and idx != self._current_index:
            self._current_index = idx
            self.tabChanged.emit(idx)
        elif kind == "btn" and idx == self._pressed_btn:
            win = self.window()
            if idx == 0:
                win.showMinimized()
            elif idx == 1:
                toggleMaxState(win)
            else:
                win.close()
        self._pressed_btn = -1
        self._pressed_tab = -1
        self.update()
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        kind, idx = self._hit_test(event.position().toPoint())
        self._hover_tab = idx if kind == "tab" else -1
        self._hover_btn = idx if kind == "btn" else -1
        self.update()
        super().mouseMoveEvent(event)


class Window(FramelessWindow):

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        tab_bar = CustomTabBar(self)
        self.setTitleBar(tab_bar)

        self._stack = QStackedWidget(self)
        contents = ["Tab 1 内容", "Tab 2 内容", "Tab 3 内容"]
        pix = QPixmap("screenshot/shoko.png")
        for i in range(3):
            page = QLabel(self)
            page.setAlignment(Qt.AlignCenter)
            page.setStyleSheet("font-size: 24px; color: #333;")
            if i == 0 and not pix.isNull():
                page.setPixmap(pix)
                page.setScaledContents(True)
            else:
                page.setText(contents[i])
            self._stack.addWidget(page)

        tab_bar.tabChanged.connect(self._stack.setCurrentIndex)

        self.setWindowIcon(QIcon("screenshot/logo.png"))
        self.setWindowTitle("PySide6-Frameless-Window")
        self.setStyleSheet("background:white")

        self.titleBar.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._stack.setGeometry(0, 36, self.width(), self.height() - 36)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    demo = Window()
    demo.show()
    app.exec()
