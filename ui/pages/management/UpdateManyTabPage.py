from PySide6.QtWidgets import QVBoxLayout, QWidget
from PySide6.QtCore import Slot, QThreadPool, QTimer
import logging

from darkeye_ui import LazyWidget
from darkeye_ui.components.button import Button


class UpdateManyTabPage(LazyWidget):
    # 软件的设置
    def __init__(self):
        super().__init__()

    def _lazy_load(self):
        logging.info("----------加载批量更新窗口----------")
        from controller.message_service import MessageBoxService

        self.msg = MessageBoxService(self)
        self._force_translate_done = 0
        self._force_translate_total = 0
        self._force_translate_elapsed = 0.0
        self._force_translate_timer = QTimer(self)
        self._force_translate_timer.setInterval(400)
        self._force_translate_timer.timeout.connect(self._on_force_progress_tick)

        self.btn_search_actress = Button("更新热门女优")
        self.btn_search_actress.setToolTip(
            "由 Firefox 插件打开 javtxt 热门页并解析前 50 名写入库"
        )

        self.btn_update_needactress = Button("更新标记需要更新的女优数据")
        self.btn_update_needactress.setToolTip(
            "把所有被标记为需要更新的女优一个一个进行数据更新"
        )

        self.btn_update_maker_by_knowledge = Button("根据番号前缀判断片商")
        self.btn_update_maker_by_knowledge.setToolTip(
            "根据番号前缀把，那些确定的片商都给改了"
        )

        self.btn_batch_translate_cn = Button("一键翻译标题/简介")
        self.btn_batch_translate_cn.setToolTip(
            "后台执行：有日文标题且中文标题为空时翻译成 cn_title；"
            "有日文简介且中文简介为空时翻译成 cn_story；二者皆无日文源的作品不会请求翻译。"
        )
        self.btn_force_translate_cn = Button("覆盖翻译标题/简介")
        self.btn_force_translate_cn.setToolTip(
            "后台执行：只要有日文标题/简介，就强制翻译并覆盖写入 cn_title/cn_story；"
            "翻译并发 4 个 worker。"
        )

        self.btn_normalize_cover_names = Button("统一封面文件名为番号.jpg")
        self.btn_normalize_cover_names.setToolTip(
            "将 work.image_url 及 workcovers 目录内对应文件统一为 「番号.jpg」；"
            "磁盘上缺少源文件、或目标文件名已存在时跳过该条（不覆盖）。"
        )

        self.btn_search_actress.clicked.connect(self.task_search_actress)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)
        left_layout.addWidget(self.btn_search_actress)
        left_layout.addWidget(self.btn_update_needactress)
        left_layout.addWidget(self.btn_update_maker_by_knowledge)
        left_layout.addWidget(self.btn_batch_translate_cn)
        left_layout.addWidget(self.btn_force_translate_cn)
        left_layout.addWidget(self.btn_normalize_cover_names)
        left_layout.addStretch()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(left_panel)
        self.btn_update_needactress.clicked.connect(self.search_actress_info)
        self.btn_update_maker_by_knowledge.clicked.connect(
            self.task_update_maker_by_prefix
        )
        self.btn_batch_translate_cn.clicked.connect(self.task_batch_translate_cn)
        self.btn_force_translate_cn.clicked.connect(self.task_force_translate_cn)
        self.btn_normalize_cover_names.clicked.connect(
            self.task_normalize_cover_filenames
        )

    @Slot()
    def task_search_actress(self):
        from core.crawler.javtxt import top_actresses
        from core.crawler.worker import Worker, wire_worker_finished

        worker = Worker(top_actresses)
        wire_worker_finished(worker, self._on_top_actresses_finished)
        QThreadPool.globalInstance().start(worker)
        self.msg.show_info("开始", "已在浏览器打开 javtxt 热门页，请稍候…")

    @Slot(object)
    def _on_top_actresses_finished(self, result):
        if result is None:
            self.msg.show_info("错误", "更新失败，请查看日志")
            return
        if result:
            self.msg.show_info("完成", "热门女优已更新")
        else:
            self.msg.show_info(
                "失败",
                "未能完成更新（请确认 Firefox 插件已连接、或查看日志）",
            )

    @Slot()
    def task_update_maker_by_prefix(self):
        from core.crawler.worker import Worker, wire_worker_finished
        from core.database.update import update_work_maker_from_prefix_relation

        def _run():
            return update_work_maker_from_prefix_relation()

        worker = Worker(_run)
        wire_worker_finished(worker, self._on_maker_prefix_update_finished)
        QThreadPool.globalInstance().start(worker)
        self.msg.show_info("开始", "正在按 prefix_maker_relation 回写片商…")

    @Slot(object)
    def _on_maker_prefix_update_finished(self, result):
        from controller.global_signal_bus import global_signals

        if result is None:
            self.msg.show_info("错误", "更新失败，请查看日志")
            return
        global_signals.workDataChanged.emit()
        self.msg.show_info("完成", str(result))

    @Slot()
    def task_batch_translate_cn(self):
        from core.crawler.worker import Worker, wire_worker_finished
        from core.database.update import batch_translate_missing_cn_fields

        worker = Worker(batch_translate_missing_cn_fields)
        wire_worker_finished(worker, self._on_batch_translate_finished)
        QThreadPool.globalInstance().start(worker)
        self.msg.show_info("开始", "正在后台翻译并写库，请稍候…")

    @Slot(object)
    def _on_batch_translate_finished(self, result):
        from controller.global_signal_bus import global_signals

        if result is None:
            self.msg.show_info("错误", "批量翻译失败，请查看日志")
            return
        global_signals.workDataChanged.emit()
        self.msg.show_info("完成", str(result))

    @Slot()
    def task_force_translate_cn(self):
        from core.crawler.worker import Worker, wire_worker_finished
        from core.database.update import batch_force_translate_cn_fields

        self._force_translate_done = 0
        self._force_translate_total = 0
        self._force_translate_elapsed = 0.0
        self.btn_force_translate_cn.setEnabled(False)
        self._on_force_progress_tick()
        self._force_translate_timer.start()

        worker = Worker(
            lambda: batch_force_translate_cn_fields(
                max_workers=4,
                progress_cb=self._update_force_translate_progress,
            )
        )
        wire_worker_finished(worker, self._on_force_translate_finished)
        QThreadPool.globalInstance().start(worker)
        self.msg.show_info("开始", "正在后台强制翻译并覆盖写库，请稍候…")

    @Slot(object)
    def _on_force_translate_finished(self, result):
        from controller.global_signal_bus import global_signals

        self._force_translate_timer.stop()
        self.btn_force_translate_cn.setEnabled(True)
        self.btn_force_translate_cn.setText("覆盖翻译标题/简介")

        if result is None:
            self.msg.show_info("错误", "覆盖翻译失败，请查看日志")
            return
        global_signals.workDataChanged.emit()
        self.msg.show_info("完成", str(result))

    def _update_force_translate_progress(self, done: int, total: int, elapsed_s: float):
        self._force_translate_done = max(0, int(done))
        self._force_translate_total = max(0, int(total))
        self._force_translate_elapsed = max(0.0, float(elapsed_s))

    @Slot()
    def _on_force_progress_tick(self):
        total = self._force_translate_total
        done = min(self._force_translate_done, total) if total else 0
        elapsed = self._force_translate_elapsed
        if total > 0:
            self.btn_force_translate_cn.setText(
                f"覆盖翻译中 {done}/{total} · {elapsed:.1f}s"
            )
        else:
            self.btn_force_translate_cn.setText(f"覆盖翻译中 0/0 · {elapsed:.1f}s")

    @Slot()
    def task_normalize_cover_filenames(self):
        from core.crawler.worker import Worker, wire_worker_finished
        from core.database.update import normalize_work_cover_filenames_to_serial

        worker = Worker(normalize_work_cover_filenames_to_serial)
        wire_worker_finished(worker, self._on_normalize_cover_names_finished)
        QThreadPool.globalInstance().start(worker)
        self.msg.show_info("开始", "正在统一封面文件名与 image_url…")

    @Slot(object)
    def _on_normalize_cover_names_finished(self, result):
        from controller.global_signal_bus import global_signals

        if result is None:
            self.msg.show_info("错误", "处理失败，请查看日志")
            return
        global_signals.workDataChanged.emit()
        self.msg.show_info("完成", str(result))

    @Slot()
    def search_actress_info(self):
        # 开始后台线程
        from core.crawler.minnanoav import actress_need_update, SearchActressInfo_js
        from core.crawler.worker import Worker, wire_worker_finished

        if actress_need_update():
            worker = Worker(SearchActressInfo_js)
            wire_worker_finished(worker, self.on_result)
            QThreadPool.globalInstance().start(worker)
            self.msg.show_info("开始更新", "开始更新，可能需要一段时间")
        else:
            self.msg.show_info("提示", "没有要更新的女优")

    @Slot(object)
    def on_result(self, result):  # Qsignal回传信息
        from controller.global_signal_bus import global_signals

        if isinstance(result, tuple) and len(result) == 2:
            msg, changed = result[0], result[1]
            if changed:
                global_signals.actressDataChanged.emit()
            self.msg.show_info("提示", str(msg))
            return
        self.msg.show_info("提示", str(result))
