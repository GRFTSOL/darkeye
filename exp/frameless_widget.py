"""
FramelessWidget - Windows 无边框窗口实现

特性：
- 无边框 + DWM 阴影效果
- 自定义标题栏（Logo/标题/最小化/最大化/关闭按钮）
- Win+方向键 跨屏移动/最大化/最小化
- 多 DPI 显示器自适应
- 拖拽标题栏移动，双击最大化/还原
- 四边四角可拖拽调整大小
- 最大化时不跨屏溢出
- Win7/Win10/Win11 兼容
- 不依赖 DirectX/显卡驱动
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
from ctypes import POINTER, Structure, byref, c_int, sizeof, windll
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, QPoint, QSize, QEvent, Signal, QTimer
from PySide6.QtGui import QIcon, QMouseEvent, QPainter, QColor, QPixmap, QCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QApplication,
    QSizePolicy,
    QGraphicsDropShadowEffect,
)

if TYPE_CHECKING:
    from PySide6.QtCore import QByteArray

# ============================================================================
# Win32 API 常量
# ============================================================================

# Window Messages
WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084
WM_NCACTIVATE = 0x0086
WM_GETMINMAXINFO = 0x0024
WM_DPICHANGED = 0x02E0
WM_SIZE = 0x0005
WM_SYSCOMMAND = 0x0112

# WM_NCHITTEST 返回值
HTCLIENT = 1
HTCAPTION = 2
HTSYSMENU = 3
HTMINBUTTON = 8
HTMAXBUTTON = 9
HTCLOSE = 20
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17

# WM_SIZE wParam 值
SIZE_RESTORED = 0
SIZE_MINIMIZED = 1
SIZE_MAXIMIZED = 2

# Window Styles
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000

# Extended Window Styles
GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000

# Monitor 相关
MONITOR_DEFAULTTONEAREST = 2

# SWP Flags
SWP_FRAMECHANGED = 0x0020
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004

# System Command
SC_MAXIMIZE = 0xF030
SC_RESTORE = 0xF120


# ============================================================================
# Win32 结构体定义
# ============================================================================


class MARGINS(Structure):
    _fields_ = [
        ("cxLeftWidth", c_int),
        ("cxRightWidth", c_int),
        ("cyTopHeight", c_int),
        ("cyBottomHeight", c_int),
    ]


class RECT(Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class NCCALCSIZE_PARAMS(Structure):
    _fields_ = [
        ("rgrc", RECT * 3),
    ]


class MINMAXINFO(Structure):
    _fields_ = [
        ("ptReserved", wintypes.POINT),
        ("ptMaxSize", wintypes.POINT),
        ("ptMaxPosition", wintypes.POINT),
        ("ptMinTrackSize", wintypes.POINT),
        ("ptMaxTrackSize", wintypes.POINT),
    ]


class MONITORINFO(Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]


# ============================================================================
# Win32 API 函数加载
# ============================================================================

user32 = windll.user32
dwmapi = windll.dwmapi
gdi32 = windll.gdi32

# DWM 函数
try:
    DwmExtendFrameIntoClientArea = dwmapi.DwmExtendFrameIntoClientArea
    DwmExtendFrameIntoClientArea.argtypes = [wintypes.HWND, POINTER(MARGINS)]
    DwmExtendFrameIntoClientArea.restype = wintypes.LONG

    DwmIsCompositionEnabled = dwmapi.DwmIsCompositionEnabled
    DwmIsCompositionEnabled.argtypes = [POINTER(wintypes.BOOL)]
    DwmIsCompositionEnabled.restype = wintypes.LONG

    DWM_AVAILABLE = True
except (OSError, AttributeError):
    DWM_AVAILABLE = False

# User32 函数
GetWindowLongW = user32.GetWindowLongW
GetWindowLongW.argtypes = [wintypes.HWND, c_int]
GetWindowLongW.restype = wintypes.LONG

SetWindowLongW = user32.SetWindowLongW
SetWindowLongW.argtypes = [wintypes.HWND, c_int, wintypes.LONG]
SetWindowLongW.restype = wintypes.LONG

SetWindowPos = user32.SetWindowPos
SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    c_int,
    c_int,
    c_int,
    c_int,
    wintypes.UINT,
]
SetWindowPos.restype = wintypes.BOOL

MonitorFromWindow = user32.MonitorFromWindow
MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
MonitorFromWindow.restype = wintypes.HMONITOR

GetMonitorInfoW = user32.GetMonitorInfoW
GetMonitorInfoW.argtypes = [wintypes.HMONITOR, POINTER(MONITORINFO)]
GetMonitorInfoW.restype = wintypes.BOOL

GetCursorPos = user32.GetCursorPos
GetCursorPos.argtypes = [POINTER(wintypes.POINT)]
GetCursorPos.restype = wintypes.BOOL

ReleaseCapture = user32.ReleaseCapture
SendMessageW = user32.SendMessageW

# DPI 相关函数 (Win10+)
try:
    GetDpiForWindow = user32.GetDpiForWindow
    GetDpiForWindow.argtypes = [wintypes.HWND]
    GetDpiForWindow.restype = wintypes.UINT
    DPI_AWARE = True
except (OSError, AttributeError):
    DPI_AWARE = False


def is_dwm_composition_enabled() -> bool:
    """检查 DWM 合成是否启用"""
    if not DWM_AVAILABLE:
        return False
    enabled = wintypes.BOOL()
    result = DwmIsCompositionEnabled(byref(enabled))
    return result == 0 and enabled.value


def get_window_dpi(hwnd: int) -> int:
    """获取窗口 DPI"""
    if DPI_AWARE:
        return GetDpiForWindow(hwnd)
    return 96  # 默认 DPI


# ============================================================================
# TitleBarButton - 标题栏按钮
# ============================================================================


class TitleBarButton(QPushButton):
    """自定义标题栏按钮，支持 hover/pressed 效果"""

    def __init__(
        self,
        icon_path: str = "",
        button_type: str = "normal",  # "normal", "minimize", "maximize", "close"
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._button_type = button_type
        self._icon_path = icon_path
        self._is_hovered = False
        self._is_pressed = False
        self._is_maximized = False  # 用于最大化按钮状态切换

        self.setFixedSize(46, 32)
        self.setFlat(True)
        self.setCursor(Qt.ArrowCursor)
        self.setAttribute(Qt.WA_Hover, True)

        if icon_path:
            self._update_icon()

        self._update_style()

    def set_maximized_state(self, maximized: bool):
        """设置最大化状态（用于切换图标）"""
        self._is_maximized = maximized
        self._update_icon()

    def _update_icon(self):
        """更新按钮图标"""
        if not self._icon_path:
            return

        # 如果是最大化按钮，根据状态切换图标
        icon_path = self._icon_path
        if self._button_type == "maximize" and self._is_maximized:
            # 最大化状态显示还原图标
            icon_path = icon_path.replace("square.svg", "copy.svg")

        self.setIcon(QIcon(icon_path))
        self.setIconSize(QSize(16, 16))

    def _update_style(self):
        """根据状态更新样式"""
        if self._button_type == "close":
            if self._is_pressed:
                bg_color = "#C42B1C"
                icon_color = "#FFFFFF"
            elif self._is_hovered:
                bg_color = "#E81123"
                icon_color = "#FFFFFF"
            else:
                bg_color = "transparent"
                icon_color = "#FFFFFF"
        else:
            if self._is_pressed:
                bg_color = "rgba(255, 255, 255, 0.1)"
            elif self._is_hovered:
                bg_color = "rgba(255, 255, 255, 0.06)"
            else:
                bg_color = "transparent"
            icon_color = "#FFFFFF"

        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {bg_color};
                border: none;
                border-radius: 0px;
            }}
        """
        )

    def enterEvent(self, event):
        self._is_hovered = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        self._is_pressed = False
        self._update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_pressed = True
            self._update_style()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._is_pressed = False
        self._update_style()
        super().mouseReleaseEvent(event)


