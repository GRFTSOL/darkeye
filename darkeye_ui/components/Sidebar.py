from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional, Sequence, Union

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..design.icon import BUILTIN_ICONS
from ..design.theme_context import resolve_theme_manager
from ..design.theme_manager import ThemeManager
from ..design.tokens import ThemeTokens
from .icon_push_button import IconPushButton


if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget as _QWidget


MenuDef = tuple[str, str, str]


class MenuButton(QWidget):
    clicked = Signal()

    def __init__(
        self,
        text: str,
        icon_name: str,
        icon_path: Optional[Union[str, Path]] = None,
        expanded_width: int = 240,
        collapsed_width: int = 60,
        theme_tokens: Optional[ThemeTokens] = None,
        theme_manager: Optional[ThemeManager] = None,
    ) -> None:
        super().__init__()
        self.setFixedHeight(50)
        self.setFixedWidth(expanded_width)
        self.setAttribute(Qt.WA_StyledBackground)  # type: ignore[arg-type]
        self._is_selected = False
        self._tokens = theme_tokens

        self.mainlayout = QHBoxLayout(self)
        self.mainlayout.setContentsMargins(0, 0, 0, 0)
        self.mainlayout.setSpacing(0)
        self.icon_label = IconPushButton(
            icon_name=icon_name,
            icon_path=icon_path,
            icon_size=20,
            out_size=collapsed_width,
            theme_manager=theme_manager,
            parent=self,
        )
        self.icon_label.setFixedSize(collapsed_width, 50)
        self.text_label = QLabel(text)
        self.text_label.setStyleSheet("border: none;")
        self.icon_label.setAttribute(Qt.WA_TransparentForMouseEvents)  # type: ignore[arg-type]
        self.text_label.setAttribute(Qt.WA_TransparentForMouseEvents)  # type: ignore[arg-type]
        self.mainlayout.addWidget(self.icon_label)
        self.mainlayout.addWidget(self.text_label)
        self.mainlayout.addStretch()
        self._update_style()

    def _update_style(self):
        if self._tokens is not None:
            text_normal = self._tokens.color_text
            # 侧边栏选中状态下也使用正常文字颜色，保证深色主题下在深背景上仍有足够对比度
            text_selected = self._tokens.color_text
            bg_selected = self._tokens.color_bg_input
            border_selected = self._tokens.color_border_focus
        else:
            text_normal = "#8a8e99"
            text_selected = "#ffffff"
            bg_selected = "#F7E6B0"
            border_selected = "#DBCA97"

        if self._is_selected:
            style = f"""
                MenuButton {{
                    background-color: {bg_selected};
                    border-left: 3px solid {border_selected};
                }}
                MenuButton:hover {{
                    background-color: {bg_selected};
                }}
                QLabel {{
                    color: {text_selected};
                    font-size: 13px;
                    background: transparent;
                }}
                MenuButton:hover QLabel {{
                    color: {text_selected};
                }}
            """
        else:
            style = f"""
                MenuButton {{
                    background-color: transparent;
                    border-left: 3px solid transparent;
                }}
                MenuButton:hover {{
                    background-color: {bg_selected};
                }}
                QLabel {{
                    color: {text_normal};
                    font-size: 13px;
                    background: transparent;
                }}
                MenuButton:hover QLabel {{
                    color: {text_selected};
                }}
            """
        self.setStyleSheet(style)

    def set_selected(self, selected: bool):
        if self._is_selected != selected:
            self._is_selected = selected
            self._update_style()

    def is_selected(self):
        return self._is_selected

    def mousePressEvent(self, event):
        self.clicked.emit()


