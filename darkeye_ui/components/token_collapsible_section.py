# darkeye_ui/components/token_collapsible_section.py - 可折叠面板，由设计令牌驱动
"""可折叠面板（Accordion 风格），背景与图标由设计令牌驱动。"""

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSizePolicy, QToolButton, QVBoxLayout, QWidget

from ..design import get_builtin_icon
from ..design.theme_context import resolve_theme_manager
from ..design.tokens import LIGHT_TOKENS, ThemeTokens

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class TokenCollapsibleSection(QWidget):
    """可折叠面板：标题栏背景由设计令牌驱动，支持主题切换。"""

    toggled = Signal(bool)

    def __init__(
        self,
        title: str = "标题",
        theme_manager: Optional["ThemeManager"] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._is_expanded = False

        theme_manager = resolve_theme_manager(theme_manager, "TokenCollapsibleSection")
        self._theme_manager = theme_manager
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._apply_token_styles)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        self.toggle_btn = QToolButton()
        self.toggle_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.toggle_btn.setText(title)
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(False)
        self.toggle_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._update_icon(False)
        self.toggle_btn.toggled.connect(self.toggle_content)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.content.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.toggle_btn)
        layout.addWidget(self.content)

        self._apply_token_styles()

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _update_icon(self, expanded: bool) -> None:
        t = self._tokens()
        icon = get_builtin_icon(
            "chevron_down" if expanded else "chevron_right", size=16, color=t.color_icon
        )
        self.toggle_btn.setIcon(icon)

    def _apply_token_styles(self) -> None:
        t = self._tokens()
        self.toggle_btn.setStyleSheet(f"""
            QToolButton {{
                border: none;
                background: {t.color_bg_page};
                padding: 8px;
                font-weight: bold;
                text-align: left;
                color: {t.color_text};
            }}
            QToolButton:checked {{
                background: {t.color_bg_input};
            }}
        """)
        self._update_icon(self._is_expanded)

    def toggle_content(self, checked: bool) -> None:
        self._is_expanded = checked
        self._update_icon(checked)
        self.content.setVisible(checked)
        if checked:
            self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        else:
            self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.content.updateGeometry()
        self.updateGeometry()
        self.toggled.emit(checked)

    def addWidget(self, widget) -> None:
        self.content_layout.addWidget(widget)

    def addLayout(self, layout) -> None:
        self.content_layout.addLayout(layout)

    def expand(self) -> None:
        self.toggle_btn.setChecked(True)

    def collapse(self) -> None:
        self.toggle_btn.setChecked(False)
