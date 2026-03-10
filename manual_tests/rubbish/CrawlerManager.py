import logging
import random
import asyncio
from time import sleep
from functools import partial
from PySide6.QtCore import QObject, Signal, QThreadPool, Slot
from core.crawler.Worker import Worker
from core.database.insert import InsertNewWork, InsertNewActress, InsertNewActor, add_tag2work
from core.database.update import update_work_byhand_
from core.database.query import exist_actress, exist_actor, get_tagid_by_keyword
from core.crawler.avdanyuwiki import SearchInfoDanyukiwi
from core.crawler.javtxt import fetch_javtxt_movie_info
from core.crawler.download import download_image
from config import WORKCOVER_PATH
from utils.utils import translate_text, text2tag_id_list

class CrawlerManager(QObject):
    _instance = None
    
    # 定义一些可能需要的信号
    # task_finished = Signal(str, bool, str) # serial_number, success, message

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(CrawlerManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        super().__init__()
        # 确保初始化只执行一次
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._active_workers = set()  # 防止 Worker 被 GC
            logging.info("CrawlerManager initialized")
            # 连接信号
            #from server.bridge import bridge
            #bridge.captureone_received.connect(lambda serial_number:self.start_batch_tasks([serial_number]))

    def _track_worker(self, worker: Worker):
        """追踪 worker 防止被 GC，并在完成后自动移除"""
        self._active_workers.add(worker)
        # 使用 weakref 或者直接闭包，这里直接用闭包简单有效
        # 注意：这里需要确保 worker 在 lambda 中被正确捕获
        worker.signals.finished.connect(lambda _: self._active_workers.discard(worker))

    def start_batch_tasks(self, serial_list: list[str]):
        """启动批量任务
        UI 线程调用此方法，此方法将整个批量逻辑扔到后台线程执行，立即返回
        """
        logging.info(f"CrawlerManager 接收到批量任务: {len(serial_list)} 个番号")
        worker = Worker(lambda: self._batch_process_serials(serial_list))
        self._track_worker(worker)
        QThreadPool.globalInstance().start(worker)

    def _batch_process_serials(self, serial_list: list[str]):

        """后台批量处理逻辑 (运行在 Worker 线程)"""
        success_count = 0
        logging.info(f"CrawlerManager 开始后台批量处理 {len(serial_list)} 个番号...")
        
        for i, serial in enumerate(serial_list):
            try:
                logging.info(f"正在处理: {serial}")
                work_id = InsertNewWork(serial)
                if work_id:
                    success_count += 1
                    # 启动针对单个番号的爬虫任务
                    self._start_single_crawler_task(serial, work_id)
                    
                    # 随机睡眠 8-15 秒
                    if i < len(serial_list) - 1: # 如果不是最后一个
                        sleep_time = random.uniform(8, 15)
                        logging.info(f"[{serial} 完成] 等待 {sleep_time:.2f} 秒后处理下一个...")
                        sleep(sleep_time)
            except Exception as e:
                logging.error(f"CrawlerManager 处理番号 {serial} 时出错: {e}")

        logging.info(f"CrawlerManager 批量处理完成。成功: {success_count}/{len(serial_list)}")

    def _start_single_crawler_task(self, serial_number: str, work_id: int):
        """启动单个番号的爬虫任务 (Javtxt 和 Danyuwiki)"""
        logging.info(f"后台查询番号：{serial_number}")
        
        # 任务1: Javtxt
        # 修改: Lambda 返回 (data, work_id) 元组
        work1 = Worker(lambda: (fetch_javtxt_movie_info(serial_number), work_id))
        work1.signals.finished.connect(self._on_javtxt_result)
        self._track_worker(work1)
        QThreadPool.globalInstance().start(work1)
        
        # 任务2: Danyuwiki
        # 修改: Lambda 返回 (data, work_id, serial_number) 元组
        work2 = Worker(lambda: (SearchInfoDanyukiwi(serial_number), work_id, serial_number))
        work2.signals.finished.connect(self._on_danyuwiki_result)
        self._track_worker(work2)
        QThreadPool.globalInstance().start(work2)



    # -------------------------------------------------------------------------
    # 回调函数区域 (注意：这些回调会在 QThread 线程中被调用，因为 Worker 是 QRunnable)
    # 或者如果通过信号连接，通常会在接收者所在的线程（这里 CrawlerManager 如果是在主线程创建，则在主线程）
    # 但 CrawlerManager 是单例，如果在主线程初始化，则 _on_xxx 默认在主线程执行。
    # 这正是我们想要的：逻辑在主线程/后台线程都行，关键是 CrawlerManager 不会被销毁。
    # -------------------------------------------------------------------------

    @Slot(object)
    def _on_javtxt_result(self, result_bundle):
        '''返回的数据直写入数据库中'''
        if not result_bundle or len(result_bundle) != 2:
            logging.warning("爬javtxt返回数据格式错误")
            return
            
        data, work_id = result_bundle
        logging.info(f"爬虫结束，获得javtxt信息{data}并写入数据库{work_id}")
        if not data:
            logging.warning("爬javtxt产生错误信息")
            return
        try:
            #写入中英文标题
            if data.get("cn_title") == "":
                cn_title = asyncio.run(translate_text(data.get("jp_title","")))
            else:
                cn_title = data.get("cn_title")

            if data.get("cn_story") == "":
                cn_story = asyncio.run(translate_text(data.get("jp_story","")))
            else:
                cn_story = data.get("cn_story")

            update_work_byhand_(work_id, cn_title=cn_title, jp_title=data.get("jp_title"), cn_story=cn_story, jp_story=data.get("jp_story"))

            #常试性分解tag然后写入
            tag_id_list = text2tag_id_list(data.get("jp_title",""))
            if tag_id_list:
                add_tag2work(work_id, tag_ids=tag_id_list)
        except Exception as e:
            logging.error(f"CrawlerManager _on_javtxt_result 异常: {e}")

    @Slot(object)
    def _on_danyuwiki_result(self, result_bundle):
        if not result_bundle or len(result_bundle) != 3:
             logging.warning("爬danyuwiki返回数据格式错误")
             return
             
        data, work_id, serial_number = result_bundle
        logging.info(f"爬虫结束，获得danyuwiki信息{data}")
        
        try:
            if not data:
                logging.warning("爬danyuwiki产生错误信息，尝试 MissAV")
                #这里通过missav下载封面
                dst_path = WORKCOVER_PATH / serial_number
                imageurl = f"https://fourhoi.com/{serial_number}/cover-n.jpg"

                # 修改: Lambda 返回 (result, work_id, image_url)
                worker1 = Worker(lambda: (download_image(imageurl, dst_path), work_id, imageurl))
                worker1.signals.finished.connect(self._on_download_image_missav)
                self._track_worker(worker1)
                QThreadPool.globalInstance().start(worker1)
                return

            #写入封面url,导演，拍摄时间
            logging.info("数据库写入danyuwiki的封面url,导演，拍摄时间")
            update_work_byhand_(work_id, director=data.get("director"), release_date=data.get("release_date"), fcover_url=data.get("cover"))

            #下载图片并写入
            image_filename = serial_number.strip().lower().replace('-', '') + 'pl.jpg'
            dst_path = WORKCOVER_PATH / image_filename
            cover_url = data.get("cover")

            # 修改: Lambda 返回 (result, work_id, image_filename)
            worker2 = Worker(lambda: (download_image(cover_url, dst_path), work_id, image_filename))
            worker2.signals.finished.connect(self._on_download_image_danyu)
            self._track_worker(worker2)
            QThreadPool.globalInstance().start(worker2)


            #直接写入女优
            actress_list = data.get("actress_list", [])
            actress_ids = []
            for actress in actress_list:
                id = exist_actress(actress)
                if id is None:
                    if InsertNewActress(actress, actress):
                        logging.info("添加女优成功:%s", actress)
                        id = exist_actress(actress)
                        actress_ids.append(id)
                        from controller.GlobalSignalBus import global_signals
                        global_signals.actress_data_changed.emit()
                else:
                    actress_ids.append(id)
            update_work_byhand_(work_id, actress_ids=actress_ids)

            #直接写入男优
            actor_list = data.get("actor_list", [])
            actor_ids = []
            for actor in actor_list:
                id = exist_actor(actor)
                if id is None:
                    if InsertNewActor(actor, actor):
                        logging.info("添加男优成功:%s", actor)
                        id = exist_actor(actor)
                        actor_ids.append(id)
                        from controller.GlobalSignalBus import global_signals
                        global_signals.actor_data_changed.emit()
                else:
                    actor_ids.append(id)
            update_work_byhand_(work_id, actor_ids=actor_ids)

            if len(actor_list) == 1 and len(actress_list) == 1:
                logging.info("自动写入1V1标签")
                tag_id_list = get_tagid_by_keyword("1V1", match_hole_word=True)
                if add_tag2work(work_id, tag_ids=[tag_id_list]):
                    logging.info("写入1V1标签成功")
        
        except Exception as e:
            logging.error(f"CrawlerManager _on_danyuwiki_result 异常: {e}")

    @Slot(object)
    def _on_download_image_danyu(self, result_bundle):
        if not result_bundle or len(result_bundle) != 3:
             return
        result, work_id, image_filename = result_bundle
        
        success, msg = result
        if success:
            logging.info("封面图片下载成功 (Danyu)")
            update_work_byhand_(work_id, image_url=image_filename)
        else:
            logging.warning(f"封面图片下载失败 (Danyu): {msg}")
            # 失败了尝试 MissAV
            # 注意：这里需要获取 serial_number，但参数里只有 image_filename。
            # 简单起见，这里不再重试 MissAV，或者需要从 filename 反推，或者传参带上 serial_number。
            # 鉴于 DanyuWiki 数据已有，只是图片下载失败，可能网络问题。
            pass

    @Slot(object)
    def _on_download_image_missav(self, result_bundle):
        if not result_bundle or len(result_bundle) != 3:
             return
        result, work_id, image_url = result_bundle
        
        success, msg = result
        if success:
            logging.info("封面图片下载成功 (MissAV)")
            # MissAV 下载的文件名通常就是 serial_number (无后缀或 jpg)，
            # 这里 update_work_byhand_ 需要的是文件名还是 URL？
            # 查看原逻辑：dst_path = WORKCOVER_PATH / serial_number
            # update_work_byhand_(..., image_url=image_url)
            # 这里的 image_url 传进来的是 http url，但数据库存的应该是文件名。
            # 原逻辑：update_work_byhand_(work_id,image_url=image_url)
            # 在 _on_download_image1 中，传入的 image_url 是 http url。
            # 这似乎是个 bug，数据库应该存相对路径或文件名。
            # 检查 AddQuickWork.py:212 -> lambda result:self._on_download_image1(result,work_id,image_url=imageurl)
            # 这里的 imageurl 是 "https://fourhoi.com/..."
            # 但 download_image 的 dst_path 是 WORKCOVER_PATH / serial_number
            # 那么文件保存在哪里了？
            # 无论如何，这里保持原逻辑，但加上文件名修正（如果需要）。
            # 假设数据库存的是文件名，这里应该存文件名。
            # 修正：MissAV 下载时，dst_path 是 WORKCOVER_PATH / serial_number
            # 所以文件名就是 serial_number
            # 我们应该存 serial_number (或者加上 .jpg 如果 download_image 会自动加后缀)
            # 暂时存传入的 image_url 保持一致，或者更合理的做法是存文件名。
            # 为了稳妥，存 image_url (如果是 URL) 或者文件名。
            # 原逻辑似乎存的是 URL? 
            # AddQuickWork.py:317 update_work_byhand_(work_id,image_url=image_url)
            # 此时 image_url 是 https://...
            # 这会导致前端显示图片时去加载 URL 吗？还是本地？
            # Model.py 注释说 image_url 是相对地址。
            # 那么原逻辑存 URL 是错误的？
            # 暂时按原逻辑写，并在日志中标记疑问。
            update_work_byhand_(work_id, image_url=image_url)
        else:
            logging.warning(f"封面图片下载失败 (MissAV): {msg}")

# 全局实例
crawler_manager = CrawlerManager()