class Sidebar(QWidget):
    itemClicked = Signal(str)
    selectedChanged = Signal(str)
    backwardClicked = Signal()
    forwardClicked = Signal()

    def __init__(
        self,
        menu_defs: Sequence[MenuDef] | None = None,
        icons_base_path: Optional[Union[str, Path]] = None,
        theme_manager: Optional[ThemeManager] = None,
        parent: _QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.expanded_width = 180
        self.collapsed_width = 60
        self.setMinimumWidth(self.collapsed_width)
        self.setMaximumWidth(self.collapsed_width)
        self._is_expanded = False

        self.menu_defs: list[MenuDef] = list(menu_defs) if menu_defs else []
        self._icons_base = Path(icons_base_path) if icons_base_path else None
        self._theme_manager: ThemeManager | None = resolve_theme_manager(
            theme_manager, "Sidebar"
        )
        self._tokens: ThemeTokens | None = None

        self._refresh_tokens_from_theme()

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.toggle_btn = self._create_menu_btn("隐藏菜单", "menu")
        self.toggle_btn.clicked.connect(self.toggle_menu)
        self.main_layout.addWidget(self.toggle_btn)

        # 前进 / 后退按钮行，放在缩放按钮下方
        self.nav_container = QWidget()
        self.nav_layout = QHBoxLayout(self.nav_container)
        self.nav_layout.setContentsMargins(0, 0, 0, 0)
        self.nav_layout.setSpacing(0)
        # 总宽度固定为侧边栏收缩状态宽度
        self.nav_container.setFixedWidth(self.collapsed_width)

        # 使用两个仅图标的 IconPushButton，占据与单个菜单按钮相同的总高度
        half_width = self.collapsed_width // 2
        self.back_btn = IconPushButton(
            icon_name="arrow_left",
            icon_size=20,
            out_size=half_width,
            theme_manager=self._theme_manager,
            parent=self.nav_container,
        )
        self.forward_btn = IconPushButton(
            icon_name="arrow_right",
            icon_size=20,
            out_size=self.collapsed_width - half_width,
            theme_manager=self._theme_manager,
            parent=self.nav_container,
        )
        self.back_btn.setFixedSize(half_width, 50)
        self.forward_btn.setFixedSize(self.collapsed_width - half_width, 50)

        self.back_btn.clicked.connect(self.backwardClicked)
        self.forward_btn.clicked.connect(self.forwardClicked)

        self.nav_layout.addWidget(self.back_btn)
        self.nav_layout.addWidget(self.forward_btn)
        # 让总宽度为收缩宽度的按钮行在展开时，贴近左侧对齐
        self.main_layout.addWidget(self.nav_container)

        self.menu_container = QWidget()
        self.menu_layout = QVBoxLayout(self.menu_container)
        self.menu_layout.setContentsMargins(0, 0, 0, 0)
        self.menu_layout.setSpacing(0)

        self.buttons: dict[str, MenuButton] = {}
        for mid, text, icon in self.menu_defs:
            btn = self._create_menu_btn(text, icon)
            btn.clicked.connect(lambda _=False, m=mid: self._on_menu_item_clicked(m))
            self.menu_layout.addWidget(btn)
            self.buttons[mid] = btn

        # 顶部菜单区与底部设置 / 帮助按钮之间留空
        self.menu_layout.addStretch()

        # 底部帮助按钮（不参与普通菜单选中态）
        self.help_btn = self._create_menu_btn("帮助", "circle_question_mark")
        self.help_btn.clicked.connect(self._on_help_clicked)
        self.menu_layout.addWidget(self.help_btn)

        # 底部设置按钮（不参与普通菜单选中态）
        self.settings_btn = self._create_menu_btn("设置", "settings")
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        self.menu_layout.addWidget(self.settings_btn)
        self.main_layout.addWidget(self.menu_container)

        if self.menu_defs:
            self._current_id: str | None = self.menu_defs[0][0]
            if self._current_id in self.buttons:
                self.buttons[self._current_id].set_selected(True)
        else:
            self._current_id = None

        self.anim = QPropertyAnimation(self, b"minimumWidth")
        self.anim.setDuration(500)
        self.anim.setEasingCurve(QEasingCurve.InOutQuint)  # type: ignore[arg-type]
        self.anim.valueChanged.connect(lambda v: self.setMaximumWidth(v))
        self.anim.setStartValue(self.collapsed_width)
        self.anim.setEndValue(self.expanded_width)

        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._on_theme_changed)

    def _refresh_tokens_from_theme(self) -> None:
        if self._theme_manager is not None:
            try:
                self._tokens = self._theme_manager.tokens()
            except Exception:
                self._tokens = None
        else:
            self._tokens = None

    def _create_menu_btn(self, text: str, icon_type: str) -> MenuButton:
        icon_name = icon_type
        icon_path: Optional[Path] = None
        if icon_type not in BUILTIN_ICONS and self._icons_base is not None:
            icon_path = self._icons_base / icon_type
        btn = MenuButton(
            text=text,
            icon_name=icon_name,
            icon_path=icon_path,
            expanded_width=self.expanded_width,
            collapsed_width=self.collapsed_width,
            theme_tokens=self._tokens,
            theme_manager=self._theme_manager,
        )
        return btn

    def _on_menu_item_clicked(self, menu_id: str) -> None:
        if self._current_id == menu_id:
            btn = self.buttons.get(menu_id)
            if btn:
                btn.set_selected(False)
            self._current_id = None
            self.selectedChanged.emit("")
        else:
            prev_btn = self.buttons.get(self._current_id)
            if prev_btn:
                prev_btn.set_selected(False)
            new_btn = self.buttons.get(menu_id)
            if new_btn:
                new_btn.set_selected(True)
            self._current_id = menu_id
            self.selectedChanged.emit(menu_id)
        self.itemClicked.emit(menu_id)

    def _on_settings_clicked(self) -> None:
        # 设置页不对应普通菜单项，清除现有选中，仅发出特殊 menu_id
        self.clear_selection()
        self.itemClicked.emit("setting")

    def _on_help_clicked(self) -> None:
        # 帮助页不对应普通菜单项，清除现有选中，仅发出特殊 menu_id
        self.clear_selection()
        self.itemClicked.emit("help")

    def get_selected_id(self) -> str | None:
        return self._current_id

    def clear_selection(self) -> None:
        if self._current_id is None:
            return
        btn = self.buttons.get(self._current_id)
        if btn:
            btn.set_selected(False)
        self._current_id = None
        self.selectedChanged.emit("")

    def select(self, menu_id: str) -> None:
        if self._current_id != menu_id:
            prev_btn = self.buttons.get(self._current_id)
            if prev_btn:
                prev_btn.set_selected(False)
            new_btn = self.buttons.get(menu_id)
            if new_btn:
                new_btn.set_selected(True)
            self._current_id = menu_id
            self.selectedChanged.emit(menu_id)

    def toggle_menu(self) -> None:
        if self._is_expanded:
            self.anim.setDirection(QPropertyAnimation.Direction.Backward)
        else:
            self.anim.setDirection(QPropertyAnimation.Direction.Forward)
        self.anim.start()
        self._is_expanded = not self._is_expanded

    def _on_theme_changed(self, *_args) -> None:
        self._refresh_tokens_from_theme()
        # 更新顶部“隐藏菜单”按钮
        if isinstance(self.toggle_btn, MenuButton):
            self.toggle_btn._tokens = self._tokens
            self.toggle_btn._update_style()
        # 更新菜单项按钮
        for btn in self.buttons.values():
            btn._tokens = self._tokens
            btn._update_style()
        # 更新底部设置 / 帮助按钮
        if hasattr(self, "settings_btn") and isinstance(self.settings_btn, MenuButton):
            self.settings_btn._tokens = self._tokens
            self.settings_btn._update_style()
        if hasattr(self, "help_btn") and isinstance(self.help_btn, MenuButton):
            self.help_btn._tokens = self._tokens
            self.help_btn._update_style()
        self.update()
