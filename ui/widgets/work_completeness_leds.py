"""爬虫任务 Inbox：15 维库内完整度红/绿灯条（与 WORK_COMPLETENESS_KEYS 顺序一致）。"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QHelpEvent, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from core.database.query.work_completeness import (
    WORK_COMPLETENESS_KEYS,
    WORK_COMPLETENESS_LABELS_ZH,
)


class WorkCompletenessLedStrip(QWidget):
    """横向 15 个小方块；``completeness`` 为 ``None`` 时表示尚未检测（灰色）。"""

    def __init__(
        self,
        completeness: dict[str, bool] | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        for i, key in enumerate(WORK_COMPLETENESS_KEYS):
            label_zh = WORK_COMPLETENESS_LABELS_ZH[i]
            # 比方块略大的热区，便于触发 tooltip；整体尽量紧凑
            cell = QWidget(self)
            cell.setFixedSize(14, 14)
            cell.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            cell.setCursor(Qt.CursorShape.PointingHandCursor)
            outer = QVBoxLayout(cell)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(0)
            outer.addStretch(1)
            inner = QHBoxLayout()
            inner.setContentsMargins(0, 0, 0, 0)
            inner.setSpacing(0)
            inner.addStretch(1)

            dot = QFrame(cell)
            dot.setFixedSize(10, 10)
            # 子控件默认箭头光标会盖住父级手型，鼠标在边缘与方块间会闪；穿透给 cell 统一光标/tooltip
            dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            if completeness is None:
                dot.setStyleSheet("QFrame { background-color: #888888; border-radius: 0; }")
                cell.setToolTip(f"{label_zh}\n（库内完整度）未检测")
            elif completeness.get(key):
                dot.setStyleSheet("QFrame { background-color: #27ae60; border-radius: 0; }")
                cell.setToolTip(f"{label_zh}\n（库内完整度）已有")
            else:
                dot.setStyleSheet("QFrame { background-color: #c0392b; border-radius: 0; }")
                cell.setToolTip(f"{label_zh}\n（库内完整度）暂无")

            inner.addWidget(dot)
            inner.addStretch(1)
            outer.addLayout(inner)
            outer.addStretch(1)
            layout.addWidget(cell)


class WorkCompletenessBitsDelegate(QStyledItemDelegate):
    """按 15 位 bit 串绘制完整度方格，顺序与 WORK_COMPLETENESS_KEYS 一致。"""

    _UNKNOWN_COLOR = QColor("#888888")
    _OK_COLOR = QColor("#27ae60")
    _MISS_COLOR = QColor("#c0392b")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bits_len = len(WORK_COMPLETENESS_KEYS)
        self._cell_size = 10
        self._cell_gap = 1

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index,
    ) -> None:
        bits = self._normalize_bits(index.data(Qt.ItemDataRole.DisplayRole))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        total_width = self._bits_len * self._cell_size + (self._bits_len - 1) * self._cell_gap
        start_x = option.rect.x() + max(0, (option.rect.width() - total_width) // 2)
        start_y = option.rect.y() + max(0, (option.rect.height() - self._cell_size) // 2)

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        for i, bit in enumerate(bits):
            x = start_x + i * (self._cell_size + self._cell_gap)
            color = self._UNKNOWN_COLOR
            if bit == "1":
                color = self._OK_COLOR
            elif bit == "0":
                color = self._MISS_COLOR
            painter.fillRect(QRect(x, start_y, self._cell_size, self._cell_size), color)

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        total_width = self._bits_len * self._cell_size + (self._bits_len - 1) * self._cell_gap
        return QSize(total_width + 6, max(option.fontMetrics.height() + 2, self._cell_size + 4))

    def helpEvent(
        self,
        event,
        view,
        option: QStyleOptionViewItem,
        index,
    ) -> bool:
        if isinstance(event, QHelpEvent):
            bits = self._normalize_bits(index.data(Qt.ItemDataRole.DisplayRole))
            tooltip = self._build_tooltip(bits)
            QToolTip.showText(event.globalPos(), tooltip, view)
            return True
        return super().helpEvent(event, view, option, index)

    def _normalize_bits(self, value: object) -> str:
        text = "" if value is None else str(value).strip()
        if len(text) == self._bits_len and all(ch in ("0", "1") for ch in text):
            return text
        return "?" * self._bits_len

    def _build_tooltip(self, bits: str) -> str:
        if "?" in bits:
            return "库内完整度\n未检测"

        miss = [
            WORK_COMPLETENESS_LABELS_ZH[i]
            for i, ch in enumerate(bits)
            if ch == "0"
        ]
        score = bits.count("1")
        if not miss:
            return f"库内完整度 {score}/{self._bits_len}\n信息完整"
        return f"库内完整度 {score}/{self._bits_len}\n缺：{'、'.join(miss)}"
