# darkeye_ui/components/completer_line_edit.py - 带异步补全的单行输入，令牌驱动
from PySide6.QtWidgets import QCompleter
from PySide6.QtCore import Qt, QEvent, Signal, Slot, QThreadPool, QRunnable
from typing import Callable, Optional, TYPE_CHECKING

from .._logging import get_logger, warn_once
from .input import LineEdit
from ..design.theme_context import resolve_theme_manager
from ..design.tokens import LIGHT_TOKENS

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager

_log = get_logger(__name__)


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
    """在后台线程执行 loader_func，结果通过 signal 传回主线程（携带请求序号）。"""

    def __init__(
        self, loader_func: Callable[[], list], request_seq: int, signal: Signal
    ):
        super().__init__()
        self.loader_func = loader_func
        self.request_seq = request_seq
        self.signal = signal
        self._logger = get_logger(__name__)

    def run(self):
        try:
            items = self.loader_func() if self.loader_func else []
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            warn_once(
                self._logger,
                "CompleterLineEdit:loader_failed",
                "CompleterLineEdit: loader_func failed, fallback to empty items.",
                exc_info=exc,
            )
            items = []
        self.signal.emit(self.request_seq, items)


class CompleterLineEdit(LineEdit):
    """支持传入加载函数的单行输入，带弹出补全；异步加载 + 缓存。弹出框由设计令牌驱动（objectName=DesignCompleterPopup）。"""

    itemsLoaded = Signal(int, list)

    def __init__(
        self,
        loader_func: Callable[[], list] | None = None,
        parent=None,
        theme_manager: Optional["ThemeManager"] = None,
    ):
        """
        :param loader_func: 返回项目列表的函数（在后台线程执行）
        :param parent: 父组件
        :param theme_manager: 可选，用于主题切换时刷新弹出框颜色；未传则从 controller.app_context 获取
        """
        super().__init__(parent)
        self.items: list = []
        self.loader_func = loader_func
        self._load_seq = 0
        self._cache: list = []
        theme_manager = resolve_theme_manager(theme_manager, "CompleterLineEdit")
        self._theme_manager = theme_manager
        self.setup_completer()
        self.itemsLoaded.connect(self._on_items_loaded)
        self.installEventFilter(self)
        self.load_items()
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._on_theme_changed)

    def set_loader_func(self, loader_func: Callable[[], list] | None):
        """设置新的加载函数并异步重新加载"""
        self.loader_func = loader_func
        self.reload_items()

    def load_items(self):
        """发起异步加载；多次调用时仅最后一次完成时会应用结果（旧请求丢弃）。"""
        if self.loader_func is None:
            return
        self._load_seq += 1
        seq = self._load_seq
        runnable = CompleterLoaderRunnable(self.loader_func, seq, self.itemsLoaded)
        QThreadPool.globalInstance().start(runnable)

    @Slot(int, list)
    def _on_items_loaded(self, seq: int, items: list):
        """主线程：收到异步加载结果，更新缓存与补全列表"""
        if seq != self._load_seq:
            return
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
        old = getattr(self, "completer1", None)
        if old is not None:
            try:
                old.popup().hide()
            except RuntimeError as e:
                _log.debug(
                    "setup_completer: 隐藏旧补全 popup 失败（可能已销毁）: %s",
                    e,
                    exc_info=True,
                )
        # 无 parent 的 QCompleter 由 setCompleter 接管；直接 setCompleter(新) 会换下旧 completer，
        # 勿再 setCompleter(None)+deleteLater(old)，否则 PySide 下易出现 C++ 对象已被销毁的 RuntimeError。
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