# ============================================================================
# TitleBar - 自定义标题栏
# ============================================================================


class TitleBar(QWidget):
    """自定义标题栏"""

    minimizeClicked = Signal()
    maximizeClicked = Signal()
    closeClicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None, icons_path: str = ""):
        super().__init__(parent)
        self._icons_path = icons_path
        self._parent_window = parent
        self._drag_start_pos: Optional[QPoint] = None
        self._is_dragging = False

        self.setFixedHeight(32)
        self.setMouseTracking(True)

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.set_contentsMargins(8, 0, 0, 0)
        layout.setSpacing(0)

        # Logo
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(20, 20)
        layout.addWidget(self._icon_label)

        layout.addSpacing(8)

        # 标题
        self._title_label = QLabel()
        self._title_label.setStyleSheet(
            """
            QLabel {
                color: #FFFFFF;
                font-size: 12px;
            }
        """
        )
        layout.addWidget(self._title_label)

        # 弹性空间
        layout.addStretch()

        # 窗口控制按钮
        icon_path = self._icons_path

        self._min_btn = TitleBarButton(
            icon_path=f"{icon_path}/minus.svg" if icon_path else "",
            button_type="minimize",
        )
        self._max_btn = TitleBarButton(
            icon_path=f"{icon_path}/square.svg" if icon_path else "",
            button_type="maximize",
        )
        self._close_btn = TitleBarButton(
            icon_path=f"{icon_path}/close.svg" if icon_path else "", button_type="close"
        )

        self._min_btn.clicked.connect(self.minimizeClicked.emit)
        self._max_btn.clicked.connect(self.maximizeClicked.emit)
        self._close_btn.clicked.connect(self.closeClicked.emit)

        layout.addWidget(self._min_btn)
        layout.addWidget(self._max_btn)
        layout.addWidget(self._close_btn)

    def setWindowIcon(self, icon: QIcon):
        """设置窗口图标"""
        pixmap = icon.pixmap(16, 16)
        self._icon_label.setPixmap(pixmap)

    def setWindowTitle(self, title: str):
        """设置窗口标题"""
        self._title_label.setText(title)

    def set_maximized_state(self, maximized: bool):
        """设置最大化状态"""
        self._max_btn.set_maximized_state(maximized)

    def is_in_title_bar_area(self, pos: QPoint) -> bool:
        """检查位置是否在标题栏区域（排除按钮）"""
        # 检查是否在按钮上
        for btn in [self._min_btn, self._max_btn, self._close_btn]:
            btn_rect = btn.geometry()
            if btn_rect.contains(pos):
                return False
        return True

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下"""
        if event.button() == Qt.LeftButton:
            if self.is_in_title_bar_area(event.position().toPoint()):
                self._drag_start_pos = event.globalPosition().toPoint()
                self._is_dragging = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动 - 拖拽窗口"""
        if self._is_dragging and self._drag_start_pos and self._parent_window:
            # 如果窗口是最大化状态，先还原
            if self._parent_window.isMaximized():
                # 计算还原后的位置
                self._parent_window._restore_from_maximized(
                    event.globalPosition().toPoint()
                )
                self._drag_start_pos = event.globalPosition().toPoint()
            else:
                delta = event.globalPosition().toPoint() - self._drag_start_pos
                new_pos = self._parent_window.pos() + delta
                self._parent_window.move(new_pos)
                self._drag_start_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放"""
        self._is_dragging = False
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """双击标题栏"""
        if event.button() == Qt.LeftButton:
            if self.is_in_title_bar_area(event.position().toPoint()):
                self.maximizeClicked.emit()
        super().mouseDoubleClickEvent(event)


# ============================================================================
# FramelessWidget - 无边框窗口主类
# ============================================================================


class FramelessWidget(QWidget):
    """
    Windows 无边框窗口

    使用方法:
        class MyWindow(FramelessWidget):
            def __init__(self):
                super().__init__()
                self.setWindowTitle("My App")
                self.setWindowIcon(QIcon("icon.svg"))

                content = QWidget()
                # ... 设置 content 内容 ...
                self.set_content(content)
    """

    # 边框拖拽区域大小
    BORDER_WIDTH = 5

    def __init__(self, parent: Optional[QWidget] = None, icons_path: str = ""):
        super().__init__(parent)

        self._icons_path = icons_path
        self._hwnd: Optional[int] = None
        self._is_maximized = False
        self._normal_geometry = None  # 保存正常状态的几何信息
        self._dpi_scale = 1.0
        self._dwm_enabled = is_dwm_composition_enabled()

        # 设置窗口属性
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setMouseTracking(True)

        # 初始化 UI
        self._init_ui()

        # 延迟设置 Win32 样式（等窗口句柄创建后）
        QTimer.singleShot(0, self._setup_win32_style)

    def _init_ui(self):
        """初始化 UI 布局"""
        self._main_layout = QVBoxLayout(self)
        self._main_layout.set_contentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # 标题栏
        self._title_bar = TitleBar(self, self._icons_path)
        self._title_bar.minimizeClicked.connect(self.showMinimized)
        self._title_bar.maximizeClicked.connect(self._toggle_maximize)
        self._title_bar.closeClicked.connect(self.close)
        self._main_layout.addWidget(self._title_bar)

        # 内容区域容器
        self._content_container = QWidget()
        self._content_layout = QVBoxLayout(self._content_container)
        self._content_layout.set_contentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._main_layout.addWidget(self._content_container, 1)

        # 设置默认背景色
        self.setStyleSheet(
            """
            FramelessWidget {
                background-color: #1E1E1E;
            }
        """
        )

    def set_content(self, widget: QWidget):
        """设置窗口内容"""
        # 清除旧内容
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # 添加新内容
        self._content_layout.addWidget(widget)

    def setWindowTitle(self, title: str):
        """设置窗口标题"""
        super().setWindowTitle(title)
        self._title_bar.setWindowTitle(title)

    def setWindowIcon(self, icon: QIcon):
        """设置窗口图标"""
        super().setWindowIcon(icon)
        self._title_bar.setWindowIcon(icon)

    def set_icons_path(self, path: str):
        """设置图标路径"""
        self._icons_path = path

    def _setup_win32_style(self):
        """设置 Win32 窗口样式"""
        self._hwnd = int(self.winId())

        if not self._hwnd:
            return

        # 获取当前窗口样式
        style = GetWindowLongW(self._hwnd, GWL_STYLE)

        # 设置窗口样式：保留边框功能但去掉视觉效果
        # WS_THICKFRAME: 允许调整大小
        # WS_CAPTION: 允许标题栏（用于系统快捷键）
        # WS_MINIMIZEBOX/WS_MAXIMIZEBOX: 允许最小化/最大化
        new_style = (
            style
            | WS_THICKFRAME
            | WS_CAPTION
            | WS_MINIMIZEBOX
            | WS_MAXIMIZEBOX
            | WS_SYSMENU
        )
        SetWindowLongW(self._hwnd, GWL_STYLE, new_style)

        # 启用 DWM 阴影
        if self._dwm_enabled:
            self._enable_dwm_shadow()

        # 通知窗口样式已更改
        SetWindowPos(
            self._hwnd,
            0,
            0,
            0,
            0,
            0,
            SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER,
        )

        # 获取初始 DPI
        if DPI_AWARE:
            dpi = get_window_dpi(self._hwnd)
            self._dpi_scale = dpi / 96.0

    def _enable_dwm_shadow(self):
        """启用 DWM 阴影效果"""
        if not DWM_AVAILABLE or not self._hwnd:
            return

        # 扩展边框到客户区以启用阴影
        margins = MARGINS(1, 1, 1, 1)
        DwmExtendFrameIntoClientArea(self._hwnd, byref(margins))

    def _toggle_maximize(self):
        """切换最大化/还原状态"""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _restore_from_maximized(self, cursor_pos: QPoint):
        """从最大化状态还原（用于拖拽还原）"""
        if not self.isMaximized():
            return

        # 保存当前宽度比例
        title_bar_width = self._title_bar.width()
        cursor_x_ratio = (
            (cursor_pos.x() - self.x()) / title_bar_width
            if title_bar_width > 0
            else 0.5
        )

        # 还原窗口
        self.showNormal()

        # 计算新位置（让光标保持在标题栏的相对位置）
        new_width = self.width()
        new_x = cursor_pos.x() - int(new_width * cursor_x_ratio)
        new_y = cursor_pos.y() - self._title_bar.height() // 2

        self.move(new_x, new_y)

    def showMaximized(self):
        """最大化窗口"""
        if not self._is_maximized:
            self._normal_geometry = self.geometry()
        self._is_maximized = True
        self._title_bar.set_maximized_state(True)
        super().showMaximized()

    def showNormal(self):
        """还原窗口"""
        self._is_maximized = False
        self._title_bar.set_maximized_state(False)
        super().showNormal()
        if self._normal_geometry:
            self.setGeometry(self._normal_geometry)

    def isMaximized(self) -> bool:
        """检查是否最大化"""
        return self._is_maximized or super().isMaximized()

    def _get_border_hit_test(self, x: int, y: int) -> int:
        """获取边框拖拽区域"""
        w = self.width()
        h = self.height()
        bw = self.BORDER_WIDTH

        # 四角
        if x < bw and y < bw:
            return HTTOPLEFT
        if x >= w - bw and y < bw:
            return HTTOPRIGHT
        if x < bw and y >= h - bw:
            return HTBOTTOMLEFT
        if x >= w - bw and y >= h - bw:
            return HTBOTTOMRIGHT

        # 四边
        if x < bw:
            return HTLEFT
        if x >= w - bw:
            return HTRIGHT
        if y < bw:
            return HTTOP
        if y >= h - bw:
            return HTBOTTOM

        return HTCLIENT

    def _handle_nchittest(self, x: int, y: int) -> int:
        """处理 WM_NCHITTEST 消息"""
        # 转换为窗口坐标
        local_pos = self.mapFromGlobal(QPoint(x, y))
        lx, ly = local_pos.x(), local_pos.y()

        # 最大化时不允许调整大小
        if not self.isMaximized():
            hit = self._get_border_hit_test(lx, ly)
            if hit != HTCLIENT:
                return hit

        # 检查是否在标题栏区域
        title_bar_rect = self._title_bar.geometry()
        if title_bar_rect.contains(local_pos):
            # 转换为标题栏本地坐标
            title_bar_pos = self._title_bar.mapFromParent(local_pos)
            if self._title_bar.is_in_title_bar_area(title_bar_pos):
                return HTCAPTION

        return HTCLIENT

    def _handle_getminmaxinfo(self, l_param: int) -> None:
        """处理 WM_GETMINMAXINFO 消息 - 多屏最大化支持"""
        if not self._hwnd:
            return

        info = ctypes.cast(l_param, POINTER(MINMAXINFO)).contents

        # 获取当前屏幕信息
        monitor = MonitorFromWindow(self._hwnd, MONITOR_DEFAULTTONEAREST)
        monitor_info = MONITORINFO()
        monitor_info.cbSize = sizeof(MONITORINFO)

        if GetMonitorInfoW(monitor, byref(monitor_info)):
            work_rect = monitor_info.rcWork
            monitor_rect = monitor_info.rcMonitor

            # 设置最大化位置和大小（使用工作区域，排除任务栏）
            info.ptMaxPosition.x = work_rect.left - monitor_rect.left
            info.ptMaxPosition.y = work_rect.top - monitor_rect.top
            info.ptMaxSize.x = work_rect.right - work_rect.left
            info.ptMaxSize.y = work_rect.bottom - work_rect.top

    def _handle_dpichanged(self, w_param: int, l_param: int) -> None:
        """处理 WM_DPICHANGED 消息 - DPI 自适应"""
        new_dpi = w_param >> 16  # HIWORD
        self._dpi_scale = new_dpi / 96.0

        # 获取系统建议的新窗口矩形
        rect = ctypes.cast(l_param, POINTER(RECT)).contents

        # 调整窗口大小和位置
        SetWindowPos(
            self._hwnd,
            0,
            rect.left,
            rect.top,
            rect.right - rect.left,
            rect.bottom - rect.top,
            SWP_NOZORDER,
        )

    def nativeEvent(self, event_type: QByteArray, message: int) -> tuple:
        """处理 Windows 原生事件"""
        try:
            msg = ctypes.wintypes.MSG.from_address(int(message))
        except Exception:
            return False, 0

        if msg.message == WM_NCCALCSIZE:
            # 移除非客户区（标题栏和边框）
            if msg.wParam:
                # 返回 0 表示整个窗口都是客户区
                return True, 0

        elif msg.message == WM_NCHITTEST:
            # 处理鼠标命中测试
            x = msg.lParam & 0xFFFF
            y = (msg.lParam >> 16) & 0xFFFF
            # 处理负坐标（多屏幕情况）
            if x > 32767:
                x -= 65536
            if y > 32767:
                y -= 65536

            result = self._handle_nchittest(x, y)
            return True, result

        elif msg.message == WM_GETMINMAXINFO:
            # 处理最大化尺寸
            self._handle_getminmaxinfo(msg.lParam)
            return False, 0

        elif msg.message == WM_DPICHANGED:
            # 处理 DPI 变化
            self._handle_dpichanged(msg.wParam, msg.lParam)
            return False, 0

        elif msg.message == WM_NCACTIVATE:
            # 防止非客户区激活导致的闪烁
            return True, 1

        elif msg.message == WM_SIZE:
            # 更新最大化状态
            w_param = msg.wParam
            if w_param == SIZE_MAXIMIZED:
                self._is_maximized = True
                self._title_bar.set_maximized_state(True)
            elif w_param == SIZE_RESTORED:
                self._is_maximized = False
                self._title_bar.set_maximized_state(False)

        return super().nativeEvent(event_type, message)

    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)

        # 首次显示时居中
        if not event.spontaneous():
            self._center_on_screen()

    def _center_on_screen(self):
        """窗口居中显示"""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            x = (screen_geo.width() - self.width()) // 2 + screen_geo.x()
            y = (screen_geo.height() - self.height()) // 2 + screen_geo.y()
            self.move(x, y)

    def changeEvent(self, event):
        """状态改变事件"""
        if event.type() == QEvent.WindowStateChange:
            # 同步最大化状态
            is_max = self.windowState() & Qt.WindowMaximized
            self._is_maximized = bool(is_max)
            self._title_bar.set_maximized_state(self._is_maximized)
        super().changeEvent(event)


# ============================================================================
# Win7 兼容性回退方案
# ============================================================================


class FramelessWidgetFallback(QWidget):
    """
    Win7 无 DWM 时的回退实现
    使用纯 Qt 实现，手动绘制阴影
    """

    SHADOW_WIDTH = 10
    BORDER_WIDTH = 5

    def __init__(self, parent: Optional[QWidget] = None, icons_path: str = ""):
        super().__init__(parent)

        self._icons_path = icons_path
        self._is_maximized = False
        self._normal_geometry = None
        self._drag_start_pos = None
        self._resize_edge = None

        # 设置无边框窗口
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowMinMaxButtonsHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self._init_ui()

    def _init_ui(self):
        """初始化 UI"""
        # 主容器（带阴影边距）
        self._main_container = QWidget(self)
        self._main_container.setObjectName("mainContainer")
        self._main_container.setStyleSheet(
            """
            #mainContainer {
                background-color: #1E1E1E;
                border-radius: 0px;
            }
        """
        )

        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(self.SHADOW_WIDTH * 2)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 0)
        self._main_container.setGraphicsEffect(shadow)

        # 主布局
        outer_layout = QVBoxLayout(self)
        outer_layout.set_contentsMargins(
            self.SHADOW_WIDTH, self.SHADOW_WIDTH, self.SHADOW_WIDTH, self.SHADOW_WIDTH
        )
        outer_layout.addWidget(self._main_container)

        # 内部布局
        self._main_layout = QVBoxLayout(self._main_container)
        self._main_layout.set_contentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # 标题栏
        self._title_bar = TitleBar(self, self._icons_path)
        self._title_bar.minimizeClicked.connect(self.showMinimized)
        self._title_bar.maximizeClicked.connect(self._toggle_maximize)
        self._title_bar.closeClicked.connect(self.close)
        self._main_layout.addWidget(self._title_bar)

        # 内容区域
        self._content_container = QWidget()
        self._content_layout = QVBoxLayout(self._content_container)
        self._content_layout.set_contentsMargins(0, 0, 0, 0)
        self._main_layout.addWidget(self._content_container, 1)

    def set_content(self, widget: QWidget):
        """设置内容"""
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._content_layout.addWidget(widget)

    def setWindowTitle(self, title: str):
        super().setWindowTitle(title)
        self._title_bar.setWindowTitle(title)

    def setWindowIcon(self, icon: QIcon):
        super().setWindowIcon(icon)
        self._title_bar.setWindowIcon(icon)

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def showMaximized(self):
        if not self._is_maximized:
            self._normal_geometry = self.geometry()
        self._is_maximized = True
        self._title_bar.set_maximized_state(True)

        # 移除阴影边距
        self.layout().set_contentsMargins(0, 0, 0, 0)
        super().showMaximized()

    def showNormal(self):
        self._is_maximized = False
        self._title_bar.set_maximized_state(False)

        # 恢复阴影边距
        self.layout().set_contentsMargins(
            self.SHADOW_WIDTH, self.SHADOW_WIDTH, self.SHADOW_WIDTH, self.SHADOW_WIDTH
        )
        super().showNormal()
        if self._normal_geometry:
            self.setGeometry(self._normal_geometry)

    def isMaximized(self) -> bool:
        return self._is_maximized or super().isMaximized()

    def showEvent(self, event):
        super().showEvent(event)
        if not event.spontaneous():
            self._center_on_screen()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2 + geo.x()
            y = (geo.height() - self.height()) // 2 + geo.y()
            self.move(x, y)

    def _get_resize_edge(self, pos: QPoint) -> Optional[str]:
        """获取调整大小的边缘"""
        if self._is_maximized:
            return None

        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        sw = self.SHADOW_WIDTH
        bw = self.BORDER_WIDTH

        # 考虑阴影边距
        in_left = x < sw + bw
        in_right = x > w - sw - bw
        in_top = y < sw + bw
        in_bottom = y > h - sw - bw

        if in_left and in_top:
            return "topleft"
        if in_right and in_top:
            return "topright"
        if in_left and in_bottom:
            return "bottomleft"
        if in_right and in_bottom:
            return "bottomright"
        if in_left:
            return "left"
        if in_right:
            return "right"
        if in_top:
            return "top"
        if in_bottom:
            return "bottom"

        return None

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            edge = self._get_resize_edge(event.position().toPoint())
            if edge:
                self._resize_edge = edge
                self._drag_start_pos = event.globalPosition().toPoint()
                self._normal_geometry = self.geometry()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        # 更新光标
        edge = self._get_resize_edge(event.position().toPoint())
        cursors = {
            "left": Qt.SizeHorCursor,
            "right": Qt.SizeHorCursor,
            "top": Qt.SizeVerCursor,
            "bottom": Qt.SizeVerCursor,
            "topleft": Qt.SizeFDiagCursor,
            "bottomright": Qt.SizeFDiagCursor,
            "topright": Qt.SizeBDiagCursor,
            "bottomleft": Qt.SizeBDiagCursor,
        }
        self.setCursor(cursors.get(edge, Qt.ArrowCursor))

        # 调整大小
        if self._resize_edge and self._drag_start_pos and self._normal_geometry:
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            geo = self._normal_geometry
            new_geo = geo

            if "left" in self._resize_edge:
                new_geo.setLeft(geo.left() + delta.x())
            if "right" in self._resize_edge:
                new_geo.setRight(geo.right() + delta.x())
            if "top" in self._resize_edge:
                new_geo.setTop(geo.top() + delta.y())
            if "bottom" in self._resize_edge:
                new_geo.setBottom(geo.bottom() + delta.y())

            # 最小尺寸限制
            min_w, min_h = 200, 100
            if new_geo.width() >= min_w and new_geo.height() >= min_h:
                self.setGeometry(new_geo)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._resize_edge = None
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)


# ============================================================================
# 工厂函数：自动选择合适的实现
# ============================================================================


def create_frameless_widget(
    parent: Optional[QWidget] = None, icons_path: str = ""
) -> QWidget:
    """
    创建无边框窗口，自动选择合适的实现

    Args:
        parent: 父窗口
        icons_path: 图标路径

    Returns:
        FramelessWidget 或 FramelessWidgetFallback 实例
    """
    if is_dwm_composition_enabled():
        return FramelessWidget(parent, icons_path)
    else:
        return FramelessWidgetFallback(parent, icons_path)


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == "__main__":
    import sys
    from pathlib import Path

    app = QApplication(sys.argv)

    # 获取图标路径
    icons_path = Path(__file__).parent.parent / "resources" / "icons"

    # 创建无边框窗口
    window = FramelessWidget(icons_path=str(icons_path))
    window.setWindowTitle("无边框窗口测试")
    window.setWindowIcon(QIcon(str(icons_path / "logo.svg")))
    window.resize(800, 600)

    # 创建测试内容
    content = QWidget()
    content_layout = QVBoxLayout(content)
    content_layout.set_contentsMargins(20, 20, 20, 20)
    content_layout.setSpacing(15)

    # 标题
    title = QLabel("无边框窗口测试")
    title.setStyleSheet(
        """
        QLabel {
            color: #FFFFFF;
            font-size: 24px;
            font-weight: bold;
        }
    """
    )
    content_layout.addWidget(title)

    # 功能说明
    info_text = """
    <p style="color: #AAAAAA; font-size: 14px; line-height: 1.8;">
    <b>测试功能：</b><br>
    • 拖拽标题栏移动窗口<br>
    • 双击标题栏最大化/还原<br>
    • 最大化时拖拽标题栏还原<br>
    • Win+左/右 跨屏移动<br>
    • Win+上 最大化，Win+下 还原/最小化<br>
    • 四边四角拖拽调整大小<br>
    • 标题栏按钮 hover/pressed 效果<br>
    • 关闭按钮红色高亮
    </p>
    """
    info_label = QLabel(info_text)
    info_label.setWordWrap(True)
    content_layout.addWidget(info_label)

    # 测试按钮
    btn_layout = QHBoxLayout()

    test_btn = QPushButton("测试按钮")
    test_btn.setStyleSheet(
        """
        QPushButton {
            background-color: #0078D4;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            font-size: 14px;
        }
        QPushButton:hover {
            background-color: #1084D8;
        }
        QPushButton:pressed {
            background-color: #006CBD;
        }
    """
    )
    test_btn.clicked.connect(lambda: print("按钮点击"))
    btn_layout.addWidget(test_btn)

    maximize_btn = QPushButton("切换最大化")
    maximize_btn.setStyleSheet(test_btn.styleSheet())
    maximize_btn.clicked.connect(
        lambda: window.showNormal() if window.isMaximized() else window.showMaximized()
    )
    btn_layout.addWidget(maximize_btn)

    btn_layout.addStretch()
    content_layout.addLayout(btn_layout)

    # 状态信息
    status_label = QLabel(
        "DWM 状态: "
        + ("已启用" if is_dwm_composition_enabled() else "未启用（使用回退方案）")
    )
    status_label.setStyleSheet("color: #888888; font-size: 12px;")
    content_layout.addWidget(status_label)

    content_layout.addStretch()

    # 设置内容
    window.set_content(content)

    # 显示窗口
    window.show()

    sys.exit(app.exec())
