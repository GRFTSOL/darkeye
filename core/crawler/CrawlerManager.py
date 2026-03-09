import logging
import random
import asyncio
import traceback
from PySide6.QtCore import QObject, Signal, QThreadPool, Slot, Qt,QTimer
from core.crawler.Worker import Worker
from typing import Dict, Optional
from collections import deque
from utils.utils import timeit
from core.database.query import exist_actress, exist_actor, get_tagid_by_keyword
from core.database.update import update_work_byhand_
from core.schema.model import CrawledWorkData
from utils.utils import translate_text_sync, text2tag_id_list
from core.database.insert import InsertNewWork, InsertNewActress, InsertNewActor, add_tag2work,insert_tag
from core.database.query import get_tagid_by_keyword,get_workid_by_serialnumber
from controller.GlobalSignalBus import global_signals

class CrawlerTask:
    def __init__(self, serial_number, sources=["javlib", "javdb","fanza","javtxt","avdanyuwiki"],withGUI=False):
        self.serial:str = serial_number #任务号
        self.pending_sources:set[str] = set(sources) #分爬虫
        self.results:Dict[str, dict] = {} # 存储每个源的结果
        self.withGUI=withGUI # 是否经过GUI确认，默认直接写入数据库

class ResultRelay(QObject):
    '''
    结果中继类，用于将从不同爬虫获取的结果传递给CrawlerManager2
    '''
    def __init__(self, manager, source, serial):
        super().__init__()
        self._manager = manager
        self._source = source
        self._serial = serial
    @Slot(object)
    def handle(self, result):
        self._manager.on_result_received(self._source, self._serial, result)

class MergeRelay(QObject):
    '''
    合并结果中继类，用于将合并结果传递给CrawlerManager2
    '''
    def __init__(self, manager, serial):
        super().__init__()
        self._manager = manager
        self._serial = serial
    @Slot(object)
    def handle(self, final_data):
        self._manager.on_merge_finished(self._serial, final_data)

