from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

from PySide6.QtCore import Qt, Slot, QTimer, QStringListModel
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QAbstractItemView,
)

from controller.global_signal_bus import global_signals
from core.crawler.crawler_task import CrawlWorkflowState
from darkeye_ui.components import Label, TokenListView

_WORKFLOW_LABELS: dict[CrawlWorkflowState, str] = {
    CrawlWorkflowState.QUEUED: "排队",
    CrawlWorkflowState.CRAWLING: "插件拉取",
    CrawlWorkflowState.PERSISTING: "入库",
}


@dataclass
class DownloadTaskState:
    serial: str
    current: int = 0
    total: int = 0
    status_text: str = ""
    finished: bool = False
    success: bool = False
    started: bool = False
    in_queue: bool = False
    crawling: bool = False
    workflow: CrawlWorkflowState | None = None


class InboxPage(QWidget):
    """
    爬虫任务 Inbox：仅只读展示。

    三列：待爬队列、进行中（元数据/入库/封面）、已完成（以下载收尾信号为准）。
    数据与 :class:`core.crawler.crawler_manager.CrawlerManager2` 的队列及任务字典对齐。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._tasks: Dict[str, DownloadTaskState] = {}
        self._pending_serials: list[str] = []
        self._running_serials: list[str] = []
        self._finished_serials: list[str] = []
        self._models_dirty: bool = False

        self._init_ui()
        self._connect_signals()
        self._init_poll_timer()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(8)

        header_layout = QHBoxLayout()
        self._scheduler_label = Label("调度：—")
        header_layout.addWidget(self._scheduler_label)
        header_layout.addStretch(1)
        root_layout.addLayout(header_layout)

        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(12)

        pending_layout = QVBoxLayout()
        pending_layout.setContentsMargins(0, 0, 0, 0)
        pending_layout.setSpacing(8)
        self.pending_label = Label("待爬 (0)")
        pending_layout.addWidget(self.pending_label)
        self._pending_model = QStringListModel(self)
        self.pending_list = TokenListView(self)
        self.pending_list.setModel(self._pending_model)
        self.pending_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.pending_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        pending_layout.addWidget(self.pending_list)
        columns_layout.addLayout(pending_layout, 1)

        running_layout = QVBoxLayout()
        running_layout.setContentsMargins(0, 0, 0, 0)
        running_layout.setSpacing(8)
        self.running_label = Label("进行中 (0)")
        running_layout.addWidget(self.running_label)
        self._running_model = QStringListModel(self)
        self.running_list = TokenListView(self)
        self.running_list.setModel(self._running_model)
        self.running_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.running_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        running_layout.addWidget(self.running_list)
        columns_layout.addLayout(running_layout, 1)

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

        hint_label = Label(
            "左：request_queue；中：active 任务（含工作流阶段与封面下载）；右："
            "downloadTaskFinished 收尾状态。"
        )
        hint_label.setWordWrap(True)
        hint_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        root_layout.addWidget(hint_label)

    def _connect_signals(self) -> None:
        global_signals.downloadTaskStarted.connect(self._on_task_started)
        global_signals.downloadTaskProgress.connect(self._on_task_progress)
        global_signals.downloadTaskFinished.connect(self._on_task_finished)

    def _init_poll_timer(self) -> None:
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(1000)
        self._poll_timer.timeout.connect(self._poll_crawler_snapshot)
        self._poll_timer.start()

    @Slot(str, int)
    def _on_task_started(self, serial: str, total: int) -> None:
        state = self._tasks.get(serial)
        if state is None:
            state = DownloadTaskState(
                serial=serial, current=0, total=max(0, int(total))
            )
            self._tasks[serial] = state
        else:
            state.total = max(0, int(total))
            state.current = 0
            state.finished = False
            state.success = False

        state.started = True
        state.status_text = "封面下载开始"
        self._recompute_column_for_task(serial)
        self._sync_models_if_needed()
        self._refresh_counters()

    @Slot()
    def _poll_crawler_snapshot(self) -> None:
        try:
            from core.crawler.crawler_manager import get_manager

            manager = get_manager()
        except Exception:
            logging.debug(
                "InboxPage: 获取 CrawlerManager 失败（可能未初始化）",
                exc_info=True,
            )
            return

        try:
            terminated = manager.is_crawl_terminated()
            q_len = len(manager.request_queue)
            self._scheduler_label.setText(
                f"调度：{'已暂停' if terminated else '运行中'} · 队列长度 {q_len}"
            )

            queue_serials, running_serials = manager.inbox_snapshot()
        except Exception:
            logging.debug(
                "InboxPage: 读取爬虫队列快照失败",
                exc_info=True,
            )
            return

        for state in self._tasks.values():
            state.in_queue = False
            state.crawling = False

        for serial in queue_serials:
            state = self._tasks.get(serial)
            if state is None:
                state = DownloadTaskState(serial=serial)
                self._tasks[serial] = state
            state.in_queue = True

        for serial in running_serials:
            state = self._tasks.get(serial)
            if state is None:
                state = DownloadTaskState(serial=serial)
                self._tasks[serial] = state
            state.crawling = True
            try:
                state.workflow = manager.get_serial_workflow_state(serial)
            except Exception:
                logging.debug(
                    "InboxPage: get_serial_workflow_state 失败 serial=%s",
                    serial,
                    exc_info=True,
                )
                state.workflow = None

        for serial in list(self._tasks.keys()):
            self._recompute_column_for_task(serial)

        self._sync_models_if_needed()
        self._refresh_counters()

    @Slot(str, int, int, str)
    def _on_task_progress(
        self, serial: str, current: int, total: int, msg: str
    ) -> None:
        state = self._tasks.get(serial)
        if state is None:
            state = DownloadTaskState(serial=serial)
            self._tasks[serial] = state

        state.started = True
        state.current = max(0, int(current))
        if total:
            state.total = max(0, int(total))
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

        self._remove_from_all_columns(serial)

        if state.finished:
            self._finished_serials.insert(0, serial)
        elif state.crawling or state.started:
            self._running_serials.insert(0, serial)
        elif state.in_queue:
            self._pending_serials.insert(0, serial)
        else:
            self._tasks.pop(serial, None)
            self._models_dirty = True
            return

        self._models_dirty = True

    def _running_subtitle(self, state: DownloadTaskState) -> str:
        if state.started:
            return "封面下载"
        wf = state.workflow
        if wf is not None:
            return _WORKFLOW_LABELS.get(wf, wf.value)
        if state.crawling:
            return "处理中"
        return ""

    def _display_text_for_serial(self, serial: str) -> str:
        state = self._tasks.get(serial)
        if not state:
            return serial

        display_serial = state.serial or "未知任务"

        if serial in self._finished_serials:
            suffix = "✅" if state.success else "❌"
            if not state.success and state.status_text:
                return f"{display_serial} {suffix} · {state.status_text}"
            return f"{display_serial} {suffix}"

        if serial in self._running_serials:
            sub = self._running_subtitle(state)
            return f"{display_serial} · {sub}" if sub else display_serial

        return f"{display_serial} (待爬)"

    def _sync_models(self) -> None:
        self._pending_model.setStringList(
            [self._display_text_for_serial(s) for s in self._pending_serials]
        )
        self._running_model.setStringList(
            [self._display_text_for_serial(s) for s in self._running_serials]
        )
        self._finished_model.setStringList(
            [self._display_text_for_serial(s) for s in self._finished_serials]
        )
        self._models_dirty = False

    def _sync_models_if_needed(self) -> None:
        if self._models_dirty:
            self._sync_models()

    def _refresh_counters(self) -> None:
        pending_count = sum(
            1
            for s in self._tasks.values()
            if s.in_queue and not s.started and not s.finished
        )
        running_count = sum(
            1
            for s in self._tasks.values()
            if (s.crawling or s.started) and not s.finished
        )
        finished_count = sum(1 for s in self._tasks.values() if s.finished)

        self.pending_label.setText(f"待爬 ({pending_count})")
        self.running_label.setText(f"进行中 ({running_count})")
        self.finished_label.setText(f"已完成 ({finished_count})")
