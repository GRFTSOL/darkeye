from PySide6.QtWidgets import (
    QHBoxLayout,
    QWidget,
    QVBoxLayout,
    QStackedWidget,
    QScrollArea,
    QButtonGroup,
)

from PySide6.QtCore import Qt, Signal, Slot, QThreadPool, QRunnable, QObject
from darkeye_ui.components import CalendarHeatmap
from core.database.query import get_record_count_by_year, get_record_by_year

from darkeye_ui.components.label import Label
from darkeye_ui.components.icon_push_button import IconPushButton
from darkeye_ui.components.button import Button


class DatabaseQueryWorker(QRunnable):
    """数据库查询工作线程"""

    def __init__(self, query_func, *args, **kwargs):
        super().__init__()
        self.query_func = query_func
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.query_func(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            import logging

            logging.error(f"数据库查询失败: {e}")
            self.signals.finished.emit(None)


class WorkerSignals(QObject):
    """工作线程信号"""

    finished = Signal(object)


class SwitchHeapMap(QWidget):
    def __init__(self):
        super().__init__()
        self.thread_pool = QThreadPool.globalInstance()
        self.current_year = None
        self.heatmap_data_cache = {}  # 缓存每年的数据

        from core.database.query import get_record_early_year
        from datetime import datetime

        early_year = get_record_early_year()
        if not early_year:
            early_year = int(datetime.now().year)
        # 年份列表,从有记录的最早的年份开始，到当前年份结束
        year_list = [str(x) for x in list(range(early_year, datetime.now().year + 1))]
        year_list = year_list[::-1]
        # year_list=[str(x) for x in list(range(2018,2026))]
        self.buttonlist = ButtonList(year_list)
        self.buttonlist.setFixedHeight(200)
        # 左右切换按钮
        self.btn_prev = IconPushButton(icon_name="arrow_up")
        self.btn_next = IconPushButton(icon_name="arrow_down")

        today_year = datetime.today().year  # 获取当前年份
        self.current_year = today_year
        # 绑定按钮点击
        self.btn_prev.clicked.connect(lambda: self.switch(-1))
        self.btn_next.clicked.connect(lambda: self.switch(1))

        # 先显示占位UI
        self.placeholder_widget = Label("加载中...")
        self.placeholder_widget.setAlignment(Qt.AlignCenter)
        self.placeholder_widget.setStyleSheet(
            "font-size: 16px; color: #999999; padding: 50px;"
        )
        self.placeholder_widget.setFixedSize(750, 155)

        # 三个示例 QWidget - 先创建空的热力图
        self.calendar_heatmap_masturbation = CalendarHeatmap(year=today_year, data={})
        self.calendar_heatmap_sex = CalendarHeatmap(year=today_year, data={})
        self.calendar_heatmap_arousal = CalendarHeatmap(year=today_year, data={})

        # QStackedWidget 管理多个 QWidget
        self.stack = QStackedWidget()
        self.stack.addWidget(self.calendar_heatmap_masturbation)
        self.stack.addWidget(self.calendar_heatmap_sex)
        self.stack.addWidget(self.calendar_heatmap_arousal)

        # 初始显示加载占位符
        self.heatmap_names = ["加载中...", "加载中...", "加载中..."]
        self.heatmap_name = Label(self.heatmap_names[0])
        # 布局
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.heatmap_name)
        btn_layout.addWidget(self.btn_prev)
        btn_layout.addWidget(self.btn_next)

        left_layout = QVBoxLayout()

        left_layout.addLayout(btn_layout)

        # 使用 QStackedWidget 来切换占位符和热力图
        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self.placeholder_widget)
        self.content_stack.addWidget(self.stack)
        self.content_stack.setCurrentWidget(self.placeholder_widget)

        left_layout.addWidget(self.content_stack)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addLayout(left_layout)
        main_layout.addWidget(self.buttonlist)

        self.buttonlist.switch_year.connect(self.update)

        # 异步加载初始数据
        self._load_initial_data(today_year)

    def _load_initial_data(self, year):
        """异步加载初始年份数据"""
        self.current_year = year

        # 加载统计数据
        count_worker = DatabaseQueryWorker(self._load_counts, year)
        count_worker.signals.finished.connect(self._on_counts_loaded)
        self.thread_pool.start(count_worker)

        # 加载热力图数据
        heatmap_worker = DatabaseQueryWorker(self._load_heatmaps, year)
        heatmap_worker.signals.finished.connect(self._on_heatmaps_loaded)
        self.thread_pool.start(heatmap_worker)

    def _load_counts(self, year):
        """加载统计数据"""
        return [
            get_record_count_by_year(year, 0),
            get_record_count_by_year(year, 1),
            get_record_count_by_year(year, 2),
        ]

    def _load_heatmaps(self, year):
        """加载热力图数据"""
        return [
            get_record_by_year(year, 0),
            get_record_by_year(year, 1),
            get_record_by_year(year, 2),
        ]

    def _on_counts_loaded(self, counts):
        """统计数据加载完成"""
        if counts:
            self.heatmap_names = [
                f"撸管{counts[0]}次在当年中",
                f"做爱{counts[1]}次在当年中",
                f"晨勃{counts[2]}次在当年中",
            ]
            index = self.stack.currentIndex()
            self.heatmap_name.setText(self.heatmap_names[index])

    def _on_heatmaps_loaded(self, heatmap_data):
        """热力图数据加载完成"""
        if heatmap_data:
            # 更新热力图数据
            self.calendar_heatmap_masturbation.update_data(
                self.current_year, heatmap_data[0]
            )
            self.calendar_heatmap_sex.update_data(self.current_year, heatmap_data[1])
            self.calendar_heatmap_arousal.update_data(
                self.current_year, heatmap_data[2]
            )

            # 缓存数据
            self.heatmap_data_cache[self.current_year] = heatmap_data

            # 切换到真实热力图显示
            self.content_stack.setCurrentWidget(self.stack)

    @Slot()
    def switch(self, step: int):
        """统一切换方法，step=-1 表示上一个，step=1 表示下一个"""
        index = (self.stack.currentIndex() + step) % self.stack.count()
        self.stack.setCurrentIndex(index)
        self.heatmap_name.setText(self.heatmap_names[index])

    @Slot(int)
    def update(self, year: int, force_refresh: bool = False):
        """根据年份去更新自身。force_refresh=True 时忽略缓存强制重新加载（用于数据变更后刷新）"""
        self.current_year = year

        # 显示加载状态
        self.heatmap_names = ["加载中...", "加载中...", "加载中..."]
        self.heatmap_name.setText(self.heatmap_names[self.stack.currentIndex()])
        self.content_stack.setCurrentWidget(self.placeholder_widget)

        # 数据变更后需强制刷新，不使用旧缓存
        if force_refresh and year in self.heatmap_data_cache:
            del self.heatmap_data_cache[year]

        # 检查缓存
        if year in self.heatmap_data_cache:
            # 使用缓存数据
            cached_data = self.heatmap_data_cache[year]
            self._update_with_data(year, cached_data)
        else:
            # 异步加载新数据
            self._load_year_data_async(year)

    def _load_year_data_async(self, year):
        """异步加载指定年份的数据"""
        self.current_year = year

        # 加载统计数据
        count_worker = DatabaseQueryWorker(self._load_counts, year)
        count_worker.signals.finished.connect(self._on_counts_loaded)
        self.thread_pool.start(count_worker)

        # 加载热力图数据
        heatmap_worker = DatabaseQueryWorker(self._load_heatmaps, year)
        heatmap_worker.signals.finished.connect(self._on_heatmaps_loaded)
        self.thread_pool.start(heatmap_worker)

    def _update_with_data(self, year, heatmap_data):
        """使用数据更新界面"""
        # 更新热力图数据
        self.calendar_heatmap_masturbation.update_data(year, heatmap_data[0])
        self.calendar_heatmap_sex.update_data(year, heatmap_data[1])
        self.calendar_heatmap_arousal.update_data(year, heatmap_data[2])

        # 异步加载统计数据
        count_worker = DatabaseQueryWorker(self._load_counts, year)
        count_worker.signals.finished.connect(self._on_counts_loaded)
        self.thread_pool.start(count_worker)

        # 切换到真实热力图显示
        self.content_stack.setCurrentWidget(self.stack)


