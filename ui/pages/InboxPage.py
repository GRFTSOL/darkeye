from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from PySide6.QtCore import Qt, Slot, QTimer, QStringListModel, QItemSelectionModel
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QAbstractItemView,
)

from controller.GlobalSignalBus import global_signals
from darkeye_ui.components import Button, Label, TokenListView


@dataclass
class DownloadTaskState:
    serial: str
    current: int = 0
    total: int = 0
    status_text: str = ""
    finished: bool = False
    success: bool = False
    started: bool = False  # 是否已经开始下载封面（用于列划分）
    in_queue: bool = False  # 是否还在 CrawlerManager 的待爬队列中
    crawling: bool = False  # 是否在 CrawlerManager 的 tasks 中（元数据爬取阶段）


class InboxPage(QWidget):
    """
    下载提示 Inbox 页面

    三列布局：左-待爬，中-正在爬，右-已完成。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._tasks: Dict[str, DownloadTaskState] = {}
        self._pending_serials: list[str] = []
        self._running_serials: list[str] = []
        self._finished_serials: list[str] = []
        # 被用户“清空已完成”隐藏掉的 serial（避免轮询时又被重建/塞回列表）
        self._dismissed_finished_serials: set[str] = set()
        self._models_dirty: bool = False

        self._init_ui()
        self._connect_signals()
        self._init_poll_timer()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(8)

        # 顶部标题区域
        header_layout = QHBoxLayout()
        

        add_button = Button("添加", variant="default")
        add_button.clicked.connect(self._add_task)
        header_layout.addWidget(add_button)

        delete_button = Button("删除", variant="default")
        delete_button.clicked.connect(self._delete_selected_pending)
        header_layout.addWidget(delete_button)
        header_layout.addStretch(1)

        self.pause_button = Button("中止", variant="default")
        self.pause_button.clicked.connect(self._pause_crawl)
        header_layout.addWidget(self.pause_button)

        self.resume_button = Button("继续", variant="default")
        self.resume_button.clicked.connect(self._resume_crawl)
        header_layout.addWidget(self.resume_button)

        clear_button = Button("清空已完成", variant="default")
        clear_button.clicked.connect(self._clear_finished)
        header_layout.addWidget(clear_button)

        root_layout.addLayout(header_layout)

        # 三列区域：待爬 / 正在爬 / 已完成
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(12)

        # 待爬
        pending_layout = QVBoxLayout()
        pending_layout.setContentsMargins(0, 0, 0, 0)
        pending_layout.setSpacing(8)
        self.pending_label = Label("待爬 (0)")
        pending_layout.addWidget(self.pending_label)
        self._pending_model = QStringListModel(self)
        self.pending_list = TokenListView(self)
        self.pending_list.setModel(self._pending_model)
        self.pending_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.pending_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        pending_layout.addWidget(self.pending_list)
        columns_layout.addLayout(pending_layout, 1)

        # 正在爬
        running_layout = QVBoxLayout()
        running_layout.setContentsMargins(0, 0, 0, 0)
        running_layout.setSpacing(8)
        self.running_label = Label("正在爬 (0)")
        running_layout.addWidget(self.running_label)
        self._running_model = QStringListModel(self)
        self.running_list = TokenListView(self)
        self.running_list.setModel(self._running_model)
        self.running_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.running_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        running_layout.addWidget(self.running_list)
        columns_layout.addLayout(running_layout, 1)

        # 已完成
        finished_layout = QVBoxLayout()
        finished_layout.setContentsMargins(0, 0, 0, 0)
        finished_layout.setSpacing(8)
        self.finished_label = Label("已完成 (0)")
        finished_layout.addWidget(self.finished_label)
        self._finished_model = QStringListModel(self)
        self.finished_list = TokenListView(self)
        self.finished_list.setModel(self._finished_model)
        self.finished_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.finished_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        finished_layout.addWidget(self.finished_list)
        columns_layout.addLayout(finished_layout, 1)

        root_layout.addLayout(columns_layout, 1)

        # 底部提示
        hint_label = Label("左：待爬，中：正在爬（不显示过程），右：已完成（成功/失败）。")
        hint_label.setWordWrap(True)
        hint_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        root_layout.addWidget(hint_label)

    def _connect_signals(self) -> None:
        global_signals.download_task_started.connect(self._on_task_started)
        global_signals.download_task_progress.connect(self._on_task_progress)
        global_signals.download_task_finished.connect(self._on_task_finished)

    def _init_poll_timer(self) -> None:
        """定时轮询爬虫管理器中的待爬队列，用于填充左侧待爬列表。"""
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(1000)  # 1 秒
        self._poll_timer.timeout.connect(self._poll_pending_tasks)
        self._poll_timer.start()

    # ========== 槽函数 ==========

    @Slot(str, int)
    def _on_task_started(self, serial: str, total: int) -> None:
        # 任务重新开始时，解除“已清空”隐藏
        self._dismissed_finished_serials.discard(serial)
        state = self._tasks.get(serial)
        if state is None:
            state = DownloadTaskState(serial=serial, current=0, total=max(0, int(total)))
            self._tasks[serial] = state
        else:
            state.total = max(0, int(total))
            state.current = 0
            state.finished = False
            state.success = False

        state.started = True
        state.status_text = "开始下载"
        self._recompute_column_for_task(serial)
        self._sync_models_if_needed()
        self._refresh_counters()

    @Slot()
    def _poll_pending_tasks(self) -> None:
        """从 CrawlerManager2 读取待爬/运行中任务，增强三列判断。"""
        try:
            from core.crawler.CrawlerManager import get_manager

            manager = get_manager()
        except Exception:
            # 若管理器尚未初始化或发生异常，则本轮忽略
            return

        try:
            queue_serials = {item[0] for item in manager.request_queue}
            running_serials = set(manager.tasks.keys())
        except Exception:
            return

        # 同步“中止/继续”按钮状态
        try:
            terminated = bool(getattr(manager, "is_crawl_terminated", lambda: False)())
            self.pause_button.setEnabled(not terminated)
            self.resume_button.setEnabled(terminated)
        except Exception:
            # 按钮状态同步失败不影响主流程
            pass

        # 先重置所有任务的队列/爬取标记
        for state in self._tasks.values():
            state.in_queue = False
            state.crawling = False

        # 队列中的任务标记为 in_queue
        for serial in queue_serials:
            if serial in self._dismissed_finished_serials:
                continue
            state = self._tasks.get(serial)
            if state is None:
                state = DownloadTaskState(serial=serial)
                self._tasks[serial] = state
            state.in_queue = True

        # CrawlerManager.tasks 中的任务标记为 crawling
        for serial in running_serials:
            if serial in self._dismissed_finished_serials:
                continue
            state = self._tasks.get(serial)
            if state is None:
                state = DownloadTaskState(serial=serial)
                self._tasks[serial] = state
            state.crawling = True

        # 根据最新标记重新放入三列
        for serial in list(self._tasks.keys()):
            self._recompute_column_for_task(serial)

        self._sync_models_if_needed()
        self._refresh_counters()

    @Slot(str, int, int, str)
    def _on_task_progress(self, serial: str, current: int, total: int, msg: str) -> None:
        state = self._tasks.get(serial)
        if state is None:
            state = DownloadTaskState(serial=serial)
            self._tasks[serial] = state

        state.started = True
        state.current = max(0, int(current))
        if total:
            state.total = max(0, int(total))
        # 不再在 UI 中展示详细过程，只保留内部状态
        if msg:
            state.status_text = msg

        self._recompute_column_for_task(serial)
        self._sync_models_if_needed()
        self._refresh_counters()

    @Slot(str, bool, str)
    def _on_task_finished(self, serial: str, success: bool, msg: str) -> None:
        state = self._tasks.get(serial)
        if state is None:
            state = DownloadTaskState(serial=serial)
            self._tasks[serial] = state

        state.finished = True
        state.success = success
        if msg:
            state.status_text = msg

        self._recompute_column_for_task(serial)
        self._sync_models_if_needed()
        self._refresh_counters()

    # ========== UI 更新 ==========

    def _remove_from_all_columns(self, serial: str) -> None:
        if serial in self._pending_serials:
            self._pending_serials.remove(serial)
        if serial in self._running_serials:
            self._running_serials.remove(serial)
        if serial in self._finished_serials:
            self._finished_serials.remove(serial)

    def _recompute_column_for_task(self, serial: str) -> None:
        state = self._tasks.get(serial)
        if not state:
            return

        if state.finished and serial in self._dismissed_finished_serials:
            # 用户已清空（隐藏）该完成项：不再展示
            self._remove_from_all_columns(serial)
            self._models_dirty = True
            return

        self._remove_from_all_columns(serial)

        # 列划分顺序：已完成 > 正在爬（爬元数据或下载封面） > 待爬
        if state.finished:
            self._finished_serials.insert(0, serial)
        elif state.crawling or state.started:
            self._running_serials.insert(0, serial)
        elif state.in_queue:
            self._pending_serials.insert(0, serial)
        else:
            # 既不在队列、也不在 tasks、且未开始/未完成：不展示
            return

        self._models_dirty = True

    def _display_text_for_serial(self, serial: str) -> str:
        state = self._tasks.get(serial)
        if not state:
            return serial

        display_serial = state.serial or "未知任务"

        # 文本规则：
        # 待爬：只标识任务 + “(待爬)”
        # 正在爬：只显示任务标识，不显示进度过程
        # 已完成：任务标识 + 成功/失败标记
        if serial in self._finished_serials:
            suffix = "✅" if state.success else "❌"
            return f"{display_serial} {suffix}"
        if serial in self._running_serials:
            return display_serial
        else:
            return f"{display_serial} (待爬)"

    def _sync_models(self) -> None:
        # 刷新模型会清空 QListView 的 selection。这里先记住当前“待爬”选中的 serial，刷新后尽量恢复。
        selected_pending_serial = None
        try:
            indexes = self.pending_list.selectionModel().selectedIndexes()
            if indexes:
                row = int(indexes[0].row())
                if 0 <= row < len(self._pending_serials):
                    selected_pending_serial = self._pending_serials[row]
        except Exception:
            selected_pending_serial = None

        self._pending_model.setStringList([self._display_text_for_serial(s) for s in self._pending_serials])
        self._running_model.setStringList([self._display_text_for_serial(s) for s in self._running_serials])
        self._finished_model.setStringList([self._display_text_for_serial(s) for s in self._finished_serials])

        # 恢复待爬选择
        try:
            if selected_pending_serial and selected_pending_serial in self._pending_serials:
                row = self._pending_serials.index(selected_pending_serial)
                idx = self._pending_model.index(row)
                if idx.isValid():
                    self.pending_list.setCurrentIndex(idx)
                    self.pending_list.selectionModel().select(
                        idx,
                        QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows
                    )
        except Exception:
            pass
        self._models_dirty = False

    def _sync_models_if_needed(self) -> None:
        if self._models_dirty:
            self._sync_models()

    def _refresh_counters(self) -> None:
        # 待爬：仍在队列中，且没有开始下载/完成
        pending_count = sum(
            1 for s in self._tasks.values() if s.in_queue and not s.started and not s.finished
        )
        # 正在爬：在 CrawlerManager.tasks 中或已经开始下载封面，且未完成
        running_count = sum(
            1 for s in self._tasks.values() if (s.crawling or s.started) and not s.finished
        )
        finished_count = sum(
            1
            for serial, s in self._tasks.items()
            if s.finished and serial not in self._dismissed_finished_serials
        )

        self.pending_label.setText(f"待爬 ({pending_count})")
        self.running_label.setText(f"正在爬 ({running_count})")
        self.finished_label.setText(f"已完成 ({finished_count})")

    @Slot()
    def _clear_finished(self) -> None:
        """清空（隐藏）已完成列表项，不影响待爬/正在爬。"""
        remove_serials = [s for s, st in self._tasks.items() if st.finished]
        for serial in remove_serials:
            self._dismissed_finished_serials.add(serial)
            self._remove_from_all_columns(serial)

        self._models_dirty = True
        self._sync_models_if_needed()
        self._refresh_counters()

    @Slot()
    def _pause_crawl(self) -> None:
        """中止调度：不再启动新的爬取任务，正在爬的继续；默认不清空队列，便于继续。"""
        try:
            from core.crawler.CrawlerManager import get_manager

            get_manager().terminate_crawl(clear_queue=False)
        except Exception:
            return

    @Slot()
    def _resume_crawl(self) -> None:
        """继续调度：恢复从队列中取任务执行。"""
        try:
            from core.crawler.CrawlerManager import get_manager

            get_manager().resume_crawl()
        except Exception:
            return

    @Slot()
    def _add_task(self) -> None:
        """弹出快速添加番号对话框。"""
        try:
            from ui.dialogs.AddQuickWork import AddQuickWork

            AddQuickWork().exec()
        except Exception:
            return

    @Slot()
    def _delete_selected_pending(self) -> None:
        """删除左侧“待爬”中选中的单个任务（从队列+ini移除，重启不再恢复）。"""
        try:
            indexes = self.pending_list.selectionModel().selectedIndexes()
            if not indexes:
                return
            row = int(indexes[0].row())
            if row < 0 or row >= len(self._pending_serials):
                return
            serial = self._pending_serials[row]
            if not serial:
                return

            from core.crawler.CrawlerManager import get_manager

            manager = get_manager()
            # 仅删除待爬队列任务；不强杀正在爬的 worker
            if hasattr(manager, "drop_pending"):
                manager.drop_pending(serial)
        except Exception:
            return

