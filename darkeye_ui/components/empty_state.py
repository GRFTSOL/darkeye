from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..design.theme_context import resolve_theme_manager
from .button import Button
from .label import Label

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class EmptyState(QWidget):
    """Empty-state widget with icon, title, description and optional action."""

    actionTriggered = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        title: str = "No Data",
        description: str = "There is no data to display.",
        icon_text: str = "○",
        action_text: Optional[str] = None,
        theme_manager: Optional["ThemeManager"] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DesignEmptyState")

        self._theme_manager = resolve_theme_manager(theme_manager, "EmptyState")
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._on_theme_changed)

        self._icon_label = Label(icon_text)
        self._icon_label.setObjectName("DesignEmptyStateIcon")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title_label = Label(title)
        self._title_label.setObjectName("DesignEmptyStateTitle")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._desc_label = Label(description)
        self._desc_label.setObjectName("DesignEmptyStateDescription")
        self._desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._desc_label.setWordWrap(True)

        self._action_button = Button(action_text or "Refresh", variant="primary")
        self._action_button.setVisible(bool(action_text))
        self._action_button.clicked.connect(self.actionTriggered.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addStretch(1)
        layout.addWidget(self._icon_label)
        layout.addWidget(self._title_label)
        layout.addWidget(self._desc_label)
        layout.addWidget(self._action_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

    def set_title(self, text: str) -> None:
        self._title_label.setText(text)

    def set_description(self, text: str) -> None:
        self._desc_label.setText(text)

    def set_icon_text(self, text: str) -> None:
        self._icon_label.setText(text)

    def set_action_text(self, text: Optional[str]) -> None:
        visible = bool(text)
        if visible:
            self._action_button.setText(text or "")
        self._action_button.setVisible(visible)

    def _on_theme_changed(self, *_args) -> None:
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()
