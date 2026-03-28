"""拖拽时覆盖整个工作区的透明层：统一做命中测试 (pane, zone)，驱动预览与 drop。"""

from typing import Callable

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QDragLeaveEvent

from ui.myads.pane_widget import PaneWidget, MIME_TYPE_TAB
from ui.myads.tab_drag_handler import hit_test, DropZone


def hit_test_global(
    get_panes: Callable[[], list[PaneWidget]],
    overlay: QWidget,
    global_pos: QPoint,
) -> tuple[PaneWidget | None, DropZone | None]:
    """
    根据全局坐标在 overlay 所在窗口内判断落入的 (pane, zone)。
    get_panes() 返回当前所有 PaneWidget；若有多个 pane 包含该点，取最后一个（视觉上更靠前）。
    """
    panes = get_panes()
    if not panes:
        return None, None
    pos_in_overlay = overlay.mapFromGlobal(global_pos)
    if not overlay.rect().contains(pos_in_overlay):
        return None, None
    found = None
    found_zone = None
    for pane in panes:
        if not pane.isVisible():
            continue
        # 点是否在该 pane 的几何范围内（overlay 与 pane 同属一个 window，用 global 中转）
        pos_in_pane = pane.mapFromGlobal(global_pos)
        if pane.rect().contains(pos_in_pane):
            zone = hit_test(pane.rect(), pos_in_pane)
            found = pane
            found_zone = zone
    return found, found_zone


class DragDropOverlay(QWidget):
    """
    覆盖整个 workspace 的透明层。平时 WA_TransparentForMouseEvents，不拦截事件；
    拖拽开始后 activate() 设为接收事件，在此层统一做命中测试并驱动预览与 drop。
    主要是为了拖动的时候拦截事件，不让其他干扰，实际上计算是否命中区域不用这个也可以做
    """

    def __init__(
        self,
        parent: QWidget,
        get_panes: Callable[[], list[PaneWidget]],
        preview_callback: Callable[[DropZone | None, PaneWidget | None], None] | None,
        execute_drop: Callable[[PaneWidget | None, DropZone | None, QDropEvent], bool],
    ):
        super().__init__(parent)
        self._get_panes = get_panes
        self._preview_callback = preview_callback
        self._execute_drop = execute_drop
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAcceptDrops(True)

    def activate(self) -> None:
        """开始接收拖放事件（在 Tab 开始拖拽时由外部调用）。"""
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.raise_()
        self.setGeometry(self.parent().rect())

    def deactivate(self) -> None:
        """停止接收拖放事件，恢复穿透。"""
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        if self._preview_callback:
            self._preview_callback(None, None)

    def _global_pos(self, event) -> QPoint:
        """从拖放事件取得全局坐标。"""
        if hasattr(event, "position"):
            return self.mapToGlobal(event.position().toPoint())
        if hasattr(event, "globalPos"):
            return event.globalPos()
        return QPoint(0, 0)

    def _hit(self, event) -> tuple[PaneWidget | None, DropZone | None]:
        return hit_test_global(self._get_panes, self, self._global_pos(event))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(MIME_TYPE_TAB):
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if not event.mimeData().hasFormat(MIME_TYPE_TAB):
            return
        pane, zone = self._hit(event)
        if self._preview_callback:
            self._preview_callback(zone, pane)
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        self.deactivate()
        if not event.mimeData().hasFormat(MIME_TYPE_TAB):
            return
        pane, zone = self._hit(event)
        self._execute_drop(pane, zone, event)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.deactivate()
