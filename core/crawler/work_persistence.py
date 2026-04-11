import json
import logging
import traceback
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import QObject

from config import get_translation_engine
from controller.global_signal_bus import global_signals
from core.database.db_queue import submit_db_raw
from core.database.insert import (
    InsertNewWork,
    InsertNewActress,
    InsertNewActor,
    add_tag2work,
    insert_tag,
)
from core.database.query import (
    exist_actress,
    exist_actor,
    get_tagid_by_keyword,
    get_workid_by_serialnumber,
)
from core.database.update import update_work_byhand_
from core.schema.model import CrawledWorkData
from utils.utils import text2tag_id_list, translate_text_sync


def _dispatch_minnano_actress_update_via_browser(actress_id: int, jp_name: str) -> bool:
    """GET /api/v1/actress/ 同步拉取 minnano 并写库；成功表示数据已持久化。"""
    from core.crawler.minnanoav import fetch_and_persist_actress_minnano_worker
    from core.database.query import exist_minnao_id

    raw_mid = exist_minnao_id(actress_id)
    mid = str(raw_mid).strip() if raw_mid is not None and str(raw_mid).strip() else None
    kind, _payload = fetch_and_persist_actress_minnano_worker(jp_name, actress_id, mid)
    return kind == "success"


def apply_title_story_translation(work: CrawledWorkData) -> None:
    """按引擎与空中文条件补全 ``cn_title`` / ``cn_story``（与旧多源合并后翻译规则一致）。"""
    try:
        engine = get_translation_engine()
        force_translate = engine == "llm"
        if (work.jp_title or "").strip() != "" and (
            force_translate or not (work.cn_title or "").strip()
        ):
            work.cn_title = translate_text_sync(work.jp_title, fallback="empty")
        if (work.jp_story or "").strip() != "" and (
            force_translate or not (work.cn_story or "").strip()
        ):
            work.cn_story = translate_text_sync(work.jp_story, fallback="empty")
    except Exception as e:
        logging.warning(
            "DataUpdate 标题/简介翻译失败，使用原文: %s\n%s",
            e,
            traceback.format_exc(),
        )


