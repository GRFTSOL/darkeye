from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QFrame,
)
from PySide6.QtCore import Qt

from ui.navigation.router import Router
from darkeye_ui.components.label import Label

class DashboardPage(QWidget):
    """
    首页 Dashboard

    结构按信息密度从粗到细划分为 5 个区域：
    1. 顶部统计卡片
    2. 最近行为
    3. 偏好 / Top 榜
    4. 待处理 / 异常提醒
    5. 快捷入口

    当前版本先搭好布局和交互骨架，数据后续通过 query.py 补充。
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

        # ③ 偏好 / Top 榜
        self.preferences_container = self._build_preferences_section()
        main_layout.addWidget(self.preferences_container)

        # ④ 待处理提醒
        self.pending_container = self._build_pending_section()
        main_layout.addWidget(self.pending_container)

        # ⑤ 快捷入口
        self.shortcuts_container = self._build_shortcuts_section()
        main_layout.addWidget(self.shortcuts_container)

        # 占满剩余空间
        main_layout.addStretch()

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

        # 先用占位数据，后续用 query.py 填充真实数值
        for label_text in ["作品总数", "女优总数", "代表作数量", "近30天新增作品"]:
            card = self._create_stat_card(label_text, "--")
            cards_row.addWidget(card)

        cards_row.addStretch()
        layout.addLayout(cards_row)
        return container

    def _create_stat_card(self, label: str, value: str) -> QWidget:
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

        return card

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
    # ③ 偏好 / Top 榜
    # --------------------------------------
    def _build_preferences_section(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = Label("偏好统计 / Top 榜（基础版）")
        title.setObjectName("dashboard_section_title")
        layout.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(16)

        self.top_actress_list = QListWidget()
        self.top_studio_list = QListWidget()

        self.top_actress_list.setMaximumHeight(160)
        self.top_studio_list.setMaximumHeight(160)

        row.addWidget(self._wrap_list_with_title(self.top_actress_list, "出现次数最多的女优 Top 5"), 1)
        row.addWidget(self._wrap_list_with_title(self.top_studio_list, "出现次数最多的厂牌 Top 5"), 1)

        layout.addLayout(row)

        # 占位数据
        for i in range(1, 4):
            QListWidgetItem(f"（占位）女优 Top {i}", self.top_actress_list)
            QListWidgetItem(f"（占位）厂牌 Top {i}", self.top_studio_list)

        return container

    def _wrap_list_with_title(self, list_widget: QListWidget, title: str) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        v.addWidget(Label(title))
        v.addWidget(list_widget)
        return w

    # --------------------------------------
    # ④ 待处理 / 异常提醒
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
            "（占位）3 位女优没有代表作",
        ]:
            QListWidgetItem(text, self.pending_list)

        return container

    # --------------------------------------
    # ⑤ 快捷入口
    # --------------------------------------
    def _build_shortcuts_section(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = Label("快捷操作")
        title.setObjectName("dashboard_section_title")
        layout.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(8)

        def add_button(text: str, callback) -> None:
            btn = QPushButton(text)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            btn.clicked.connect(callback)
            row.addWidget(btn)

        add_button("新增作品", self._goto_add_work)
        add_button("新增女优", self._goto_add_actress)
        add_button("打开统计页", self._goto_statistics)
        add_button("作品高级搜索", self._goto_works)
        add_button("随机推荐一部", self._goto_random_recommend)

        row.addStretch()
        layout.addLayout(row)

        return container

    # --------------------------------------
    # 快捷操作路由
    # --------------------------------------
    def _goto_add_work(self) -> None:
        # 这里暂时跳到管理页的作品 Tab，具体 tab 切换由 ManagementPage 处理
        Router.instance().push("database")

    def _goto_add_actress(self) -> None:
        Router.instance().push("actress")

    def _goto_statistics(self) -> None:
        Router.instance().push("chart")

    def _goto_works(self) -> None:
        Router.instance().push("mutiwork")

    def _goto_random_recommend(self) -> None:
        # 先复用原首页逻辑：随机推荐 + 作品列表
        from ui.pages.CoverBrowser import CoverBrowser
        from core.recommendation.Recommend import randomRec

        # 直接用 CoverBrowser 打开一次随机推荐页面
        # 更精细的“单一作品推荐”可以后续改为跳 SingleWorkPage
        browser = CoverBrowser(randomRec())
        browser.setWindowModality(Qt.ApplicationModal)
        browser.setWindowTitle("随机推荐")
        browser.resize(800, 600)
        browser.show()

