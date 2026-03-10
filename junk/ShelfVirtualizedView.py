from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLayout,
    QWidget,
    QHBoxLayout,
    QSizePolicy,
)

from core.database.query import get_workcardinfo_by_workid
from ui.basic import HorizontalScrollArea
from ui.widgets.ShelfItemWidget import ShelfItemWidget, SPINE_PLACEHOLDER_W


ESTIMATED_ITEM_WIDTH = 60
SPACING = 16
MARGIN = 2
SHELF_MARGIN_LEFT = 16
SHELF_MARGIN_RIGHT = 16
SHELF_MARGIN_TOP = 16
SHELF_MARGIN_BOTTOM = 20


class ShelfVirtualizedView(QWidget):
    def __init__(self, parent: QWidget | None = None, min_height: int = 600) -> None:
        super().__init__(parent)
        self._work_ids: List[int] = []
        self._widths: List[float] = []
        self._offsets: List[float] = []
        self._load_start = -1
        self._load_end = -2
        self._updating_range = False

        self.scroll_area = HorizontalScrollArea(self)
        self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.scroll_area.setMinimumHeight(min_height)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self._container = QWidget()
        self._container.setMinimumHeight(min_height)
        self.shelf_layout = QHBoxLayout(self._container)
        self.shelf_layout.setContentsMargins(
            SHELF_MARGIN_LEFT, SHELF_MARGIN_TOP, SHELF_MARGIN_RIGHT, SHELF_MARGIN_BOTTOM
        )
        self.shelf_layout.setSpacing(SPACING)
        self.shelf_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
        )
        self.shelf_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)

        self._left_placeholder = QWidget()
        self._left_placeholder.setFixedWidth(0)
        self._left_placeholder.setFixedHeight(1)
        self._right_placeholder = QWidget()
        self._right_placeholder.setFixedWidth(0)
        self._right_placeholder.setFixedHeight(1)
        self.shelf_layout.addWidget(
            self._left_placeholder, alignment=Qt.AlignmentFlag.AlignBottom
        )
        self.shelf_layout.addWidget(
            self._right_placeholder, alignment=Qt.AlignmentFlag.AlignBottom
        )

        self._container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.scroll_area.setWidget(self._container)

        self.scroll_area.scrolled.connect(self._on_shelf_scrolled)
        self.scroll_area.horizontalScrollBar().valueChanged.connect(
            self._on_scroll_value_changed
        )
        self.scroll_area.viewport().installEventFilter(self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll_area)

    def work_count(self) -> int:
        return len(self._work_ids)

    def set_work_ids(self, work_ids: list[int]) -> None:
        self._work_ids = work_ids
        N = len(self._work_ids)
        self._widths = [float(ESTIMATED_ITEM_WIDTH)] * N
        self._offsets = [0.0] * N if N > 0 else []
        self._load_start = -1
        self._load_end = -2
        self.scroll_area.horizontalScrollBar().setValue(0)
        if N == 0:
            while self.shelf_layout.count() > 2:
                item = self.shelf_layout.takeAt(1)
                if item and item.widget():
                    item.widget().deleteLater()
            self._left_placeholder.setFixedWidth(0)
            self._left_placeholder.hide()
            self._right_placeholder.setFixedWidth(0)
            self._right_placeholder.hide()
            self._container.setFixedWidth(0)
            return
        self._update_visible_range()

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent

        if obj is self.scroll_area.viewport() and event.type() == QEvent.Type.Resize:
            self._update_visible_range()
        elif isinstance(obj, ShelfItemWidget) and event.type() == QEvent.Type.Resize:
            idx = getattr(obj, "_shelf_index", -1)
            if 0 <= idx < len(self._widths):
                new_w = float(obj.width())
                if new_w > 0 and abs(self._widths[idx] - new_w) > 1.0:
                    self._widths[idx] = new_w
                    self._refresh_content_width()
        return super().eventFilter(obj, event)

    def _on_scroll_value_changed(self, _value: int) -> None:
        self._update_visible_range()
        self._on_shelf_scrolled(self.scroll_area.horizontalScrollBar().value())

    def _on_shelf_scrolled(self, _scroll_value: int) -> None:
        for i in range(self.shelf_layout.count()):
            item = self.shelf_layout.itemAt(i)
            if item is None:
                continue
            w = item.widget()
            if w and isinstance(w, ShelfItemWidget):
                w.check_mouse_position_on_scroll()

    def _rebuild_offsets_and_content_width(self) -> float:
        N = len(self._widths)
        if N == 0:
            self._offsets = []
            return 0.0

        offsets: List[float] = [0.0] * N
        offsets[0] = float(SHELF_MARGIN_LEFT)
        for i in range(1, N):
            prev_width = max(self._widths[i - 1], float(ESTIMATED_ITEM_WIDTH))
            offsets[i] = offsets[i - 1] + prev_width + SPACING

        self._offsets = offsets
        last_width = max(self._widths[N - 1], float(ESTIMATED_ITEM_WIDTH))
        content_width = offsets[N - 1] + last_width + float(SHELF_MARGIN_RIGHT)
        return content_width

    def _find_first_index(self, scroll_value: float) -> int:
        N = len(self._work_ids)
        if N == 0 or not self._offsets:
            return N

        lo, hi = 0, N
        while lo < hi:
            mid = (lo + hi) // 2
            effective_width = max(self._widths[mid], float(ESTIMATED_ITEM_WIDTH))
            if self._offsets[mid] + effective_width > scroll_value:
                hi = mid
            else:
                lo = mid + 1
        return lo

    def _find_last_index(self, scroll_right: float) -> int:
        N = len(self._work_ids)
        if N == 0 or not self._offsets:
            return -1

        lo, hi = 0, N
        while lo < hi:
            mid = (lo + hi) // 2
            if self._offsets[mid] < scroll_right:
                lo = mid + 1
            else:
                hi = mid
        return lo - 1

    def _refresh_content_width(self) -> None:
        if self._updating_range:
            return
        self._updating_range = True
        try:
            content_width = self._rebuild_offsets_and_content_width()
            self._container.setFixedWidth(int(content_width))
            if self._load_start >= 0 and self._load_end >= self._load_start:
                self._update_placeholders(self._load_start, self._load_end, content_width)
        finally:
            self._updating_range = False

    def _update_placeholders(
        self, load_start: int, load_end: int, content_width: float
    ) -> None:
        N = len(self._work_ids)
        if load_start > 0:
            left_w = (
                max(0, int(self._offsets[load_start] - float(SHELF_MARGIN_LEFT)))
                - SPACING
            )
            self._left_placeholder.setFixedWidth(left_w)
            self._left_placeholder.show()
        else:
            self._left_placeholder.setFixedWidth(0)
            self._left_placeholder.hide()
        if load_end < N - 1:
            effective_width_end = max(self._widths[load_end], float(ESTIMATED_ITEM_WIDTH))
            right_w = max(
                0,
                int(
                    content_width
                    - float(SHELF_MARGIN_RIGHT)
                    - (self._offsets[load_end] + effective_width_end)
                )
                - SPACING,
            )
            self._right_placeholder.setFixedWidth(right_w)
            self._right_placeholder.show()
        else:
            self._right_placeholder.setFixedWidth(0)
            self._right_placeholder.hide()

    def _update_visible_range(self) -> None:
        if self._updating_range:
            return
        self._updating_range = True
        try:
            self._do_update_visible_range()
        finally:
            self._updating_range = False

    def _do_update_visible_range(self) -> None:
        N = len(self._work_ids)
        if N == 0:
            return

        content_width = self._rebuild_offsets_and_content_width()
        viewport_width = self.scroll_area.viewport().width()
        scroll_value = self.scroll_area.horizontalScrollBar().value()
        scroll_right = scroll_value + viewport_width

        estimated_total_width = ESTIMATED_ITEM_WIDTH + SPACING
        if estimated_total_width <= 0:
            estimated_total_width = 1
        min_visible_count = max(
            15, int((viewport_width + estimated_total_width - 1) / estimated_total_width)
        )

        first_index = self._find_first_index(scroll_value)
        last_index = self._find_last_index(scroll_right)
        if last_index < first_index:
            return

        visible_start = first_index
        visible_end = last_index
        visible_count = visible_end - visible_start + 1
        if visible_count < min_visible_count:
            extra = min_visible_count - visible_count
            extend_right = min(extra, N - 1 - visible_end)
            visible_end += extend_right
            extra -= extend_right
            if extra > 0:
                visible_start = max(0, visible_start - extra)
            visible_count = visible_end - visible_start + 1

        load_start = max(0, visible_start - MARGIN)
        load_end = min(N - 1, visible_end + MARGIN)

        self._container.setFixedWidth(int(content_width))

        if load_start == self._load_start and load_end == self._load_end:
            self._update_placeholders(load_start, load_end, content_width)
            return

        self._update_placeholders(load_start, load_end, content_width)

        while self.shelf_layout.count() > 2:
            item = self.shelf_layout.takeAt(1)
            if item and item.widget():
                item.widget().deleteLater()

        for j in range(load_end - load_start + 1):
            idx = load_start + j
            work_id = self._work_ids[idx]
            try:
                card = get_workcardinfo_by_workid(work_id)
            except Exception:
                card = {}
            if card and "work_id" in card and "serial_number" in card:
                widget = ShelfItemWidget(card, self._container)
                widget._shelf_index = idx
                widget.installEventFilter(self)
                self.shelf_layout.insertWidget(
                    1 + j, widget, alignment=Qt.AlignmentFlag.AlignBottom
                )
            else:
                placeholder = QWidget(self._container)
                placeholder.setFixedWidth(SPINE_PLACEHOLDER_W)
                placeholder.setFixedHeight(1)
                placeholder.setStyleSheet("background: transparent;")
                self.shelf_layout.insertWidget(
                    1 + j, placeholder, alignment=Qt.AlignmentFlag.AlignBottom
                )

        self._load_start = load_start
        self._load_end = load_end

        updated_content_width = self._rebuild_offsets_and_content_width()
        self._container.setFixedWidth(int(updated_content_width))
        self._update_placeholders(load_start, load_end, updated_content_width)
