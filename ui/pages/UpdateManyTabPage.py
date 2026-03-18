from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
from PySide6.QtCore import Slot,QThreadPool
import logging
from core.crawler.download import update_title_story_db
from core.crawler.javtxt import top_actresses
from darkeye_ui import LazyWidget
from darkeye_ui.components.button import Button


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
        mainlayout=QVBoxLayout(self)
        mainlayout.addLayout(layout1)
        self.btn_update_needactress.clicked.connect(self.searchActressinfo)


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