class CrawlerManager2(QObject):
    _instance = None
    task_finished = Signal(str, dict)
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(CrawlerManager2, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        super().__init__()
        # 确保初始化只执行一次
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.tasks:Dict[str, CrawlerTask]= {} # serial -> CrawlerTask
            self._relays:Dict[tuple, QObject] = {}
            self._merge_relays:Dict[str, QObject] = {} # serial -> MergeRelay
            
            
            # 任务队列系统
            self.request_queue = deque()
            self.schedule_timer = QTimer(self)
            self.schedule_timer.setSingleShot(True)
            self.schedule_timer.timeout.connect(self._on_schedule_tick)
            self.last_schedule_time = 0 # 记录上次调度时间
            from server.bridge import bridge
            # FastAPI/uvicorn 运行在后台线程：这里必须使用 QueuedConnection
            # 否则 slot 可能在服务器线程执行，触发跨线程操作 QTimer 等 Qt 对象而崩溃。
            bridge.captureone_received.connect(
                lambda serial_number: self.start_crawl([serial_number]),
                Qt.ConnectionType.QueuedConnection,
            )

    # 对外只暴露这一个信号：任务彻底完成
    # 这个管理器只针对一种任务，那就是爬取目标番号的相关信息，另外爬女优信息的任务就是另一个爬虫

    # 1. 统一开始入口
    def start_crawl(self, serial_numbers, withGUI=False):
        """将任务加入队列，由调度器接管执行"""
        if isinstance(serial_numbers, str):
            serial_numbers = [serial_numbers]

        existing_serials = {item[0] for item in self.request_queue}

        for serial_number in serial_numbers:
            if serial_number in existing_serials:
                logging.info(f"任务 {serial_number} 已在队列中，跳过重复添加")
                continue
            self.request_queue.append((serial_number, withGUI))
            logging.info(f"任务 {serial_number} 已入队，当前队列长度: {len(self.request_queue)}")
        
        # 如果调度器未在运行（且队列有任务），立即触发第一次（或稍后触发）
        # 这里选择立即触发第一次，后续任务再延迟
        if not self.schedule_timer.isActive() and self.request_queue:
            import time
            now = time.time() * 1000
            elapsed = now - self.last_schedule_time
            min_interval = 12000 # 最小间隔12秒

            if elapsed < min_interval:
                delay = int(min_interval - elapsed)
                self._schedule_next(delay)
            else:
                self._schedule_next(0)

    def _schedule_next(self, delay=None):
        """安排下一次调度"""
        if delay is None:
            delay = random.randint(12000, 18000) # 12-15秒
        self.schedule_timer.start(delay)
        logging.info(f"调度器将在 {delay/1000:.1f} 秒后执行下一个任务")

    def _on_schedule_tick(self):
        """调度器心跳回调"""
        if not self.request_queue:
            logging.info("队列为空，调度器停止")
            return
        
        # 更新最后调度时间
        import time
        self.last_schedule_time = time.time() * 1000

        # 取出并执行任务
        serial, withGUI = self.request_queue.popleft()
        self._execute_crawl(serial, withGUI)
        
        # 如果队列仍有任务，安排下一次
        if self.request_queue:
            self._schedule_next()
        else:
            logging.info("队列已空，停止后续调度")

    def _execute_crawl(self, serial_number,withGUI=False):
        """真正发起爬虫请求（原start_crawl逻辑）"""
        # 创建任务状态
        task = CrawlerTask(serial_number, ["javlib","javtxt","avdanyuwiki"],withGUI)
        self.tasks[serial_number]= task
        #目前这里开3个线程

        # 统一分发请求
        self._dispatch_request("javlib", serial_number)
        self._dispatch_request("javdb", serial_number)
        self._dispatch_request("fanza", serial_number)
        self._dispatch_request("javtxt", serial_number)
        self._dispatch_request("avdanyuwiki", serial_number)


    # 2. 内部发送逻辑
    def _dispatch_request(self, source, serial):
        if source == "javlib":
            # 正常情况单结果，正确信息
            # NMSL-013测试搜索不到的情况
            # 测试多结果的情况，靠蓝光分开
            # 测试多结果，靠蓝光分不开
            # ABF-017 多结果但是番号重复
            # 遇到5秒盾
            # 遇到点击盾
            # 遇到fanza图片加载不出来的情况，实际可爬，就是图片没用
            # STARS-859这个只有后缀带v的情况
            from core.crawler.javlib import jump_to_javlib
            worker=Worker(lambda:jump_to_javlib(serial))
            relay = ResultRelay(self, "javlib", serial)
            self._relays[("javlib", serial)] = relay
            worker.signals.finished.connect(relay.handle, Qt.ConnectionType.QueuedConnection)
            QThreadPool.globalInstance().start(worker)
        elif source == "fanza":
            pass
        elif source == "javdb":
            pass
        elif source == "javtxt":
            from core.crawler.javtxt import fetch_javtxt_movie_info
            worker=Worker(lambda:fetch_javtxt_movie_info(serial))
            relay = ResultRelay(self, "javtxt", serial)
            self._relays[("javtxt", serial)] = relay
            worker.signals.finished.connect(relay.handle, Qt.ConnectionType.QueuedConnection)
            QThreadPool.globalInstance().start(worker)
        elif source == "avdanyuwiki":
            from core.crawler.avdanyuwiki import SearchInfoDanyukiwi
            worker=Worker(lambda:SearchInfoDanyukiwi(serial))
            relay = ResultRelay(self, "avdanyuwiki", serial)
            self._relays[("avdanyuwiki", serial)] = relay
            worker.signals.finished.connect(relay.handle, Qt.ConnectionType.QueuedConnection)
            QThreadPool.globalInstance().start(worker)
        else:
            pass

    # 3. 统一接收回调
    @timeit
    @Slot(str, str, dict)
    def on_result_received(self, source, serial, data):
        '''这个目前是在主线程接收回调'''
        try:
            task = self.tasks.get(serial)#取这个任务
            if not task: 
                logging.error(f"未找到任务 {serial}")
                return

            # 存结果（Worker 异常时 data 为 None，归一化为 {} 避免 _merge_results 崩溃）
            task.results[source] = data if isinstance(data, dict) else {}
            task.pending_sources.discard(source)
            logging.info(f"已接收 {source} 的结果:\n 剩余待处理: {task.pending_sources}")
            key = (source, serial)
            if key in self._relays:
                del self._relays[key]

            if not task.pending_sources:  # 全部完成，仅在工作线程做合并+翻译；DataUpdate 必须在主线程创建以便下载器信号槽正常
                worker = Worker(lambda: self._do_merge_only(serial))
                worker.signals.finished.connect(
                    self._on_merge_worker_finished,
                    Qt.ConnectionType.QueuedConnection,
                )
                QThreadPool.globalInstance().start(worker)
        except Exception as e:
            logging.error(f"on_result_received 崩溃 [source={source} serial={serial}]: {e}\n{traceback.format_exc()}")

    def _do_merge_only(self, serial: str):
        """在工作线程中执行：合并结果（含同步翻译）。返回 final_data，不创建 DataUpdate。"""
        task = self.tasks.get(serial)
        if not task:
            return None
        return self._merge_results(task.results, serial)

    @Slot(object)
    def _on_merge_worker_finished(self, result):
        """合并工作线程结束后的回调（主线程）：在主线程创建 DataUpdate，保证 SequentialDownloader 与下载完成槽在主线程执行。"""
        try:
            if result is None:
                return
            final_data: CrawledWorkData = result
            serial = final_data.serial_number
            task = self.tasks.get(serial)
            if not task:
                return
            DataUpdate(final_data, self, withGUI=task.withGUI)
        except Exception as e:
            logging.error(f"_on_merge_worker_finished 崩溃: {e}\n{traceback.format_exc()}")

    @timeit
    def _merge_results(self, results:Dict[str, dict],serial:str)-> CrawledWorkData:
        '''合并所有爬虫的结果,返回标准爬虫标准model'''
        #logging.info(f"开始合并结果\n{results}")

        # 防御：Worker 异常时 emit(None)，results 中可能存 None，.get(k, {}) 仍会返回 None
        javlib_result = results.get("javlib") or {}
        javtxt_result = results.get("javtxt") or {}
        avdanyuwiki_result = results.get("avdanyuwiki") or {}
        fanza_result = results.get("fanza") or {}

        release_date=javlib_result.get("release_date", avdanyuwiki_result.get("release_date", ""))

        director=avdanyuwiki_result.get("director", javlib_result.get("director", ""))

        video_length=javlib_result.get("length", avdanyuwiki_result.get("length", ""))
        actress_list=avdanyuwiki_result.get("actress_list") or javlib_result.get("actress") or []

        # 封面的优先级是javlib,avdanyuwiki,missav
        def _urls(x):
            if x is None: return []
            return [x] if isinstance(x, str) else (x if isinstance(x, list) else [])
        cover_list = [u for u in _urls(javlib_result.get("image")) if u and isinstance(u, str)]
        avdanurl = avdanyuwiki_result.get("cover") or ""
        if avdanurl:
            cover_list.append(avdanurl)
        serial_number = self.tasks[serial].serial.lower()
        cover_list.append("https://fourhoi.com/" + serial_number + "/cover-n.jpg")

        tag_list = avdanyuwiki_result.get("tag_list") or []
        genre_jav = javlib_result.get("genre") or []
        genre_raw = (tag_list if isinstance(tag_list, list) else []) + (genre_jav if isinstance(genre_jav, list) else [])
        genre_list = list(set(str(g) for g in genre_raw if g is not None))

        jp_title=javlib_result.get("title", javtxt_result.get("jp_title", ""))  

        work_merge={
            "serial_number": self.tasks[serial].serial,
            "release_date": release_date,
            "director": director,
            "video_length": video_length,
            "actress_list": actress_list,
            "actor_list": avdanyuwiki_result.get("actor_list") or [],
            "genre_list": genre_list,
            "cn_title": javtxt_result.get("cn_title", ""),
            "jp_title": jp_title,
            "cn_story": javtxt_result.get("cn_story", ""),
            "jp_story": javtxt_result.get("jp_story", ""),
            "cover_list": cover_list,
        }
        
        #上面是基本合并，会计算先后的顺序，各项的优先级都是不同的。

        #下面是预处理
        # 空缺的cn_title与cn_story用jp_title与jp_story的翻译
        try:
            if work_merge["cn_title"] == "" and work_merge["jp_title"] != "":
                work_merge["cn_title"] = translate_text_sync(work_merge["jp_title"], fallback="empty")
            if work_merge["cn_story"] == "" and work_merge["jp_story"] != "":
                work_merge["cn_story"] = translate_text_sync(work_merge["jp_story"], fallback="empty")
        except Exception as e:
            logging.warning(f"_merge_results 翻译失败，使用原文: {e}\n{traceback.format_exc()}")

        logging.info(f"基本聚合结果: {work_merge}")

        # vlength 必须为 int，video_length 可能为 "" 或 "120" 等字符串
        try:
            vlength_val = int(work_merge["video_length"]) if work_merge["video_length"] else 0
        except (ValueError, TypeError):
            vlength_val = 0

        crawled_work_data=CrawledWorkData(
            serial_number=work_merge["serial_number"],
            director=work_merge["director"],
            release_date=work_merge["release_date"],
            vlength=vlength_val,
            cn_title=work_merge["cn_title"],
            jp_title=work_merge["jp_title"],
            cn_story=work_merge["cn_story"],
            jp_story=work_merge["jp_story"],
            tag_list=work_merge["genre_list"],
            actress_list=work_merge["actress_list"],
            actor_list=work_merge["actor_list"],
            cover_url_list=work_merge["cover_list"],
        )
        return crawled_work_data
        



class DownloadRelay(QObject):
    '''中继类，防止_merge_results执行完后，下载器被gc回收'''
    def __init__(self, downloader):
        super().__init__()
        self.downloader = downloader
    
    @Slot(object)
    def handle(self, result):
        self.downloader._on_download_result(result)

class SequentialDownloader(QObject):
    '''用于递归的下载图片'''
    finished = Signal(bool, str) # 成功/失败, 最终文件路径/错误信息
    success=Signal(str)

    def __init__(self, manager,withGUI:bool=False):
        super().__init__()
        self.manager = manager
        self.current_worker_id = None
        self._download_in_progress = False
        self.withGUI=withGUI

    def __del__(self):
        logging.info("SequentialDownloader 实例已成功销毁，内存已释放")
        
    def start(self, url_list, save_path,image_filename):
        # 防御性清理：仅当不在下载中时，清掉上一轮遗留 relay
        # （如果仍在下载中就清理，会导致 relay 失去引用而被回收，进而丢回调）
        if (
            not self._download_in_progress
            and self.current_worker_id
            and self.current_worker_id in self.manager._relays
        ):
            del self.manager._relays[self.current_worker_id]
            self.current_worker_id = None

        logging.info(f"开始下载{url_list}到{save_path}")
        self.urls = deque(url_list) #以此建立队列
        self.save_path = save_path
        self.image_filename=image_filename
        self._try_next()

    def _try_next(self):
        if not self.urls:
            self.finished.emit(False, "所有地址均下载失败")
            return
        from core.crawler.download import download_image
        url = self.urls.popleft()
        # 启动 Worker 下载 url ...
        worker = Worker(lambda: download_image(url, self.save_path))
        
        # 使用 Relay 方案
        relay = DownloadRelay(self)
        relay.moveToThread(self.manager.thread()) 
        
        self.current_worker_id = id(worker)
        self.manager._relays[self.current_worker_id] = relay
        self._download_in_progress = True
        
        worker.signals.finished.connect(relay.handle, Qt.QueuedConnection)
        QThreadPool.globalInstance().start(worker)

    @Slot(object)
    def _on_download_result(self, result):
        # 注意：失败会触发 _try_next() 创建新 worker 并覆盖 current_worker_id。
        # 因此必须先捕获“本次回调对应的 worker_id”，并在 finally 中按该 id 清理 relay。
        worker_id = self.current_worker_id
        try:
            if result is None:
                success, e = False, "Unknown Error (None result)"
            else:
                success, e = result

            #logging.info(f"下载结果:{success},{e}")
            if success:
                logging.info(f"成功下载图片到临时地址{self.save_path}")
                # 必须转为str，否则Signal(bool, str)可能无法正确传递Path对象
                self.finished.emit(True, str(self.save_path))
            else:
                self._try_next() # 失败则尝试下一个
                return
        finally:
            # 最后再清理 relay，确保信号发射期间对象存活
            if worker_id and worker_id in self.manager._relays:
                del self.manager._relays[worker_id]
            if self.current_worker_id == worker_id:
                self.current_worker_id = None
                self._download_in_progress = False



class DataUpdate:
    '''数据更新类，用于把爬虫数据更新数据库中的数据，包括直接写入与先在GUI面板中更新'''
    def __init__(self, data: CrawledWorkData, manager: QObject = None, withGUI: bool = False):
        self.work = data
        self.manager = manager
        self.withGUI = withGUI
        self.work_id=None
        # global_signals.request_update_cover.connect(self.insert_cover)
        if withGUI:
            self._update_work()
            #这里把信号传出去给GUI用
            global_signals.gui_update.emit({
                "serial_number":self.work.serial_number,
                "director": self.work.director,
                "release_date": self.work.release_date,
                "vlength": self.work.vlength,
                "cn_title": self.work.cn_title,
                "jp_title": self.work.jp_title,
                "cn_story": self.work.cn_story,
                "jp_story": self.work.jp_story,
                "tag_id_list":self.tag_id_list,
                "actress_list":self.actress_ids,
                "actor_list":self.actor_ids,
            })
        else:
            self._update_work()
            self._insert2db()
    def __del__(self):
        logging.info("DataUpdate 实例已成功销毁，内存已释放")

    def _update_work(self):
        '''数据清洗并写入'''
        # genre_list处理，这个要更改tag系统，包括tag合并与多语言主tag的处理，如果这个系统改完后就可以把多家的tag联系都可以搞定了，
        #从jp_title中提取tag
        tag_id_list = text2tag_id_list(self.work.jp_title)
        if len(self.work.actor_list) == 1 and len(self.work.actress_list) == 1:
            tag_id_list.append(get_tagid_by_keyword("1V1", match_hole_word=True))

        added_tag=False
        if self.work.tag_list:
            for genre in self.work.tag_list:#如果这个有就加
                tag_id=get_tagid_by_keyword(genre,match_hole_word=True)
                if tag_id:
                    tag_id_list.append(tag_id)
                else:
                    success,e,tag_id=insert_tag(genre,11,"#cccccc","",None,[])
                    if success:
                        added_tag=True
                        tag_id_list.append(tag_id)
        self.tag_id_list = tag_id_list
        if added_tag:#有新添加的tag才刷新，否则这东西卡死ui
            from controller.GlobalSignalBus import global_signals
            global_signals.tag_data_changed.emit()
        #logging.info(f"要添加的tag_id_list{tag_id_list}")
        #写入work_tag_relation关系表
        #global_signals.status_msg_changed.emit(f"成功添加tag到{self.work.serial_number}")
        #logging.info(f"成功添加{tag_id_list}到{work_id}")

        # actress_list的处理，新的女优要添加到数据库并触发爬取女优的任务，女优马甲的系统也要更新。
                    #直接写入女优
        actress_list = self.work.actress_list
        self.actress_ids = []
        for actress in actress_list:
            id = exist_actress(actress)
            if id is None:
                if InsertNewActress(actress, actress):
                    logging.info("添加女优成功:%s", actress)
                    id = exist_actress(actress)
                    self.actress_ids.append(id)
                    from controller.GlobalSignalBus import global_signals
                    global_signals.actress_data_changed.emit()
            else:
                self.actress_ids.append(id)

        # actor_list这个没法处理，就是默认添加一个只有姓名的演员
        actor_list = self.work.actor_list
        self.actor_ids = []
        for actor in actor_list:
            id = exist_actor(actor)
            if id is None:
                if InsertNewActor(actor, actor):
                    logging.info("添加男优成功:%s", actor)
                    id = exist_actor(actor)
                    self.actor_ids.append(id)
                    from controller.GlobalSignalBus import global_signals
                    global_signals.actor_data_changed.emit()
            else:
                self.actor_ids.append(id)

        from pathlib import Path
        from config import WORKCOVER_PATH,TEMP_PATH
        from datetime import datetime
        image_filename = self.work.serial_number.strip().lower().replace('-', '') + 'pl.jpg'
        obj_path = WORKCOVER_PATH / image_filename

        #先下载到temp位置
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst_name = f"image_{timestamp}.jpg"  # 直接获取后缀
        TEMP_PATH.mkdir(parents=True, exist_ok=True)#若不存在临时目录，自动创建
        temp_path = Path(TEMP_PATH) / dst_name#这个是个绝对地址

        # 启动 SequentialDownloader 下载图片
        if self.manager:
            downloader = SequentialDownloader(self.manager, self.withGUI)
            # 使用 lambda 明确参数传递，并持有 self 引用
            downloader.finished.connect(lambda s, r: self._on_download_finished(s, r, image_filename))
            downloader.start(self.work.cover_url_list, temp_path, image_filename)
        else:
            logging.error("DataUpdate missing manager, cannot start downloader")

    def _on_download_finished(self, success, temp_path, image_filename):
        if success:
            if self.withGUI:
                #logging.info(f"发射信号给GUI：{temp_path}")
                #logging.info(f"图片文件名：{image_filename}")
                global_signals.download_success.emit(temp_path)
            else:
                self.insert_cover(temp_path, image_filename)

    def _insert2db(self):
        self.work_id=get_workid_by_serialnumber(self.work.serial_number)
        if self.work_id is None:
            self.work_id=InsertNewWork(self.work.serial_number)


        #下面是真正写入数据库的代码
        update_work_byhand_(self.work_id, 
        cn_title=self.work.cn_title, 
        jp_title=self.work.jp_title, 
        cn_story=self.work.cn_story, 
        jp_story=self.work.jp_story,
        director=self.work.director,
        release_date=self.work.release_date,actor_ids=self.actor_ids,
        actress_ids=self.actress_ids
        )
        add_tag2work(self.work_id, tag_ids=self.tag_id_list)

        global_signals.work_data_changed.emit()

    def insert_cover(self,temp_path,image_filename):
        '''图片下载后写入数据库'''
        #logging.info("图片下载后从temp移动到正式文件夹，并写入db")
        from core.database.insert import rename_save_image
        rename_save_image(temp_path,image_filename,"cover")
        if self.work_id is not None:
            update_work_byhand_(self.work_id, image_url=image_filename)

_crawler_manager2: Optional["CrawlerManager2"] = None

def get_manager() -> "CrawlerManager2":
    """获取 CrawlerManager2 单例（惰性初始化）。

    注意：首次创建必须发生在 Qt 主线程（GUI 线程），避免 QObject 线程归属错误。
    """
    global _crawler_manager2
    if _crawler_manager2 is None:
        from PySide6.QtCore import QCoreApplication, QThread

        app = QCoreApplication.instance()
        if app is not None and QThread.currentThread() != app.thread():
            raise RuntimeError("CrawlerManager2 必须在主线程首次初始化（请在 MainWindow show 后调用 get_manager()）")

        _crawler_manager2 = CrawlerManager2()
    return _crawler_manager2