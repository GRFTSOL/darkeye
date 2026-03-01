from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QFrame,
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
            import logging
            logging.error(f"Dashboard 数据库查询失败: {e}")
            self.signals.finished.emit(None)


class DashboardPage(QWidget):
    """
    首页 Dashboard

    结构按信息密度从粗到细划分为 3 个区域：
    1. 顶部统计卡片
    2. 最近行为
    3. 待处理 / 异常提醒

    数据库概览通过 get_dashboard_stats 异步加载，并监听全局信号自动刷新。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # ① 顶部统计卡片
        self.top_stats_container = self._build_top_stats_section()
        main_layout.addWidget(self.top_stats_container)

        # ② 最近行为：左右两栏
        self.recent_container = self._build_recent_section()
        main_layout.addWidget(self.recent_container)

        # ③ 待处理提醒
        self.pending_container = self._build_pending_section()
        main_layout.addWidget(self.pending_container)

        # 占满剩余空间
        main_layout.addStretch()

        # 连接全局信号，数据变更时刷新统计
        global_signals.work_data_changed.connect(self._refresh_stats)
        global_signals.actress_data_changed.connect(self._refresh_stats)
        global_signals.actor_data_changed.connect(self._refresh_stats)
        global_signals.tag_data_changed.connect(self._refresh_stats)
        global_signals.like_work_changed.connect(self._refresh_stats)
        global_signals.like_actress_changed.connect(self._refresh_stats)

        # 初始异步加载
        self._refresh_stats()

    # --------------------------------------
    # ① 顶部统计卡片
    # --------------------------------------
    def _build_top_stats_section(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = Label("数据库概览")
        title.setObjectName("dashboard_section_title")
        layout.addWidget(title)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)

        self._stat_value_labels: dict[str, Label] = {}
        for label_text, key in _STAT_CARD_KEYS:
            card, value_label = self._create_stat_card(label_text, "--")
            cards_row.addWidget(card)
            self._stat_value_labels[key] = value_label

        cards_row.addStretch()
        layout.addLayout(cards_row)
        return container

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

    # --------------------------------------
    # ② 最近行为
    # --------------------------------------
    def _build_recent_section(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = Label("最近行为")
        title.setObjectName("dashboard_section_title")
        layout.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(16)

        # 左：最近观看 / 最近标记
        recent_view_widget = QWidget()
        recent_view_layout = QVBoxLayout(recent_view_widget)
        recent_view_layout.setContentsMargins(0, 0, 0, 0)
        recent_view_layout.setSpacing(4)

        recent_view_title = Label("最近观看 / 最近标记")
        recent_view_layout.addWidget(recent_view_title)

        self.recent_view_list = QListWidget()
        self.recent_view_list.setMaximumHeight(200)
        recent_view_layout.addWidget(self.recent_view_list)

        # 右：最近新增作品 / 新增女优
        recent_new_widget = QWidget()
        recent_new_layout = QVBoxLayout(recent_new_widget)
        recent_new_layout.setContentsMargins(0, 0, 0, 0)
        recent_new_layout.setSpacing(4)

        recent_new_title = Label("最近新增")
        recent_new_layout.addWidget(recent_new_title)

        self.recent_added_list = QListWidget()
        self.recent_added_list.setMaximumHeight(200)
        recent_new_layout.addWidget(self.recent_added_list)

        row.addWidget(recent_view_widget, 1)
        row.addWidget(recent_new_widget, 1)

        layout.addLayout(row)

        # 占位数据，后续用真实查询替换
        for text in [
            "（占位）最近看过的一部作品",
            "（占位）最近看过的另一部作品",
        ]:
            QListWidgetItem(text, self.recent_view_list)

        for text in [
            "（占位）最近新增作品",
            "（占位）最近新增女优",
        ]:
            QListWidgetItem(text, self.recent_added_list)

        return container

    # --------------------------------------
    # ③ 待处理 / 异常提醒
    # --------------------------------------
    def _build_pending_section(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = Label("待处理事项")
        title.setObjectName("dashboard_section_title")
        layout.addWidget(title)

        self.pending_list = QListWidget()
        self.pending_list.setMaximumHeight(140)
        layout.addWidget(self.pending_list)

        # 占位提示
        for text in [
            "（占位）12 部作品没有封面",
            "（占位）8 部作品未绑定女优",
        ]:
            QListWidgetItem(text, self.pending_list)

        return container
