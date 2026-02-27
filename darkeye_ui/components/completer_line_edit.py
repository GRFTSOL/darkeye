# darkeye_ui/components/completer_line_edit.py - 带异步补全的单行输入，令牌驱动
from PySide6.QtWidgets import QCompleter
from PySide6.QtCore import Qt, QEvent, Signal, Slot, QThreadPool, QRunnable
from typing import Callable, Optional, TYPE_CHECKING

from .input import LineEdit
from ..design.tokens import LIGHT_TOKENS

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


def _popup_qss_from_tokens(t) -> str:
    """根据当前主题令牌生成 DesignCompleterPopup 的 QSS，使弹出框随主题变色。"""
    return f"""
QAbstractItemView#DesignCompleterPopup {{
    background-color: {t.color_bg};
    color: {t.color_text};
    border: {t.border_width} solid {t.color_border};
    border-radius: 0;
    padding: 4px;
    selection-background-color: {t.color_primary};
    font-family: {t.font_family_base};
    font-size: {t.font_size_base};
}}
QAbstractItemView#DesignCompleterPopup::item {{
    padding: 4px 8px;
    color: {t.color_text};
}}
QAbstractItemView#DesignCompleterPopup::item:selected {{
    background-color: {t.color_primary};
    color: {t.color_text_inverse};
}}
QAbstractItemView#DesignCompleterPopup::item:hover {{
    background-color: {t.color_bg_input};
    color: {t.color_text};
}}
"""


class CompleterLoaderRunnable(QRunnable):
    """在后台线程执行 loader_func，结果通过 signal 传回主线程"""

    def __init__(self, loader_func: Callable[[], list], signal: Signal):
        super().__init__()
        self.loader_func = loader_func
        self.signal = signal

    def run(self):
        try:
            items = self.loader_func() if self.loader_func else []
        except Exception:
            items = []
        self.signal.emit(items)


class CompleterLineEdit(LineEdit):
    """支持传入加载函数的单行输入，带弹出补全；异步加载 + 缓存。弹出框由设计令牌驱动（objectName=DesignCompleterPopup）。"""

    items_loaded = Signal(list)

    def __init__(self, loader_func: Callable[[], list] | None = None, parent=None, theme_manager: Optional["ThemeManager"] = None):
        """
        :param loader_func: 返回项目列表的函数（在后台线程执行）
        :param parent: 父组件
        :param theme_manager: 可选，用于主题切换时刷新弹出框颜色；未传则从 app_context 获取
        """
        super().__init__(parent)
        self.items: list = []
        self.loader_func = loader_func
        self._loading = False
        self._cache: list = []
        if theme_manager is None:
            try:
                from app_context import get_theme_manager
                theme_manager = get_theme_manager()
            except Exception:
                pass
        self._theme_manager = theme_manager
        self.setup_completer()
        self.items_loaded.connect(self._on_items_loaded)
        self.installEventFilter(self)
        self.load_items()
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._on_theme_changed)

    def set_loader_func(self, loader_func: Callable[[], list] | None):
        """设置新的加载函数并异步重新加载"""
        self.loader_func = loader_func
        self.reload_items()

    def load_items(self):
        """发起异步加载；若正在加载则忽略（防抖）。"""
        if self.loader_func is None or self._loading:
            return
        self._loading = True
        runnable = CompleterLoaderRunnable(self.loader_func, self.items_loaded)
        QThreadPool.globalInstance().start(runnable)

    @Slot(list)
    def _on_items_loaded(self, items: list):
        """主线程：收到异步加载结果，更新缓存与补全列表"""
        self._loading = False
        self._cache = list(items) if items is not None else []
        self.items = self._cache
        self.setup_completer()

    def _tokens(self):
        """当前主题令牌，用于弹出框 QSS。"""
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _apply_popup_style(self):
        """用当前主题令牌给弹出框设置 QSS，解决主题切换后 popup 不随 app.setStyleSheet 更新的问题。"""
        if not hasattr(self, "completer1") or self.completer1 is None:
            return
        popup = self.completer1.popup()
        popup.setStyleSheet(_popup_qss_from_tokens(self._tokens()))

    def _on_theme_changed(self):
        """主题切换时刷新弹出框样式，下次打开 popup 即为新主题。"""
        self._apply_popup_style()

    def setup_completer(self):
        """设置/重新设置自动完成器（使用当前 items），弹出框使用 DesignCompleterPopup 由 QSS 令牌驱动。"""
        self.completer1 = QCompleter(self.items)
        self.completer1.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer1.setFilterMode(Qt.MatchContains)
        self.completer1.setCompletionMode(QCompleter.PopupCompletion)
        popup = self.completer1.popup()
        popup.setObjectName("DesignCompleterPopup")
        self.setCompleter(self.completer1)
        self._apply_popup_style()

    def reload_items(self):
        """重新异步加载项目并刷新自动完成（会忽略缓存，重新请求）。"""
        self.load_items()

    def eventFilter(self, obj, event):
        if obj == self and event.type() == QEvent.FocusIn:
            self.try_show_completer()
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        self.try_show_completer()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.try_show_completer()

    def try_show_completer(self):
        """尝试显示自动完成弹出框"""
        if not hasattr(self, "completer1") or self.completer1 is None:
            return
        text = self.text()
        self.completer1.setCompletionPrefix(text)
        if self.completer1.popup().isVisible():
            return
        if text == "" or self.completer1.completionCount() > 0:
            self._apply_popup_style()
            self.completer1.complete(self.rect())
