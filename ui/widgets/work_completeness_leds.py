"""爬虫任务 Inbox：15 维库内完整度红/绿灯条（与 WORK_COMPLETENESS_KEYS 顺序一致）。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

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
