from PySide6.QtWidgets import QPushButton, QHBoxLayout,QVBoxLayout
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

        self.btn_update_db_video=Button("查找本地的视频录入数据库")
        self.btn_update_db_video.setToolTip("扫描本地视频的路径下的所有视频，并提取视频番号，将没有的番号尝试去抓取信息")

        #self.btn_search_actor.clicked.connect(update_actor_db)
        self.btn_search_story.clicked.connect(update_title_story_db)
        self.btn_search_actress.clicked.connect(self.task_search_actress)

        layout1=QHBoxLayout()
        layout1.addWidget(self.btn_search_story)
        #layout1.addWidget(self.btn_search_actor)
        layout1.addWidget(self.btn_search_actress)
        layout1.addWidget(self.btn_update_needactress)
        layout1.addWidget(self.btn_update_db_video)
        mainlayout=QVBoxLayout(self)
        mainlayout.addLayout(layout1)

        self.btn_update_db_video.clicked.connect(self.task_update_db_video)

    @Slot()
    def task_update_db_video(self):
        '''扫描本地视频的路径下的所有视频，并提取视频文件名中的番号，去除名字中的-C,-UC，将数据库中没有的番号弹出 AddQuickWork 供抓取'''
        from config import get_video_path
        from core.database.query import get_serial_number
        from utils.utils import (
            get_video_names_from_paths,
        )
        from ui.dialogs.AddQuickWork import AddQuickWork

        def _norm(s: str) -> str:
            return s.upper().replace("-", "")

        video_names = get_video_names_from_paths(get_video_path())
        logging.info(f"视频文件名列表: {video_names}，数量: {len(video_names)}")
        db_serials = get_serial_number()
        db_normalized = {_norm(s) for s in db_serials}

        missing_serials: list[str] = []
        seen_normalized: set[str] = set()
        for name in video_names:
            #serial = extract_serial_from_string(name)
            #if serial:
            norm = _norm(name)
            if norm not in db_normalized and norm not in seen_normalized:
                seen_normalized.add(norm)
                missing_serials.append(name)

        if not missing_serials:
            self.msg.show_info("提示", "本地视频的番号均已存在于数据库中")
            return

        dialog = AddQuickWork()
        dialog.load_serials(missing_serials)
        dialog.exec()

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



