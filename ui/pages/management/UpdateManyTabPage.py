from PySide6.QtWidgets import QVBoxLayout, QWidget
from PySide6.QtCore import Slot, QThreadPool
import logging

from ui.myads.workspace_manager import WorkspaceManager, Placement, ContentConfig
from core.crawler.download import update_title_story_db
from core.crawler.javtxt import top_actresses
from darkeye_ui import LazyWidget
from darkeye_ui.components.button import Button
from ui.widgets.CrawlerToolBox import CrawlerAutoPage


class UpdateManyTabPage(LazyWidget):
    #软件的设置
    def __init__(self):
        super().__init__()
    def _lazy_load(self):
        logging.info("----------加载批量更新窗口----------")
        from controller.MessageService import MessageBoxService
        self.msg = MessageBoxService(self)

        #self.btn_search_actor=QPushButton("批量更新男优")
        self.btn_search_story=Button("批量更新所有的故事")
        self.btn_search_story.setEnabled(False)
        self.btn_search_actress=Button("更新热门女优")
        self.btn_search_actress.setToolTip("更新javatext热门女优前50")

        self.btn_update_needactress=Button("更新标记需要更新的女优数据")
        self.btn_update_needactress.setToolTip("把所有被标记为需要更新的女优一个一个进行数据更新")

        self.btn_update_maker_by_knowledge=Button("根据番号前缀判断片商")
        self.btn_update_maker_by_knowledge.setToolTip("根据番号前缀把，那些确定的片商都给改了")

        #self.btn_search_actor.clicked.connect(update_actor_db)
        self.btn_search_story.clicked.connect(update_title_story_db)
        self.btn_search_actress.clicked.connect(self.task_search_actress)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)
        left_layout.addWidget(self.btn_search_story)
        left_layout.addWidget(self.btn_search_actress)
        left_layout.addWidget(self.btn_update_needactress)
        left_layout.addWidget(self.btn_update_maker_by_knowledge)
        left_layout.addStretch()

        self.crawler_auto_page = CrawlerAutoPage()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self._workspace_manager = WorkspaceManager(self)
        main_layout.addWidget(self._workspace_manager.widget())
        root = self._workspace_manager.get_root_pane()

        def make_config(title: str, w: QWidget, closeable: bool = True) -> ContentConfig:
            cfg = self._workspace_manager.create_content_config()
            return cfg.set_window_title(title).set_widget(w).set_closeable(closeable)

        pane_crawler = self._workspace_manager.split(root, Placement.Right, ratio=0.72)
        self._workspace_manager.fill_pane(root, make_config("批量操作", left_panel, closeable=False))
        self._workspace_manager.fill_pane(
            pane_crawler, make_config("空字段补充爬取", self.crawler_auto_page, closeable=False)
        )
        self.btn_update_needactress.clicked.connect(self.searchActressinfo)
        self.btn_update_maker_by_knowledge.clicked.connect(self.task_update_maker_by_prefix)
        self.crawler_auto_page.btn_get_crawler.setToolTip("根据指定字段，补充爬取，该功能为对所有的片进行筛选，只对有空字段的进行爬取，而且只更新空字段")
        self.crawler_auto_page.btn_get_crawler.clicked.connect(self.bulk_crawl_empty_fields)


    @Slot()
    def task_search_actress(self):
        if top_actresses():
            logging.info("更新完成")
        else:
            logging.error("更新失败")

    @Slot()
    def task_update_maker_by_prefix(self):
        from core.crawler.Worker import Worker
        from core.database.update import update_work_maker_from_prefix_relation

        def _run():
            return update_work_maker_from_prefix_relation()

        worker = Worker(_run)
        worker.signals.finished.connect(self._on_maker_prefix_update_finished)
        QThreadPool.globalInstance().start(worker)
        self.msg.show_info("开始", "正在按 prefix_maker_relation 回写片商…")

    @Slot(object)
    def _on_maker_prefix_update_finished(self, result):
        from controller.GlobalSignalBus import global_signals

        if result is None:
            self.msg.show_info("错误", "更新失败，请查看日志")
            return
        global_signals.work_data_changed.emit()
        self.msg.show_info("完成", str(result))

    @Slot()
    def searchActressinfo(self):
        #开始后台线程
        from core.crawler.minnanoav import actress_need_update,SearchActressInfo
        from core.crawler.Worker import Worker

        if actress_need_update():
            worker=Worker(SearchActressInfo)#传一个函数名进去
            worker.signals.finished.connect(self.on_result)
            QThreadPool.globalInstance().start(worker)
            self.msg.show_info("开始更新","开始更新，可能需要一段时间")
        else:
            self.msg.show_info("提示","没有要更新的女优")

    @Slot(object)
    def on_result(self,result:str):#Qsignal回传信息
        self.msg.show_info("提示",result)

    def _get_selected_crawler_fields(self) -> set[str]:
        """读取爬虫勾选项，映射为标准字段名。"""
        selected: set[str] = set()
        field_map = {
            "release_date": self.crawler_auto_page.cb_release_date,
            "director": self.crawler_auto_page.cb_director,
            "cover": self.crawler_auto_page.cb_cover,
            "cn_title": self.crawler_auto_page.cb_cn_title,
            "jp_title": self.crawler_auto_page.cb_jp_title,
            "cn_story": self.crawler_auto_page.cb_cn_story,
            "jp_story": self.crawler_auto_page.cb_jp_story,
            "actress": self.crawler_auto_page.cb_actress,
            "actor": self.crawler_auto_page.cb_actor,
            "tag": self.crawler_auto_page.cb_tag,
            "runtime": self.crawler_auto_page.cb_runtime,
            "maker": self.crawler_auto_page.cb_maker,
            "series": self.crawler_auto_page.cb_series,
            "label": self.crawler_auto_page.cb_label,
        }
        for field_name, checkbox in field_map.items():
            if checkbox.isChecked():
                selected.add(field_name)
        return selected

    def _is_row_empty_for_field(self, row: dict, field_name: str) -> bool:
        """按约定规则判断单字段是否为空。"""
        if field_name in {"actress", "actor", "tag"}:
            count_key = f"{field_name}_count"
            return int(row.get(count_key) or 0) <= 0
        if field_name in {"maker", "label", "series"}:
            return row.get(f"{field_name}_id") is None
        if field_name == "cover":
            val = row.get("image_url")
            return val is None or str(val).strip() == ""
        if field_name == "runtime":
            val = row.get("runtime")
            try:
                return val is None or int(val) <= 0
            except (TypeError, ValueError):
                return True
        val = row.get(field_name)
        return val is None or str(val).strip() == ""

    @Slot()
    def bulk_crawl_empty_fields(self):
        from core.database.query.work import get_works_for_bulk_crawl_fields
        from core.crawler.CrawlerManager import get_manager

        selected_fields = self._get_selected_crawler_fields()
        logging.info("批量空值爬虫触发，勾选字段: %s", sorted(selected_fields))
        if not selected_fields:
            self.msg.show_info("提示", "请先勾选至少一个字段")
            return

        rows = get_works_for_bulk_crawl_fields()
        manager = get_manager()
        queued = 0
        for row in rows:
            serial = str(row.get("serial_number") or "").strip()
            if not serial:
                continue
            per_work_fields = {
                f
                for f in selected_fields
                if self._is_row_empty_for_field(row, f)
            }
            if not per_work_fields:
                continue
            before = len(manager.request_queue)
            manager.start_crawl(
                [serial], withGUI=False, selected_fields=per_work_fields
            )
            if len(manager.request_queue) > before:
                queued += 1

        if not queued:
            self.msg.show_info("提示", "没有匹配到需要更新的作品（勾选字段在该批作品中均已非空）")
            return

        self.msg.show_info("开始更新", f"已加入队列 {queued} 条（每条仅爬取其空白勾选字段）")



