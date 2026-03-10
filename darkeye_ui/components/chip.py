from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ..design.theme_context import resolve_theme_manager
from .button import Button

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class Chip(Button):
    """Lightweight tag/chip component."""

    def __init__(
        self,
        text: str = "",
        parent=None,
        *,
        tone: str = "default",
        checkable: bool = False,
        checked: bool = False,
        theme_manager: Optional["ThemeManager"] = None,
    ) -> None:
        super().__init__(text=text, parent=parent)
        self.setObjectName("DesignChip")
        self.setProperty("tone", tone)
        self.setCheckable(checkable)
        if checkable:
            self.setChecked(checked)

        self._theme_manager = resolve_theme_manager(theme_manager, "Chip")
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._on_theme_changed)

    def set_tone(self, tone: str) -> None:
        self.setProperty("tone", tone)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    def _on_theme_changed(self, *_args) -> None:
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()


# Backward-compatible alias.
Tag = Chip
