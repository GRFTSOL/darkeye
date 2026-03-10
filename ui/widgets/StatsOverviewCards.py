"""
数据库概览统计卡片组件。展示作品、女优、男优、Tag 等数量统计，
通过 get_dashboard_stats 异步加载，监听全局信号自动刷新。
"""

import logging

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QThreadPool, QRunnable, QObject, Signal, Slot

from darkeye_ui.components.label import Label
from controller.GlobalSignalBus import global_signals
from core.database.query import get_dashboard_stats


# 统计卡片 label -> get_dashboard_stats 返回的键
_STAT_CARD_KEYS = [
    ("作品总数", "work_count"),
    ("女优总数", "actress_count"),
    ("男优总数", "actor_count"),
    ("Tag总数", "tag_count"),
    ("近30天新增作品", "recent_30_days"),
    ("收藏作品总数", "favorite_work_count"),
    ("收藏女优总数", "favorite_actress_count"),
]


class _WorkerSignals(QObject):
    finished = Signal(object)


class _DatabaseQueryWorker(QRunnable):
    def __init__(self, query_func, *args, **kwargs):
        super().__init__()
        self.query_func = query_func
        self.args = args
        self.kwargs = kwargs
        self.signals = _WorkerSignals()

    def run(self):
        try:
            result = self.query_func(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            logging.error(f"StatsOverviewCards 数据库查询失败: {e}")
            self.signals.finished.emit(None)


class StatsOverviewCards(QWidget):
    """
    数据库概览统计卡片。展示 7 个指标，异步加载并监听全局信号自动刷新。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)

        self._stat_value_labels: dict[str, Label] = {}

        # 左右各一个弹性空间，使卡片整体居中
        cards_row.addStretch()
        for label_text, key in _STAT_CARD_KEYS:
            card, value_label = self._create_stat_card(label_text, "--")
            cards_row.addWidget(card)
            self._stat_value_labels[key] = value_label

        cards_row.addStretch()
        layout.addLayout(cards_row)

        # 连接全局信号，数据变更时刷新统计
        global_signals.work_data_changed.connect(self._refresh_stats)
        global_signals.actress_data_changed.connect(self._refresh_stats)
        global_signals.actor_data_changed.connect(self._refresh_stats)
        global_signals.tag_data_changed.connect(self._refresh_stats)
        global_signals.like_work_changed.connect(self._refresh_stats)
        global_signals.like_actress_changed.connect(self._refresh_stats)

        # 初始异步加载
        self._refresh_stats()

    def _create_stat_card(self, label: str, value: str) -> tuple[QWidget, Label]:
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        v = QVBoxLayout(card)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(4)

        value_label = Label(value)
        value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        value_label.setStyleSheet("font-size: 20px; font-weight: bold;")

        desc_label = Label(label)
        desc_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        desc_label.setStyleSheet("color: gray;")

        v.addWidget(value_label)
        v.addWidget(desc_label)

        return card, value_label

    @Slot()
    def _refresh_stats(self) -> None:
        worker = _DatabaseQueryWorker(get_dashboard_stats)
        worker.signals.finished.connect(self._on_stats_loaded)
        QThreadPool.globalInstance().start(worker)

    @Slot(object)
    def _on_stats_loaded(self, data: dict | None) -> None:
        if data is None:
            return
        for key, value_label in self._stat_value_labels.items():
            val = data.get(key, "--")
            value_label.setText(str(val))