class DataUpdate:
    """把爬虫结果写入库或推给 GUI；封面通过 SequentialDownloader 在主线程链路上触发。"""

    def __init__(
        self,
        data: CrawledWorkData,
        manager: QObject = None,
        withGUI: bool = False,
        selected_fields: set[str] | None = None,
    ):
        self.work = data
        self.manager = manager
        self.withGUI = withGUI
        self.selected_fields: set[str] | None = (
            set(selected_fields) if selected_fields else None
        )
        self.work_id = None
        apply_title_story_translation(self.work)
        if withGUI:
            submit_db_raw(lambda: self._prepare_entities_and_relations_db()).result()
            global_signals.guiUpdate.emit(
                {
                    "serial_number": self.work.serial_number,
                    "director": self.work.director,
                    "release_date": self.work.release_date,
                    "runtime": self.work.runtime,
                    "cn_title": self.work.cn_title,
                    "jp_title": self.work.jp_title,
                    "cn_story": self.work.cn_story,
                    "jp_story": self.work.jp_story,
                    "tag_id_list": self.tag_id_list,
                    "actress_list": self.actress_ids,
                    "actor_list": self.actor_ids,
                    "maker": self.maker_id,
                    "label": self.label_id,
                    "series": self.series_id,
                    "fanart": self.work.fanart_url_list,
                }
            )
        else:
            submit_db_raw(lambda: self._prepare_and_insert_work_non_gui()).result()
            # self._prepare_and_insert_work_non_gui()
        self._schedule_cover_download()

    def __del__(self):
        logging.info("DataUpdate 实例已成功销毁，内存已释放")

    def _want(self, field: str) -> bool:
        return self.selected_fields is None or field in self.selected_fields

    def _prepare_and_insert_work_non_gui(self):
        """无 GUI 时：实体解析 + 作品行写入，单次入队。"""
        self._prepare_entities_and_relations_db()
        self._insert2db()

    def _prepare_entities_and_relations_db(self):
        """标签/演员/片商等解析与插入；仅在数据库队列线程内调用。"""
        self.tag_id_list = []
        if self._want("tag"):
            tag_id_list = text2tag_id_list(self.work.jp_title)
            if len(self.work.actor_list) == 1 and len(self.work.actress_list) == 1:
                tag_id_list.append(get_tagid_by_keyword("1V1", match_hole_word=True))

            added_tag = False
            if self.work.tag_list:
                for genre in self.work.tag_list:
                    tag_id = get_tagid_by_keyword(genre, match_hole_word=True)
                    if tag_id:
                        tag_id_list.append(tag_id)
                    else:
                        success, e, tag_id = insert_tag(
                            genre, 11, "#cccccc", "", None, []
                        )
                        if success:
                            added_tag = True
                            tag_id_list.append(tag_id)
            self.tag_id_list = tag_id_list
            if added_tag:
                global_signals.tagDataChanged.emit()

        self.actress_ids = []
        if self._want("actress"):
            actress_list = self.work.actress_list
            for actress in actress_list:
                id = exist_actress(actress)
                if id is None:
                    if InsertNewActress(actress, actress):
                        logging.info("添加女优成功:%s", actress)
                        id = exist_actress(actress)
                        self.actress_ids.append(id)
                        global_signals.actressDataChanged.emit()
                        # 自动调用爬虫去更新女优
                        from PySide6.QtCore import QThreadPool

                        from core.crawler.worker import Worker, wire_worker_finished

                        worker = Worker(
                            _dispatch_minnano_actress_update_via_browser, id, actress
                        )
                        wire_worker_finished(
                            worker,
                            lambda ok: (
                                global_signals.actressDataChanged.emit() if ok else None
                            ),
                        )
                        QThreadPool.globalInstance().start(worker)
                else:
                    self.actress_ids.append(id)

        self.actor_ids = []
        if self._want("actor"):
            actor_list = self.work.actor_list
            for actor in actor_list:
                id = exist_actor(actor)
                if id is None:
                    if InsertNewActor(actor, actor):
                        logging.info("添加男优成功:%s", actor)
                        id = exist_actor(actor)
                        self.actor_ids.append(id)
                        global_signals.actorDataChanged.emit()
                else:
                    self.actor_ids.append(id)

        from core.database.query.work import (
            get_maker_id_by_name,
            get_label_id_by_name,
            get_series_id_by_name,
        )
        from core.database.insert import InsertNewMaker, InsertNewLabel, InsertNewSeries

        self.maker_id = None
        maker_name = (self.work.maker or "").strip()
        if self._want("maker") and maker_name:
            maker_id = get_maker_id_by_name(maker_name)
            if maker_id is None:
                maker_id = InsertNewMaker(maker_name)
                if maker_id is None:
                    logging.error("插入新的片商失败:%s", maker_name)
                    return
                logging.info("插入新的片商:%s,maker_id:%s", maker_name, maker_id)
                global_signals.makerDataChanged.emit()
            else:
                logging.info("片商已存在:%s,maker_id:%s", maker_name, maker_id)
            self.maker_id = maker_id

        self.label_id = None
        label_name = (self.work.label or "").strip()
        if self._want("label") and label_name:
            label_id = get_label_id_by_name(label_name)
            if label_id is None:
                label_id = InsertNewLabel(label_name)
                if label_id is None:
                    logging.error("插入新的厂牌失败:%s", label_name)
                    return
                logging.info("插入新的厂牌:%s,label_id:%s", label_name, label_id)
                global_signals.labelDataChanged.emit()
            else:
                logging.info("厂牌已存在:%s,label_id:%s", label_name, label_id)
            self.label_id = label_id

        self.series_id = None
        series_name = (self.work.series or "").strip()
        if self._want("series") and series_name:
            series_id = get_series_id_by_name(series_name)
            if series_id is None:
                series_id = InsertNewSeries(series_name)
                if series_id is None:
                    logging.error("插入新的系列失败:%s", series_name)
                    return
                logging.info("插入新的系列:%s,series_id:%s", series_name, series_id)
                global_signals.seriesDataChanged.emit()
            else:
                logging.info("系列已存在:%s,series_id:%s", series_name, series_id)
            self.series_id = series_id

        self.fanart_json = None
        if self._want("fanart"):
            raw = self.work.fanart_url_list or []
            items: list[dict] = []
            for x in raw:
                if isinstance(x, str) and x.strip():
                    items.append({"url": x.strip(), "file": ""})
                elif isinstance(x, dict):
                    u = (x.get("url") or "").strip()
                    if u:
                        items.append({"url": u, "file": (x.get("file") or "").strip()})
            if items:
                self.fanart_json = json.dumps(items, ensure_ascii=False)

    def _schedule_cover_download(self):
        from config import TEMP_PATH

        image_filename = (
            self.work.serial_number.strip().upper() + ".jpg"
        )  # 这个图片就番号.jpg就行了

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst_name = f"image_{timestamp}.jpg"
        TEMP_PATH.mkdir(parents=True, exist_ok=True)
        temp_path = Path(TEMP_PATH) / dst_name

        if self.manager and self._want("cover"):
            from core.crawler.cover_download import SequentialDownloader

            task_id = self.work.serial_number
            total_steps = len(self.work.cover_url_list or [])
            pool = getattr(self.manager, "_download_pool", None)
            downloader = SequentialDownloader(
                self.manager,
                self.withGUI,
                task_id=task_id,
                total=total_steps,
                thread_pool=pool,
            )
            downloader.finished.connect(
                lambda s, r: self._on_download_finished(s, r, image_filename)
            )
            downloader.start(self.work.cover_url_list, temp_path, image_filename)
        elif self._want("cover"):
            logging.error("DataUpdate missing manager, cannot start downloader")

    def _on_download_finished(self, success, temp_path, image_filename):
        if success:
            if self.withGUI:
                global_signals.downloadSuccess.emit(temp_path)
            else:
                self.insert_cover(temp_path, image_filename)

    def _insert2db(self):
        self.work_id = get_workid_by_serialnumber(self.work.serial_number)
        if self.work_id is None:
            self.work_id = InsertNewWork(self.work.serial_number)

        update_fields = {}
        if self._want("cn_title"):
            update_fields["cn_title"] = self.work.cn_title
        if self._want("jp_title"):
            update_fields["jp_title"] = self.work.jp_title
        if self._want("cn_story"):
            update_fields["cn_story"] = self.work.cn_story
        if self._want("jp_story"):
            update_fields["jp_story"] = self.work.jp_story
        if self._want("director"):
            update_fields["director"] = self.work.director
        if self._want("release_date"):
            update_fields["release_date"] = self.work.release_date
        if self._want("actor"):
            update_fields["actor_ids"] = self.actor_ids
        if self._want("actress"):
            update_fields["actress_ids"] = self.actress_ids
        if self._want("runtime"):
            update_fields["runtime"] = self.work.runtime
        if self._want("maker"):
            update_fields["maker_id"] = self.maker_id
        if self._want("label"):
            update_fields["label_id"] = self.label_id
        if self._want("series"):
            update_fields["series_id"] = self.series_id
        if self._want("fanart") and getattr(self, "fanart_json", None):
            update_fields["fanart"] = self.fanart_json

        if update_fields:
            update_work_byhand_(self.work_id, **update_fields)
        if self._want("tag"):
            add_tag2work(self.work_id, tag_ids=self.tag_id_list)

        global_signals.workDataChanged.emit()

    def insert_cover(self, temp_path, image_filename):
        from core.database.insert import rename_save_image

        def _go():
            rename_save_image(temp_path, image_filename, "cover")
            if self.work_id is not None and self._want("cover"):
                update_work_byhand_(self.work_id, image_url=image_filename)

        submit_db_raw(_go).result()
