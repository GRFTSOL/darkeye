from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

from PySide6.QtCore import QSize, Qt, Slot, QTimer, QStringListModel
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QAbstractItemView,
    QListWidgetItem,
    QMessageBox,
)

from controller.global_signal_bus import global_signals
from core.crawler.crawler_task import CrawlWorkflowState
from darkeye_ui.components import Button, Label, TokenListView, TokenListWidget
from ui.widgets.work_completeness_leds import WorkCompletenessLedStrip

_WORKFLOW_LABELS: dict[CrawlWorkflowState, str] = {
    CrawlWorkflowState.QUEUED: "排队",
    CrawlWorkflowState.CRAWLING: "API 请求",
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
    # 库内 15 维完整度；None 表示尚未收到 workCrawlCompleteness
    completeness: dict[str, bool] | None = None


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
        self._last_finished_fingerprint: tuple | None = None

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

        self._btn_resume_queue = Button("开始队列", variant="primary")
        self._btn_resume_queue.setToolTip(
            "恢复调度：按待爬队列继续处理尚未开始的番号（与启动时恢复的暂停态对应）。"
        )
        self._btn_pause_queue = Button("暂停队列")
        self._btn_pause_queue.setToolTip(
            "暂停调度：不再从队列弹出新的番号；待爬列表保留。"
            "已在请求或入库、封面下载中的任务会继续跑完。"
        )
        self._btn_clear_queue = Button("清除全部队列")
        self._btn_clear_queue.setToolTip(
            "清空待爬队列并进入暂停态；不会中断已在进行的请求或下载。"
        )
        self._btn_resume_queue.clicked.connect(self._on_resume_queue_clicked)
        self._btn_pause_queue.clicked.connect(self._on_pause_queue_clicked)
        self._btn_clear_queue.clicked.connect(self._on_clear_queue_clicked)
        header_layout.addWidget(self._btn_resume_queue)
        header_layout.addWidget(self._btn_pause_queue)
        header_layout.addWidget(self._btn_clear_queue)

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
        self.finished_list = TokenListWidget(self)
        self.finished_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.finished_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        finished_layout.addWidget(self.finished_list)
        columns_layout.addLayout(finished_layout, 1)

        root_layout.addLayout(columns_layout, 1)

        hint_label = Label(
            "左：request_queue；中：active 任务（含工作流阶段与封面下载）；右："
            "downloadTaskFinished 收尾状态；绿/红灯为入库后库内 15 项完整度（封面在落盘"
            "后可能二次刷新）。"
        )
        hint_label.setWordWrap(True)
        hint_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        root_layout.addWidget(hint_label)

    def _connect_signals(self) -> None:
        global_signals.downloadTaskStarted.connect(self._on_task_started)
        global_signals.downloadTaskProgress.connect(self._on_task_progress)
        global_signals.downloadTaskFinished.connect(self._on_task_finished)
        global_signals.workCrawlCompleteness.connect(self._on_work_crawl_completeness)

    def _init_poll_timer(self) -> None:
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(1000)
        self._poll_timer.timeout.connect(self._poll_crawler_snapshot)
        self._poll_timer.start()

    def _crawler_manager_or_none(self):
        try:
            from core.crawler.crawler_manager import get_manager

            return get_manager()
        except Exception:
            logging.warning(
                "InboxPage: 无法获取 CrawlerManager（可能尚未初始化）",
                exc_info=True,
            )
            return None

    @Slot()
    def _on_resume_queue_clicked(self) -> None:
        mgr = self._crawler_manager_or_none()
        if mgr is None:
            return
        try:
            mgr.resume_crawl()
        except Exception:
            logging.exception("InboxPage: resume_crawl 失败")
            return
        self._poll_crawler_snapshot()

    @Slot()
    def _on_pause_queue_clicked(self) -> None:
        mgr = self._crawler_manager_or_none()
        if mgr is None:
            return
        try:
            mgr.terminate_crawl(clear_queue=False)
        except Exception:
            logging.exception("InboxPage: terminate_crawl(pause) 失败")
            return
        self._poll_crawler_snapshot()

    @Slot()
    def _on_clear_queue_clicked(self) -> None:
        mgr = self._crawler_manager_or_none()
        if mgr is None:
            return
        q_len = len(mgr.request_queue)
        if q_len == 0:
            return
        reply = QMessageBox.question(
            self,
            "清除全部队列",
            f"确定清空待爬队列中的 {q_len} 个番号吗？\n"
            "已在进行中的任务不会被中断；清空后调度将暂停。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            mgr.terminate_crawl(clear_queue=True)
        except Exception:
            logging.exception("InboxPage: terminate_crawl(clear) 失败")
            return
        self._poll_crawler_snapshot()

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

    @Slot(str, object)
    def _on_work_crawl_completeness(self, serial: str, flags: object) -> None:
        s = str(serial or "").strip()
        if not s or not isinstance(flags, dict):
            return
        state = self._tasks.get(s)
        if state is None:
            state = DownloadTaskState(serial=s)
            self._tasks[s] = state
        state.completeness = dict(flags)
        self._models_dirty = True
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

        # 已完成项勿在轮询中反复移除再置顶，否则会按 dict 顺序打乱完成先后。
        if state.finished:
            if serial in self._pending_serials:
                self._pending_serials.remove(serial)
            if serial in self._running_serials:
                self._running_serials.remove(serial)
            if serial not in self._finished_serials:
                self._finished_serials.insert(0, serial)
            self._models_dirty = True
            return

        self._remove_from_all_columns(serial)

        if state.crawling or state.started:
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
        self._sync_finished_list()
        self._models_dirty = False

    def _finished_list_fingerprint(self) -> tuple:
        parts: list[tuple] = []
        for serial in self._finished_serials:
            state = self._tasks.get(serial)
            if not state:
                continue
            c = state.completeness
            c_key = None if c is None else tuple(sorted(c.items()))
            parts.append((serial, state.success, state.status_text, c_key))
        return tuple(parts)

    def _sync_finished_list(self) -> None:
        fp = self._finished_list_fingerprint()
        if fp == self._last_finished_fingerprint:
            return
        self._last_finished_fingerprint = fp

        sb = self.finished_list.verticalScrollBar()
        old_val = sb.value()
        old_max = sb.maximum()
        # 接近底部时刷新后仍保持在底部（列表变长时）
        stick_bottom = old_max > 0 and (old_val >= old_max - 4)

        self.finished_list.clear()
        for serial in self._finished_serials:
            state = self._tasks.get(serial)
            if not state:
                continue
            item = QListWidgetItem()
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(6, 4, 6, 4)
            row_layout.setSpacing(10)
            title_text = state.serial or "未知任务"
            title = Label(title_text)
            title.setWordWrap(False)
            if not state.success and state.status_text:
                tip = state.status_text
                title.setToolTip(tip)
                row.setToolTip(tip)
            strip = WorkCompletenessLedStrip(state.completeness, row)
            row_layout.addWidget(title, 1)
            row_layout.addWidget(strip, 0)
            self.finished_list.addItem(item)
            self.finished_list.setItemWidget(item, row)
            row.updateGeometry()
            sh = row.sizeHint()
            mh = row.minimumSizeHint()
            # QSS 中 DesignListWidget::item 上下 padding 共 8px，且 min-height 36px，行高取较大者
            pad_v = 8
            h = max(sh.height() + pad_v, mh.height() + pad_v, 36)
            w = max(sh.width(), mh.width(), 1)
            item.setSizeHint(QSize(w, h))

        def _restore_scroll() -> None:
            sb2 = self.finished_list.verticalScrollBar()
            mx = sb2.maximum()
            if mx <= 0:
                return
            if stick_bottom:
                sb2.setValue(mx)
            else:
                sb2.setValue(min(old_val, mx))

        QTimer.singleShot(0, _restore_scroll)

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
