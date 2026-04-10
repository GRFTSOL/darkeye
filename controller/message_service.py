# 这个依赖注入使用，但是现在还是有问题
import sys
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from darkeye_ui.design.tokens import ThemeTokens, LIGHT_TOKENS

if TYPE_CHECKING:
    from darkeye_ui.design.theme_manager import ThemeManager


def _messagebox_qss_from_tokens(t: ThemeTokens) -> str:
    """根据当前主题令牌生成 QMessageBox 的 QSS，使弹窗随主题变色。"""
    return f"""
QMessageBox {{
    background-color: {t.color_bg};
    color: {t.color_text};
    font-family: {t.font_family_base};
    font-size: {t.font_size_base};
}}
QMessageBox QLabel {{
    color: {t.color_text};
}}
QMessageBox QPushButton {{
    background-color: {t.color_primary};
    color: {t.color_text_inverse};
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
    min-width: 70px;
}}
QMessageBox QPushButton:hover {{
    background-color: {t.color_primary_hover};
}}
QMessageBox QPushButton:disabled {{
    background-color: {t.color_text_disabled};
    color: {t.color_text};
}}
"""


def _win32_try_set_foreground(widget) -> None:
    """尽量把窗口提到前台（受系统焦点策略限制，可能失败）。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = int(widget.winId())
        if hwnd:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def _bring_parent_to_attention(parent) -> None:
    """恢复最小化、提升 Z 序、激活并闪烁任务栏，便于用户注意到后台弹窗。"""
    app = QApplication.instance()
    if app is None or parent is None:
        return
    if parent.isMinimized():
        parent.showNormal()
    parent.raise_()
    parent.activateWindow()
    app.setActiveWindow(parent)
    QApplication.alert(parent, 2000)
    _win32_try_set_foreground(parent)


class IMessageService(ABC):
    @abstractmethod
    def show_info(self, title, message, *, top_level: bool = False): ...

    @abstractmethod
    def show_warning(
        self,
        title,
        message,
        *,
        attention_grabbing: bool = False,
        top_level: bool = False,
    ): ...

    @abstractmethod
    def show_critical(self, title, message): ...

    @abstractmethod
    def ask_yes_no(self, title, message) -> bool: ...


class MessageBoxService(IMessageService):
    """消息框服务，由设计令牌驱动样式，随主题切换变色。"""

    def __init__(self, parent=None, theme_manager: Optional["ThemeManager"] = None):
        self.parent = parent
        if theme_manager is None:
            from controller.app_context import get_theme_manager

            theme_manager = get_theme_manager()
        self._theme_manager = theme_manager

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _apply_tokens_to_box(self, box: QMessageBox) -> None:
        box.setStyleSheet(_messagebox_qss_from_tokens(self._tokens()))

    def show_info(self, title, message, *, top_level: bool = False):
        """top_level：先唤起本地顶层主窗口，再以主窗口为父显示提示（适合浏览器插件回传后）。"""
        if top_level:
            win = self.parent.window() if self.parent else None
            if win is not None:
                _bring_parent_to_attention(win)
                box_parent = win
                QApplication.processEvents()
            else:
                box_parent = None
        else:
            box_parent = self.parent
        box = QMessageBox(
            QMessageBox.Information,
            title,
            message,
            QMessageBox.Ok,
            box_parent,
        )
        if top_level:
            box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self._apply_tokens_to_box(box)
        box.exec()

    def show_warning(
        self,
        title,
        message,
        *,
        attention_grabbing: bool = False,
        top_level: bool = False,
    ):
        grab = attention_grabbing or top_level
        if top_level:
            win = self.parent.window() if self.parent else None
            if win is not None:
                _bring_parent_to_attention(win)
                box_parent = win
                QApplication.processEvents()
            else:
                box_parent = None
        elif attention_grabbing:
            _bring_parent_to_attention(self.parent)
            box_parent = self.parent
        else:
            box_parent = self.parent
        box = QMessageBox(
            QMessageBox.Warning,
            title,
            message,
            QMessageBox.Ok,
            box_parent,
        )
        if grab:
            box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self._apply_tokens_to_box(box)
        box.exec()

    def show_critical(self, title, message):
        box = QMessageBox(
            QMessageBox.Critical, title, message, QMessageBox.Ok, self.parent
        )
        self._apply_tokens_to_box(box)
        box.exec()

    def ask_yes_no(self, title, message) -> bool:
        box = QMessageBox(
            QMessageBox.Question,
            title,
            message,
            QMessageBox.Yes | QMessageBox.No,
            self.parent,
        )
        self._apply_tokens_to_box(box)
        return box.exec() == QMessageBox.Yes
