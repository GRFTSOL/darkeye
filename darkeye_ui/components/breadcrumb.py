from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from ..design.theme_context import resolve_theme_manager
from .button import Button
from .label import Label

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class Breadcrumb(QWidget):
    """Clickable breadcrumb navigation."""

    crumbClicked = Signal(int, str)

    def __init__(
        self,
        items: Optional[Iterable[str]] = None,
        parent: Optional[QWidget] = None,
        *,
        theme_manager: Optional["ThemeManager"] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DesignBreadcrumb")

        self._theme_manager = resolve_theme_manager(theme_manager, "Breadcrumb")
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._on_theme_changed)

        self._items: list[str] = []
        self._current_index = -1
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self.set_items(items or [])

    def items(self) -> list[str]:
        return list(self._items)

    def current_index(self) -> int:
        return self._current_index

    def set_items(self, items: Iterable[str]) -> None:
        self._items = [str(i) for i in items]
        self._current_index = len(self._items) - 1 if self._items else -1
        self._rebuild()

    def set_current_index(self, index: int) -> None:
        if not self._items:
            self._current_index = -1
            self._rebuild()
            return
        self._current_index = max(0, min(index, len(self._items) - 1))
        self._rebuild()

    def _rebuild(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for index, text in enumerate(self._items):
            if index == self._current_index:
                btn = Button(text, variant="primary")
                btn.setEnabled(False)
            else:
                btn = Button(text)
                btn.clicked.connect(
                    lambda _=False, i=index, value=text: self._on_crumb_clicked(
                        i, value
                    )
                )
            self._layout.addWidget(btn)
            if index < len(self._items) - 1:
                sep = Label("/")
                sep.setObjectName("DesignBreadcrumbSeparator")
                self._layout.addWidget(sep)
        self._layout.addStretch(1)

    def _on_crumb_clicked(self, index: int, value: str) -> None:
        self._current_index = index
        self._rebuild()
        self.crumbClicked.emit(index, value)

    def _on_theme_changed(self, *_args) -> None:
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()
