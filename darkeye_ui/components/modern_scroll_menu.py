# darkeye_ui/components/modern_scroll_menu.py - 导航/滚动菜单，由设计令牌驱动
"""标准导航滚动菜单：顶部 Tab 导航 + 内容区滚动，样式由设计令牌驱动。"""
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..design.tokens import LIGHT_TOKENS, ThemeTokens

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class ModernScrollMenu(QWidget):
    """导航滚动菜单：顶部 Tab 导航 + 内容区滚动，样式由设计令牌驱动。"""

    def __init__(
        self,
        content_dict: dict,
        theme_manager: Optional["ThemeManager"] = None,
        parent=None,
    ):
        super().__init__(parent)
        if theme_manager is None:
            try:
                from app_context import get_theme_manager
                theme_manager = get_theme_manager()
            except Exception:
                theme_manager = None
        self._theme_manager = theme_manager

        self.nav_buttons = {}
        self.section_widgets = []
        self._title_labels: list[QLabel] = []
        self._separators: list[QFrame] = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.nav_container = QWidget()
        self.btn_layout = QHBoxLayout(self.nav_container)
        self.btn_layout.setContentsMargins(20, 10, 20, 0)
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        main_layout.addWidget(self.nav_container)

        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._apply_token_styles)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll_content = QWidget()
        self.content_layout = QVBoxLayout(self.scroll_content)
        self.content_layout.setContentsMargins(40, 20, 40, 20)
        self.scroll.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll)

        self.build_from_dict(content_dict)
        self._apply_token_styles()
        self.btn_layout.addStretch()

        self.scroll.verticalScrollBar().valueChanged.connect(self.on_scroll_update_nav)
        self.is_animating = False

    def build_from_dict(self, content_dict: dict) -> None:
        for i, (title_text, widget_instance) in enumerate(content_dict.items()):
            btn = QPushButton(title_text)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            if i == 0:
                btn.setChecked(True)
            self.btn_group.addButton(btn)
            self.btn_layout.addWidget(btn)
            self.nav_buttons[title_text] = btn

            section_wrapper = QWidget()
            sec_layout = QHBoxLayout(section_wrapper)
            sec_layout.setContentsMargins(0, 10, 0, 10)
            title_label = QLabel(title_text)
            title_label.setFixedWidth(100)
            self._title_labels.append(title_label)
            sec_layout.addWidget(title_label)
            sec_layout.addSpacing(100)
            sec_layout.addWidget(widget_instance)
            self.content_layout.addWidget(section_wrapper)
            self.section_widgets.append((section_wrapper, btn))
            btn.clicked.connect(lambda chk, w=section_wrapper, b=btn: self.scroll_to_widget(w, b))

            if i < len(content_dict) - 1:
                self.content_layout.addWidget(self.create_separator())
        self.content_layout.addStretch(1)

    def create_separator(self) -> QFrame:
        line = QFrame()
        self._separators.append(line)
        return line

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _apply_token_styles(self) -> None:
        t = self._tokens()
        self.setStyleSheet(f"background-color: {t.color_bg};")
        self.nav_container.setStyleSheet(f"""
            QPushButton {{
                border: none; background-color: transparent; color: {t.color_text_placeholder};
                padding: 10px 15px; font-size: 15px; border-bottom: {t.border_width} solid transparent;
                border-radius: 0px;
            }}
            QPushButton:hover {{ color: {t.color_text}; }}
            QPushButton:checked {{ color: {t.color_primary}; font-weight: bold; border-bottom: {t.border_width} solid {t.color_primary}; }}
        """)
        for lbl in self._title_labels:
            lbl.setStyleSheet(
                f"font-size: 18px; font-weight: bold; color: {t.color_text}; "
                "qproperty-alignment: 'AlignLeft | AlignTop';"
            )
        for sep in self._separators:
            sep.setStyleSheet(
                f"background-color: {t.color_bg_page}; min-height: 1px; max-height: 1px; margin: 10px 0px;"
            )

    def set_animating_false(self) -> None:
        self.is_animating = False

    def on_scroll_update_nav(self, value: int) -> None:
        if self.is_animating:
            return
        threshold = 50
        current_active_btn = None
        for widget, btn in self.section_widgets:
            if widget.pos().y() <= value + threshold:
                current_active_btn = btn
            else:
                break
        if current_active_btn:
            current_active_btn.blockSignals(True)
            current_active_btn.setChecked(True)
            current_active_btn.blockSignals(False)

    def scroll_to_widget(self, widget: QWidget, btn: QPushButton) -> None:
        self.is_animating = True
        bar = self.scroll.verticalScrollBar()
        target_y = widget.pos().y()
        self.anim = QPropertyAnimation(bar, b"value")
        self.anim.setDuration(500)
        self.anim.setEndValue(target_y)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.finished.connect(self.set_animating_false)
        self.anim.start()
