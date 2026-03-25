from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
from PySide6.QtCore import Slot,QThreadPool
import logging
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

        #self.btn_search_actor.clicked.connect(update_actor_db)
        self.btn_search_story.clicked.connect(update_title_story_db)
        self.btn_search_actress.clicked.connect(self.task_search_actress)

        layout1=QHBoxLayout()
        layout1.addWidget(self.btn_search_story)
        #layout1.addWidget(self.btn_search_actor)
        layout1.addWidget(self.btn_search_actress)
        layout1.addWidget(self.btn_update_needactress)
        mainlayout=QHBoxLayout(self)
        mainlayout.addLayout(layout1)
        self.crawler_auto_page = CrawlerAutoPage()
        mainlayout.addWidget(self.crawler_auto_page)
        self.btn_update_needactress.clicked.connect(self.searchActressinfo)
        self.crawler_auto_page.btn_get_crawler.setToolTip("根据指定字段，补充爬取")
        self.crawler_auto_page.btn_get_crawler.clicked.connect(self.bulk_crawl_empty_fields)


    @Slot()
    def task_search_actress(self):
        if top_actresses():
            logging.info("更新完成")
        else:
            logging.error("更新失败")


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
        serials_to_crawl: list[str] = []
        for row in rows:
            serial = str(row.get("serial_number") or "").strip()
            if not serial:
                continue
            # OR 逻辑：任一勾选字段为空即入队
            if any(self._is_row_empty_for_field(row, field) for field in selected_fields):
                serials_to_crawl.append(serial)

        if not serials_to_crawl:
            self.msg.show_info("提示", "没有匹配到需要更新的作品")
            return

        get_manager().start_crawl(serials_to_crawl, withGUI=False, selected_fields=selected_fields)
        self.msg.show_info("开始更新", f"已加入队列 {len(serials_to_crawl)} 条")



