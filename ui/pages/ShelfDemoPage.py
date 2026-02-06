from typing import List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLayout,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
)

from ui.basic import HorizontalScrollArea

from core.database.query import get_work_ids_with_cover, get_workcardinfo_by_workid
from ui.widgets.ShelfItemWidget import ShelfItemWidget
import logging

# 虚拟化常量：用估算宽度计算可见区间，不固定槽位
ESTIMATED_ITEM_WIDTH = 60
SPACING = 16
MARGIN = 2
SHELF_MARGIN_LEFT = 16
SHELF_MARGIN_RIGHT = 16
SHELF_MARGIN_TOP = 16
SHELF_MARGIN_BOTTOM = 20


class ShelfDemoPage(QWidget):
    """
    拟物化书架 Demo 页面（视口虚拟化）

    - 只加载当前视口 + 左右缓冲范围内的项，自动加载/释放
    - 用估算宽度计算可见区间，不固定槽位宽度
    - 数据来自 get_work_ids_with_cover + 按需 get_workcardinfo_by_workid
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._work_ids: List[int] = []
        self._widths: List[float] = []
        self._offsets: List[float] = []
        self._load_start = -1
        self._load_end = -2
        self._updating_range = False
        self._init_ui()
        self._load_data()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        self.scroll_area = HorizontalScrollArea(self)
        self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.scroll_area.setMinimumHeight(600)
        # 关闭内容跟随视口弹性伸缩，由我们自行计算内容宽度
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self._container = QWidget()
        self._container.setMinimumHeight(600)
        self.shelf_layout = QHBoxLayout(self._container)
        # 使用固定的书架四周 margin 与中间固定间距，避免弹性布局
        self.shelf_layout.setContentsMargins(
            SHELF_MARGIN_LEFT, SHELF_MARGIN_TOP, SHELF_MARGIN_RIGHT, SHELF_MARGIN_BOTTOM
        )
        self.shelf_layout.setSpacing(SPACING)
        # 从左到右排列，并保持底对齐
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
        self.shelf_layout.addWidget(self._left_placeholder, alignment=Qt.AlignmentFlag.AlignBottom)
        self.shelf_layout.addWidget(self._right_placeholder, alignment=Qt.AlignmentFlag.AlignBottom)

        # 容器宽度由内容决定，不随视口弹性拉伸
        self._container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.scroll_area.setWidget(self._container)

        self.scroll_area.scrolled.connect(self._on_shelf_scrolled)
        self.scroll_area.horizontalScrollBar().valueChanged.connect(self._on_scroll_value_changed)
        self.scroll_area.viewport().installEventFilter(self)

        main_layout.addWidget(self.scroll_area)
        main_layout.addStretch()

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self.scroll_area.viewport() and event.type() == QEvent.Type.Resize:
            self._update_visible_range()
        elif isinstance(obj, ShelfItemWidget) and event.type() == QEvent.Type.Resize:
            # 图片异步加载完成后 widget 宽度变化，动态更新 _widths 并刷新内容宽度
            idx = getattr(obj, '_shelf_index', -1)
            if 0 <= idx < len(self._widths):
                new_w = float(obj.width())
                if new_w > 0 and abs(self._widths[idx] - new_w) > 1.0:
                    self._widths[idx] = new_w
                    self._refresh_content_width()
        return super().eventFilter(obj, event)

    def _on_scroll_value_changed(self, _value: int) -> None:
        self._update_visible_range()
        self._on_shelf_scrolled(self.scroll_area.horizontalScrollBar().value())

    def _on_shelf_scrolled(self, scroll_value: int) -> None:
        """仅对当前已存在的 ShelfItemWidget 重新检查鼠标位置"""
        for i in range(self.shelf_layout.count()):
            item = self.shelf_layout.itemAt(i)
            if item is None:
                continue
            w = item.widget()
            if w and isinstance(w, ShelfItemWidget):
                w.check_mouse_position_on_scroll()

    def _rebuild_offsets_and_content_width(self) -> float:
        """
        根据当前的 self._widths 重建前缀和 self._offsets，并返回内容总宽度。
        """
        N = len(self._widths)
        if N == 0:
            self._offsets = []
            return 0.0

        # 第 0 本书从左侧 margin 之后开始排布
        offsets: List[float] = [0.0] * N
        offsets[0] = float(SHELF_MARGIN_LEFT)
        for i in range(1, N):
            prev_width = max(self._widths[i - 1], float(ESTIMATED_ITEM_WIDTH))
            offsets[i] = offsets[i - 1] + prev_width + SPACING

        self._offsets = offsets
        last_width = max(self._widths[N - 1], float(ESTIMATED_ITEM_WIDTH))
        # 内容总宽度 = 所有书本宽度 + 固定间距 + 左右 margin
        content_width = offsets[N - 1] + last_width + float(SHELF_MARGIN_RIGHT)
        return content_width

    def _find_first_index(self, scroll_value: float) -> int:
        """
        在 [0, N) 中二分查找第一个满足
        offsets[i] + widths[i] > scroll_value 的索引。
        若不存在则返回 N。
        """
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
        """
        在 [0, N) 中二分查找最后一个满足
        offsets[i] < scroll_right 的索引。
        若不存在则返回 -1。
        """
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
        """当 ShelfItemWidget 图片加载后宽度变化时，重新计算内容总宽度并更新容器。"""
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

    def _update_placeholders(self, load_start: int, load_end: int, content_width: float) -> None:
        """
        更新左右占位控件的宽度和可见性。
        占位控件代表未加载区域的空间；需要减去一个 SPACING 来补偿布局自动
        在占位控件与相邻书本之间添加的间距，避免双重计算。
        当占位控件不需要时（即加载范围已覆盖到边界），将其隐藏以不占空间。
        """
        N = len(self._work_ids)
        # 左占位：代表 [0, load_start) 范围内未加载项的空间
        if load_start > 0:
            left_w = max(0, int(self._offsets[load_start] - float(SHELF_MARGIN_LEFT)) - SPACING)
            self._left_placeholder.setFixedWidth(left_w)
            self._left_placeholder.show()
        else:
            self._left_placeholder.setFixedWidth(0)
            self._left_placeholder.hide()
        # 右占位：代表 (load_end, N-1] 范围内未加载项的空间
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
        """防止重入的入口：设置容器宽度等操作会触发 scrollbar valueChanged，
        该信号又会回调本方法，因此需要用 _updating_range 标记防止无限递归。"""
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

        # 基于估算宽度计算「一屏」大致能放多少本书，至少 15 本
        estimated_total_width = ESTIMATED_ITEM_WIDTH + SPACING
        if estimated_total_width <= 0:
            estimated_total_width = 1
        min_visible_count = max(
            15, int((viewport_width + estimated_total_width - 1) / estimated_total_width)
        )

        # 使用前缀和 + 二分查找计算当前视口实际可见区间
        first_index = self._find_first_index(scroll_value)
        last_index = self._find_last_index(scroll_right)
        if last_index < first_index:
            return

        # 如果实际可见数量少于一屏的最小数量，则向左右扩展索引
        visible_start = first_index
        visible_end = last_index
        visible_count = visible_end - visible_start + 1
        if visible_count < min_visible_count:
            extra = min_visible_count - visible_count
            # 优先向右扩展
            extend_right = min(extra, N - 1 - visible_end)
            visible_end += extend_right
            extra -= extend_right
            # 不够再向左扩展
            if extra > 0:
                visible_start = max(0, visible_start - extra)
            visible_count = visible_end - visible_start + 1

        load_start = max(0, visible_start - MARGIN)
        load_end = min(N - 1, visible_end + MARGIN)

        # 固定容器宽度为我们计算的内容宽度，确保滚动条范围与内容一致
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
            image_url = card.get("image_url") if card else None
            if image_url:
                widget = ShelfItemWidget(card, self._container)
                # 记录索引，用于 eventFilter 中图片加载后动态更新 _widths
                widget._shelf_index = idx
                widget.installEventFilter(self)
                self.shelf_layout.insertWidget(
                    1 + j, widget, alignment=Qt.AlignmentFlag.AlignBottom
                )
            else:
                placeholder = QWidget(self._container)
                placeholder.setFixedWidth(ESTIMATED_ITEM_WIDTH)
                placeholder.setFixedHeight(1)
                placeholder.setStyleSheet("background: transparent;")
                self.shelf_layout.insertWidget(
                    1 + j, placeholder, alignment=Qt.AlignmentFlag.AlignBottom
                )

        self._load_start = load_start
        self._load_end = load_end

        # 重建偏移量并更新容器宽度和占位
        updated_content_width = self._rebuild_offsets_and_content_width()
        self._container.setFixedWidth(int(updated_content_width))
        self._update_placeholders(load_start, load_end, updated_content_width)

    def _load_data(self) -> None:
        self._work_ids = get_work_ids_with_cover(50)
        N = len(self._work_ids)
        self._widths = [float(ESTIMATED_ITEM_WIDTH)] * N
        self._offsets = [0.0] * N if N > 0 else []
        self._load_start = -1
        self._load_end = -2
        self._update_visible_range()
