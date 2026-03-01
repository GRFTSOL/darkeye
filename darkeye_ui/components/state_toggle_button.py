# ui/components/state_toggle_button.py - 设计系统状态切换按钮，由令牌驱动颜色与样式
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import QPushButton

from ..design import get_builtin_icon
from ..design.tokens import ThemeTokens, LIGHT_TOKENS

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class StateToggleButton(QPushButton):
    """双状态切换按钮：图标与颜色由设计令牌驱动，支持主题切换时刷新。"""

    stateChanged = Signal(bool)

    def __init__(
        self,
        state1_icon: str = "x",
        state2_icon: str = "check",
        icon_size: int = 24,
        out_size: int = 24,
        hoverable: bool = True,
        theme_manager: Optional["ThemeManager"] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("DesignStateToggleButton")
        self._state = False  # False: 状态1, True: 状态2
        self._state1_icon_name = state1_icon
        self._state2_icon_name = state2_icon
        self._icon_size = icon_size
        self._out_size = out_size
        self._hoverable = hoverable
        self._theme_manager = theme_manager

        self.setFixedSize(out_size, out_size)
        self._refresh_icons()
        self.setIconSize(QSize(icon_size, icon_size))

        if theme_manager is not None:
            theme_manager.themeChanged.connect(self._refresh_icons)

        self.clicked.connect(self._toggle_state)

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _refresh_icons(self) -> None:
        t = self._tokens()
        icon_off = get_builtin_icon(
            self._state1_icon_name, size=self._icon_size, color=t.color_icon
        )
        icon_on = get_builtin_icon(
            self._state2_icon_name, size=self._icon_size, color=t.color_primary
        )
        self._icon_state1 = icon_off
        self._icon_state2 = icon_on
        self.setIcon(self._icon_state2 if self._state else self._icon_state1)

    def _toggle_state(self) -> None:
        self._state = not self._state
        self.setIcon(self._icon_state2 if self._state else self._icon_state1)
        self.setToolTip("已激活" if self._state else "默认")
        self.stateChanged.emit(self._state)

    def set_state(self, state: bool) -> None:
        if state != self._state:
            self._state = state
            self.setIcon(self._icon_state2 if state else self._icon_state1)

    def get_state(self) -> bool:
        return self._state

    def sizeHint(self) -> QSize:
        return QSize(self._out_size, self._out_size)
