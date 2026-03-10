from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
)

from darkeye_ui.components.label import Label
from ui.widgets.StatsOverviewCards import StatsOverviewCards


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
        main_layout.addWidget(StatsOverviewCards())

        # ② 最近行为：左右两栏
        self.recent_container = self._build_recent_section()
        main_layout.addWidget(self.recent_container)

        # ③ 待处理提醒
        self.pending_container = self._build_pending_section()
        main_layout.addWidget(self.pending_container)

        # 占满剩余空间
        main_layout.addStretch()

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
