from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from ..design.theme_context import resolve_theme_manager
from .button import Button
from .input import LineEdit

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class SearchBar(QWidget):
    """Search bar with quick clear and filter entry actions."""

    searchChanged = Signal(str)
    searchSubmitted = Signal(str)
    clearRequested = Signal()
    filterRequested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        placeholder: str = "Search...",
        theme_manager: Optional["ThemeManager"] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DesignSearchBar")

        self._theme_manager = resolve_theme_manager(theme_manager, "SearchBar")
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._on_theme_changed)

        self._line_edit = LineEdit(self)
        self._line_edit.setPlaceholderText(placeholder)
        self._line_edit.installEventFilter(self)

        self._btn_clear = Button("Clear")
        self._btn_filter = Button("Filter")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._line_edit, 1)
        layout.addWidget(self._btn_clear)
        layout.addWidget(self._btn_filter)

        self._line_edit.textChanged.connect(self._on_text_changed)
        self._line_edit.returnPressed.connect(self._on_submit)
        self._btn_clear.clicked.connect(self._on_clear_clicked)
        self._btn_filter.clicked.connect(self.filterRequested.emit)

    def text(self) -> str:
        return self._line_edit.text()

    def set_text(self, value: str) -> None:
        self._line_edit.setText(value)

    def line_edit(self) -> LineEdit:
        return self._line_edit

    def eventFilter(self, obj, event) -> bool:
        if obj is self._line_edit and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape and self._line_edit.text():
                self._on_clear_clicked()
                return True
        return super().eventFilter(obj, event)

    def _on_text_changed(self, text: str) -> None:
        self.searchChanged.emit(text)

    def _on_submit(self) -> None:
        self.searchSubmitted.emit(self._line_edit.text())

    def _on_clear_clicked(self) -> None:
        if not self._line_edit.text():
            return
        self._line_edit.clear()
        self._line_edit.setFocus()
        self.clearRequested.emit()

    def _on_theme_changed(self, *_args) -> None:
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()
