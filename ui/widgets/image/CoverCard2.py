# 固定尺寸封面卡片：缩略图 120×81 异步加载，标题区固定高度；左右键在同列瀑布流中的 CoverCard2 之间切换焦点。

from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea
from PySide6.QtGui import QPainter, QColor, QKeyEvent
from PySide6.QtCore import Qt, Slot, QTimer, QEvent
from config import WORKCOVER_PATH
from pathlib import Path
import logging
from ui.widgets.text.ClickableLabel import ClickableLabel
from .CoverImage import CoverImageFixed
from utils.utils import replace_sensitive
from ui.navigation.router import Router
from darkeye_ui.components.label import Label

# 与 CoverImageFixed.FIXED_SIZE 一致；卡片总宽高固定
_IMG_W = 240
_IMG_H = 162
_MARGIN_H = 5
_MARGIN_TOP = 6
_MARGIN_BOTTOM = 8
_TITLE_H = 50
_SERIAL_H = 22
_CARD_W = _IMG_W + _MARGIN_H * 2
_CARD_H = _MARGIN_TOP + _SERIAL_H + _IMG_H + _TITLE_H + _MARGIN_BOTTOM

_TITLE_DISPLAY_MAX = 40


def _title_for_label(full: str | None, green: bool) -> str:
    t = (full or "")[:_TITLE_DISPLAY_MAX]
    return replace_sensitive(t) if green else t


class CoverCard2(QWidget):
    """与 `CoverCard` 相同构造参数；`LazyScrollArea` 请使用 `column_width=CoverCard2.CARD_WIDTH`。"""

    CARD_WIDTH = _CARD_W
    CARD_HEIGHT = _CARD_H

    def __init__(
        self,
        title: str,
        image_path: str,
        serial_number,
        work_id,
        standard: bool,
        color="#87CEEB",
        green_mode=False,
        parent=None,
    ):
        super().__init__(parent)
        self.setFixedSize(_CARD_W, _CARD_H)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.background_color = color
        self._work_id = work_id
        self.original_title = title
        self._green_mode = green_mode

        if image_path is None:
            self._path = None
        else:
            self._path = Path(WORKCOVER_PATH / image_path)

        self.image_label = CoverImageFixed(
            self._path, self._work_id, standard, green_mode
        )
        self.image_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.title_label = Label(_title_for_label(title, green_mode))
        self.title_label.setStyleSheet(
            """
            QLabel {
                font-size: 12px;
                font-family: 'Microsoft YaHei';
                font-weight: bold;
            }
        """
        )
        self.serial_number = serial_number
        self.serial_number_label = ClickableLabel(serial_number)
        self.serial_number_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.title_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.image_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setFixedWidth(_IMG_W)
        self.title_label.setFixedHeight(_TITLE_H)

        self.serial_number_label.setAlignment(Qt.AlignCenter)
        self.serial_number_label.setFixedHeight(_SERIAL_H)
        self.serial_number_label.setFixedWidth(_IMG_W)
        self.serial_number_label.setStyleSheet(
            """
            QLabel {
                font-size: 13px;
                font-family: 'Microsoft YaHei';
                font-weight: bold;
            }
        """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(_MARGIN_H, _MARGIN_TOP, _MARGIN_H, _MARGIN_BOTTOM)
        layout.setSpacing(4)
        layout.addWidget(self.serial_number_label, alignment=Qt.AlignCenter)
        layout.addWidget(self.image_label)
        layout.addWidget(self.title_label)

        for w in (self.image_label, self.title_label, self.serial_number_label):
            w.installEventFilter(self)

        self.signal_connect()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            self.setFocus()
        return False

    def signal_connect(self):
        self.image_label.jumpToModifyWork.connect(
            lambda: Router.instance().push(
                "work_edit", serial_number=self.serial_number
            )
        )
        from controller.global_signal_bus import global_signals

        global_signals.greenModeChanged.connect(self._update_green_mode)
        global_signals.workDataChanged.connect(self._update_card)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self._scroll_card_visible)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Left:
            self._focus_neighbor(-1)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Right:
            self._focus_neighbor(1)
            event.accept()
            return
        super().keyPressEvent(event)

    def _covercard2_siblings_in_layout_order(self):
        parent = self.parentWidget()
        if parent is None:
            return []
        lay = parent.layout()
        if lay is None:
            return []
        out = []
        for i in range(lay.count()):
            w = lay.itemAt(i).widget()
            if isinstance(w, CoverCard2):
                out.append(w)
        return out

    def _focus_neighbor(self, delta: int) -> None:
        cards = self._covercard2_siblings_in_layout_order()
        if self not in cards:
            return
        idx = cards.index(self) + delta
        if 0 <= idx < len(cards):
            cards[idx].setFocus()

    def _scroll_card_visible(self) -> None:
        p = self.parentWidget()
        while p is not None:
            if isinstance(p, QScrollArea):
                p.ensureWidgetVisible(self, 24, 24)
                break
            p = p.parentWidget()

    @Slot()
    def _update_card(self):
        try:
            from core.database.query import get_workcardinfo_by_workid

            data = get_workcardinfo_by_workid(self._work_id)
            if not data:
                return

            title = data.get("cn_title") or ""
            self.original_title = title
            self.title_label.setText(_title_for_label(title, self._green_mode))

            image_path = data.get("image_url")
            if image_path is None:
                self._path = None
            else:
                self._path = Path(WORKCOVER_PATH / image_path)
            self.image_label._path = self._path
            self.image_label._update_image()

            self.background_color = self.backgroundcolor_from_tagid(data.get("tag_id"))
            self.update()
        except Exception:
            logging.exception(
                "CoverCard2._update_card 执行失败: work_id=%s", self._work_id
            )

    @Slot(bool)
    def _update_green_mode(self, green_mode: bool):
        self._green_mode = green_mode
        self.title_label.setText(
            _title_for_label(self.original_title, self._green_mode)
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(self.background_color))
        painter.end()
        super().paintEvent(event)

    @staticmethod
    def backgroundcolor_from_tagid(tag_id: int | None) -> str:
        color_list = ["#80B0F8", "#ffa475", "#ffeb28"]
        match tag_id:
            case 1:
                return color_list[0]
            case 2:
                return color_list[1]
            case 3:
                return color_list[2]
            case None:
                return "#00000000"
