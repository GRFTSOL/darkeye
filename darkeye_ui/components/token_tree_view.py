from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import QTreeView, QWidget

from ..design.theme_context import resolve_theme_manager

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class TreeView(QTreeView):
    """Token-driven tree view using global QSS + objectName."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        theme_manager: Optional["ThemeManager"] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DesignTreeView")
        self.setAlternatingRowColors(True)
        self.setUniformRowHeights(True)

        self._theme_manager = resolve_theme_manager(theme_manager, "TreeView")
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self, *_args) -> None:
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.viewport().update()


# Backward-compatible alias.
TokenTreeView = TreeView
