from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional, Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from ..design.theme_context import resolve_theme_manager
from .button import Button
from .combo_box import ComboBox
from .label import Label

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class Pagination(QWidget):
    """Pagination widget for table/list style data pages."""

    pageChanged = Signal(int)
    pageSizeChanged = Signal(int)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        total_items: int = 0,
        page_size: int = 10,
        page_size_options: Optional[Sequence[int]] = None,
        theme_manager: Optional["ThemeManager"] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DesignPagination")

        self._theme_manager = resolve_theme_manager(theme_manager, "Pagination")
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._on_theme_changed)

        self._total_items = max(0, total_items)
        self._page_size_options = sorted(set(page_size_options or (10, 20, 50, 100)))
        if page_size not in self._page_size_options:
            self._page_size_options.append(page_size)
            self._page_size_options.sort()
        self._page_size = max(1, page_size)
        self._current_page = 1

        self._label_size = Label("Page size:")
        self._combo_size = ComboBox()
        for size in self._page_size_options:
            self._combo_size.addItem(str(size), size)
        idx = self._combo_size.findData(self._page_size)
        if idx >= 0:
            self._combo_size.setCurrentIndex(idx)

        self._btn_prev = Button("Prev")
        self._btn_next = Button("Next")
        self._label_info = Label("")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._label_size)
        layout.addWidget(self._combo_size)
        layout.addSpacing(8)
        layout.addWidget(self._btn_prev)
        layout.addWidget(self._btn_next)
        layout.addSpacing(8)
        layout.addWidget(self._label_info, 1)

        self._combo_size.currentIndexChanged.connect(self._on_page_size_changed)
        self._btn_prev.clicked.connect(self._on_prev_clicked)
        self._btn_next.clicked.connect(self._on_next_clicked)

        self._update_ui()

    def total_items(self) -> int:
        return self._total_items

    def page_size(self) -> int:
        return self._page_size

    def current_page(self) -> int:
        return self._current_page

    def total_pages(self) -> int:
        return max(1, math.ceil(self._total_items / self._page_size))

    def set_total_items(self, total_items: int) -> None:
        self._total_items = max(0, total_items)
        self._current_page = min(self._current_page, self.total_pages())
        self._update_ui()

    def set_current_page(self, page: int, *, emit: bool = True) -> None:
        new_page = min(max(1, page), self.total_pages())
        if new_page == self._current_page:
            return
        self._current_page = new_page
        self._update_ui()
        if emit:
            self.pageChanged.emit(self._current_page)

    def set_page_size(self, size: int, *, emit: bool = True) -> None:
        new_size = max(1, int(size))
        if new_size not in self._page_size_options:
            self._page_size_options.append(new_size)
            self._page_size_options.sort()
            self._combo_size.blockSignals(True)
            self._combo_size.clear()
            for option in self._page_size_options:
                self._combo_size.addItem(str(option), option)
            self._combo_size.blockSignals(False)
        if new_size == self._page_size:
            return
        self._page_size = new_size
        self._current_page = min(self._current_page, self.total_pages())

        idx = self._combo_size.findData(self._page_size)
        if idx >= 0:
            self._combo_size.blockSignals(True)
            self._combo_size.setCurrentIndex(idx)
            self._combo_size.blockSignals(False)

        self._update_ui()
        if emit:
            self.pageSizeChanged.emit(self._page_size)
            self.pageChanged.emit(self._current_page)

    def _on_prev_clicked(self) -> None:
        self.set_current_page(self._current_page - 1)

    def _on_next_clicked(self) -> None:
        self.set_current_page(self._current_page + 1)

    def _on_page_size_changed(self, index: int) -> None:
        if index < 0:
            return
        size = self._combo_size.itemData(index)
        if size is None:
            return
        self.set_page_size(int(size))

    def _update_ui(self) -> None:
        pages = self.total_pages()
        self._btn_prev.setEnabled(self._current_page > 1)
        self._btn_next.setEnabled(self._current_page < pages)
        self._label_info.setText(
            f"Page {self._current_page}/{pages} | Total {self._total_items}"
        )

    def _on_theme_changed(self, *_args) -> None:
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()