class ButtonList(QScrollArea):
    switch_year = Signal(int)

    def __init__(self, items: list[str]):
        super().__init__()
        self.setWidgetResizable(True)  # 关键：内容自动适应
        self.setStyleSheet("""
            QScrollBar:vertical, QScrollBar:horizontal {
                width: 0px;
                height: 0px;
            }
        """)

        self.setFrameShape(QScrollArea.NoFrame)  # 去掉外框
        self.setAttribute(Qt.WA_TranslucentBackground)  # 支持透明

        # 滚动区里的实际内容容器，背景由这个决定
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.container.setAttribute(Qt.WA_TranslucentBackground)  # 这个透明很关键

        self.vbox = QVBoxLayout(self.container)
        self.vbox.setAlignment(Qt.AlignTop)  # 顶部对齐

        # 把滚动区
        self.setWidget(self.container)

        # 按钮组（保证单选）
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)  # 一次只能选一个
        self.group.idClicked.connect(self.on_button_clicked)

        # 初始化按钮
        self.populate(items)
        if self.group.buttons():
            first_btn = self.group.buttons()[0]
            first_btn.setChecked(True)
            self.on_button_clicked(self.group.id(first_btn))  # 手动触发

    def populate(self, items: list[str]):
        # 先清空旧内容（如果需要重复刷新）
        while self.vbox.count():
            item = self.vbox.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        for i, text in enumerate(items):
            btn = Button(text)
            btn.setFixedSize(100, 40)
            btn.setCheckable(True)  # 关键：可选中
            self.group.addButton(btn, i)
            self.vbox.addWidget(btn)
            # 应用现代样式

        # 撑开（保持紧凑但把多余空间留在底部）
        self.vbox.addStretch(1)

    def on_button_clicked(self, idx: int):
        self.switch_year.emit(int(self.group.button(idx).text()))
