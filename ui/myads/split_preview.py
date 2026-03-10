"""阶段四：拆分预览图层（QRubberBand）。"""

from PySide6.QtWidgets import QWidget, QRubberBand
from PySide6.QtCore import Qt, QRect

from ui.myads.pane_widget import PaneWidget
from ui.myads.tab_drag_handler import DropZone


class SplitPreviewOverlay(QWidget):
    """叠加在 WorkspaceWidget 上的透明层，用于显示拖拽时的拆分预览矩形。"""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._rubber_band: QRubberBand | None = None
        self._zone: DropZone | None = None
        self._target_pane: PaneWidget | None = None

    def show_preview(self, zone: DropZone | None, target_pane: PaneWidget | None) -> None:
        """显示预览。zone 为 None 时隐藏。"""
        self._zone = zone
        self._target_pane = target_pane
        if self._rubber_band:
            self._rubber_band.hide()
            self._rubber_band.deleteLater()
            self._rubber_band = None

        if zone is None or target_pane is None:
            self.update()
            return

        rect = self._preview_rect(zone, target_pane)
        if rect.isValid():
            # 使用 mapToGlobal/mapFromGlobal 避免 parent hierarchy 要求
            global_pos = target_pane.mapToGlobal(rect.topLeft())
            top_left = self.mapFromGlobal(global_pos)
            self._rubber_band = QRubberBand(QRubberBand.Rectangle, self)
            self._rubber_band.setGeometry(QRect(top_left, rect.size()))
            self._rubber_band.setStyleSheet("background-color: rgba(0, 170, 255, 80); border: 2px solid #00aaff;")
            self._rubber_band.show()
        self.update()

    def _preview_rect(self, zone: DropZone, pane: PaneWidget) -> QRect:
        """计算预览矩形（相对于 pane 的坐标）。"""
        r = pane.rect()
        w, h = r.width(), r.height()
        if w <= 0 or h <= 0:
            return QRect()

        if zone == DropZone.TOP:
            return QRect(0, 0, w, int(h * 0.5))
        if zone == DropZone.BOTTOM:
            return QRect(0, int(h * 0.5), w, int(h * 0.5))
        if zone == DropZone.LEFT:
            return QRect(0, 0, int(w * 0.5), h)
        if zone == DropZone.RIGHT:
            return QRect(int(w * 0.5), 0, int(w * 0.5), h)
        if zone == DropZone.CENTER:
            # 高亮整个 pane 边框
            return r

        return QRect()
