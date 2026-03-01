# darkeye_ui/components/lazy_scroll_area.py - 瀑布流懒加载滚动区，由设计令牌驱动
"""瀑布流 + 懒加载滚动区，滚动条样式由设计令牌驱动。"""
from typing import TYPE_CHECKING, Callable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLayoutItem, QScrollArea, QScrollBar, QVBoxLayout, QWidget

from ..layouts import WaterfallLayout
from ..design.tokens import LIGHT_TOKENS, ThemeTokens

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager

_MAX_SCROLL_CHECK_RETRIES = 10


def _scrollbar_style_from_tokens(t: ThemeTokens) -> str:
    """根据主题令牌生成滚动条样式。"""
    return f"""
        QScrollArea {{
            border: none;
        }}
        QScrollBar:vertical {{
            background-color: {t.color_bg_page};
            width: 10px;
            margin: 0;
            border: none;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {t.color_border};
            border-radius: 4px;
            min-height: 30px;
            margin: 2px 1px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {t.color_primary};
        }}
        QScrollBar::handle:vertical:pressed {{
            background-color: {t.color_primary_hover};
        }}
        QScrollBar:horizontal {{
            background-color: {t.color_bg_page};
            height: 10px;
            margin: 0;
            border: none;
            border-radius: 5px;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {t.color_border};
            border-radius: 4px;
            min-width: 30px;
            margin: 1px 2px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: {t.color_primary};
        }}
        QScrollBar::handle:horizontal:pressed {{
            background-color: {t.color_primary_hover};
        }}
    """


class LazyScrollArea(QScrollArea):
    """瀑布流懒加载滚动区：滚动条样式由设计令牌驱动，支持主题切换。"""

    def __init__(
        self,
        column_width: int = 200,
        widget: Optional[QWidget] = None,
        hint: bool = True,
        theme_manager: Optional["ThemeManager"] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWidgetResizable(True)

        if theme_manager is None:
            try:
                from app_context import get_theme_manager
                theme_manager = get_theme_manager()
            except Exception:
                pass
        self._theme_manager = theme_manager
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._apply_token_styles)
        self._apply_token_styles()

        try:
            from controller.MessageService import MessageBoxService
            self.msg = MessageBoxService(self)
        except Exception:
            self.msg = None

        self._hint = hint

        if widget is not None:
            content_widget = QWidget()
            vlayout = QVBoxLayout(content_widget)
            waterfall_widget = QWidget()
            self.waterfall_layout = WaterfallLayout(waterfall_widget, column_width=column_width)
            vlayout.setContentsMargins(0, 0, 0, 0)
            vlayout.addWidget(widget, 0, Qt.AlignCenter | Qt.AlignmentFlag.AlignTop)
            vlayout.addWidget(waterfall_widget, 0, Qt.AlignmentFlag.AlignTop)
            vlayout.addStretch()
        else:
            content_widget = QWidget()
            self.waterfall_layout = WaterfallLayout(content_widget, column_width=column_width)

        self.waterfall_layout.setContentsMargins(0, 5, 0, 0)
        self.setWidget(content_widget)

        self.page_size = 30
        self.current_page = 0
        self.reached_end = False
        self.loading = False
        self._loader_fn: Optional[Callable] = None
        self._scroll_check_retries = 0

        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _apply_token_styles(self) -> None:
        self.setStyleSheet(_scrollbar_style_from_tokens(self._tokens()))

    def set_loader(self, loader_fn: Callable) -> None:
        """设置加载函数，loader_fn(page_index, page_size) -> List[QWidget]"""
        self._loader_fn = loader_fn
        self.reset()

    def reset(self) -> None:
        while self.waterfall_layout.count():
            item: QLayoutItem = self.waterfall_layout.takeAt(0)
            w: QWidget = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self.waterfall_layout.update()
        self.current_page = 0
        self.reached_end = False
        self.verticalScrollBar().setValue(0)
        self._load_next_page()

    def _on_scroll(self, value: int) -> None:
        sb: QScrollBar = self.verticalScrollBar()
        if not self.loading and not self.reached_end and value >= sb.maximum() - 300:
            self._load_next_page()

    def _load_next_page(self) -> None:
        if self._loader_fn is None:
            return
        self.loading = True
        self._fetch_and_append()

    def _fetch_and_append(self) -> None:
        widgets: list = self._loader_fn(self.current_page, self.page_size)
        if not widgets:
            self.reached_end = True
        else:
            if len(widgets) < self.page_size:
                self.reached_end = True
            for w in widgets:
                self.waterfall_layout.addWidget(w)
            self.current_page += 1
        self.loading = False
        if not self.reached_end:
            self._scroll_check_retries = 0
            QTimer.singleShot(0, self._check_scrollable_and_load_next)

    def _check_scrollable_and_load_next(self) -> None:
        sb = self.verticalScrollBar()
        if sb.maximum() == 0 and not self.reached_end and not self.loading:
            self._load_next_page()
            return
        if sb.maximum() == 0 and not self.reached_end and self._scroll_check_retries < _MAX_SCROLL_CHECK_RETRIES:
            self._scroll_check_retries += 1
            QTimer.singleShot(50, self._check_scrollable_and_load_next)

    def showEvent(self, event):
        super().showEvent(event)
        self.waterfall_layout.invalidate()
