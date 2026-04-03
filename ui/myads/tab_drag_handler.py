"""阶段三：Tab 拖拽逻辑与几何计算（DND）。"""

from enum import Enum
from typing import Callable

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QDropEvent

from ui.myads.pane_widget import PaneWidget, MIME_TYPE_TAB


class DropZone(Enum):
    """拖放目标区域。与 _preview_rect 一致：边缘 50% 为拆分区，中心 50%×50% 为合并。"""

    TOP = "top"  # 上半 → 上方拆分
    BOTTOM = "bottom"  # 下半 → 下方拆分
    LEFT = "left"  # 左半 → 左侧拆分
    RIGHT = "right"  # 右半 → 右侧拆分
    CENTER = "center"  # 中间 50%×50% → 合并到当前窗格


def hit_test(pane_rect, pos: QPoint) -> DropZone:
    """根据 Pane 内相对位置计算落入的区域。与 split_preview._preview_rect 一致：中心 50%×50% 为合并，上下左右各 25% 边带为拆分区。"""
    x = pos.x()
    y = pos.y()
    w = pane_rect.width()
    h = pane_rect.height()
    if w <= 0 or h <= 0:
        return DropZone.CENTER

    xf = x / w
    yf = y / h
    # 中心 50%×50% → 合并到当前窗格
    if 0.25 <= xf <= 0.75 and 0.25 <= yf <= 0.75:
        return DropZone.CENTER
    if yf < 0.25:
        return DropZone.TOP
    if yf >= 0.75:
        return DropZone.BOTTOM
    if xf < 0.25:
        return DropZone.LEFT
    if xf >= 0.75:
        return DropZone.RIGHT
    return DropZone.CENTER


def execute_drop_action(
    layout_tree: object,
    new_pane_factory: Callable[[], PaneWidget],
    find_pane_by_id: Callable[[str], PaneWidget | None],
    on_new_pane: Callable[[PaneWidget], None] | None,
    pane: PaneWidget | None,
    zone: DropZone | None,
    event: QDropEvent,
    ratio: float = 0.5,
) -> bool:
    """
    在已知 (pane, zone) 时执行合并/拆分。供 overlay 调用。
    pane 为 None 或 zone 为 None 时返回 False。
    """
    if pane is None or zone is None:
        return False
    if not event.mimeData().hasFormat(MIME_TYPE_TAB):
        return False
    data = bytes(event.mimeData().data(MIME_TYPE_TAB)).decode("utf-8")
    parts = data.strip().split("\n")
    if len(parts) < 3:
        return False
    content_id, source_pane_id, title = parts[0], parts[1], parts[2]
    source_pane: PaneWidget = find_pane_by_id(source_pane_id)
    if not source_pane:
        return False
    if zone == DropZone.CENTER and source_pane == pane:
        return False
    widget = source_pane.get_content_widget(content_id)
    if not widget:
        return False
    icon = source_pane.get_icon_for_content(content_id)
    if zone == DropZone.CENTER:
        source_pane.remove_content(content_id)
        pane.add_content(content_id, title, widget, icon=icon)
    else:
        new_pane = new_pane_factory()
        orientation = (
            Qt.Horizontal if zone in (DropZone.LEFT, DropZone.RIGHT) else Qt.Vertical
        )
        insert_before = zone in (DropZone.TOP, DropZone.LEFT)
        layout_tree.split(pane, orientation, insert_before, new_pane, ratio=ratio)
        if on_new_pane:
            on_new_pane(new_pane)
        new_pane.add_content(content_id, title, widget, icon=icon)
        source_pane.remove_content(content_id)
    event.acceptProposedAction()
    return True
