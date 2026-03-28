# 这个依赖注入使用，但是现在还是有问题
import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import QMessageBox
from abc import ABC, abstractmethod

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


class IMessageService(ABC):
    @abstractmethod
    def show_info(self, title, message): ...

    @abstractmethod
    def show_warning(self,title,message):...

    @abstractmethod
    def show_critical(self,title,message):...

    @abstractmethod
    def ask_yes_no(self, title, message) -> bool: ...

class MessageBoxService(IMessageService):
    """消息框服务，由设计令牌驱动样式，随主题切换变色。"""

    def __init__(self, parent=None, theme_manager: Optional["ThemeManager"] = None):
        self.parent = parent
        if theme_manager is None:
            try:
                from app_context import get_theme_manager
                theme_manager = get_theme_manager()
            except Exception as e:
                logging.debug(
                    "MessageBoxService: 获取主题管理器失败，将使用默认令牌: %s",
                    e,
                    exc_info=True,
                )
        self._theme_manager = theme_manager

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _apply_tokens_to_box(self, box: QMessageBox) -> None:
        box.setStyleSheet(_messagebox_qss_from_tokens(self._tokens()))

    def show_info(self, title, message):
        box = QMessageBox(QMessageBox.Information, title, message, QMessageBox.Ok, self.parent)
        self._apply_tokens_to_box(box)
        box.exec()

    def show_warning(self, title, message):
        box = QMessageBox(QMessageBox.Warning, title, message, QMessageBox.Ok, self.parent)
        self._apply_tokens_to_box(box)
        box.exec()

    def show_critical(self, title, message):
        box = QMessageBox(QMessageBox.Critical, title, message, QMessageBox.Ok, self.parent)
        self._apply_tokens_to_box(box)
        box.exec()

    def ask_yes_no(self, title, message) -> bool:
        box = QMessageBox(
            QMessageBox.Question, title, message,
            QMessageBox.Yes | QMessageBox.No,
            self.parent
        )
        self._apply_tokens_to_box(box)
        return box.exec() == QMessageBox.Yes