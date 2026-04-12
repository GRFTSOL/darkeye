import json
import logging
import traceback
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import QObject, QThreadPool

from config import get_translation_engine
from controller.global_signal_bus import global_signals
from core.crawler.worker import Worker, wire_worker_finished
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
from core.database.query.work_completeness import read_work_completeness_flags
from core.database.update import update_work_byhand_
from core.schema.model import CrawledWorkData
from utils.utils import text2tag_id_list, translate_text_sync


def _dispatch_minnano_actress_update_via_browser(actress_id: int, jp_name: str) -> bool:
    """GET /api/v1/actress/ 同步拉取 minnano 并写库；成功表示数据已持久化。"""
    from core.crawler.actress import fetch_and_persist_actress_minnano_worker
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


def _want_field(selected_fields: set[str] | None, field: str) -> bool:
    return selected_fields is None or field in selected_fields


@dataclass
class _PersistJobResult:
    """后台持久化完成后的摘要；主线程据此发信号并起封面下载。"""

    with_gui: bool
    work: CrawledWorkData
    selected_fields: set[str] | None
    gui_payload: dict | None = None
    completeness_flags: dict | None = None
    work_id: int | None = None


def _run_persistence_job(
    work: CrawledWorkData,
    withGUI: bool,
    selected_fields: set[str] | None,
) -> _PersistJobResult:
    """翻译 + 数据库写入；在线程池线程中执行（可安全使用 ``submit_db_raw().result()``）。"""
    apply_title_story_translation(work)
    sf = set(selected_fields) if selected_fields else None
    du = DataUpdate.__new__(DataUpdate)
    du.work = work
    du.manager = None
    du.withGUI = withGUI
    du.selected_fields = sf
    du.work_id = None
    if withGUI:
        submit_db_raw(lambda: du._prepare_entities_and_relations_db()).result()
        gui_payload = {
            "serial_number": du.work.serial_number,
            "director": du.work.director,
            "release_date": du.work.release_date,
            "runtime": du.work.runtime,
            "cn_title": du.work.cn_title,
            "jp_title": du.work.jp_title,
            "cn_story": du.work.cn_story,
            "jp_story": du.work.jp_story,
            "tag_id_list": du.tag_id_list,
            "actress_list": du.actress_ids,
            "actor_list": du.actor_ids,
            "maker": du.maker_id,
            "label": du.label_id,
            "series": du.series_id,
            "fanart": du.work.fanart_url_list,
        }
        return _PersistJobResult(
            with_gui=True,
            work=work,
            selected_fields=sf,
            gui_payload=gui_payload,
            work_id=du.work_id,
        )
    flags = submit_db_raw(lambda: du._prepare_and_insert_work_non_gui()).result()
    return _PersistJobResult(
        with_gui=False,
        work=work,
        selected_fields=sf,
        completeness_flags=flags if isinstance(flags, dict) else None,
        work_id=du.work_id,
    )


def _apply_persist_result_on_main(manager: QObject | None, result: object) -> None:
    if not isinstance(result, _PersistJobResult):
        logging.error("作品持久化后台任务失败或返回异常")
        return
    if result.with_gui:
        if result.gui_payload is not None:
            global_signals.guiUpdate.emit(result.gui_payload)
    else:
        serial_norm = (result.work.serial_number or "").strip()
        if serial_norm and isinstance(result.completeness_flags, dict):
            global_signals.workCrawlCompleteness.emit(
                serial_norm, result.completeness_flags
            )
    schedule_cover_download(
        manager,
        result.work,
        result.with_gui,
        result.selected_fields,
        result.work_id,
    )


def schedule_data_update(
    manager: QObject | None,
    work: CrawledWorkData,
    withGUI: bool,
    selected_fields: set[str] | None = None,
) -> None:
    """将翻译与入库整段投递到持久化线程池；主线程仅收信号并启动封面下载。"""
    pool = getattr(manager, "_persist_pool", None)
    if pool is None:
        pool = QThreadPool.globalInstance()
    worker = Worker(_run_persistence_job, work, withGUI, selected_fields)
    wire_worker_finished(
        worker, lambda r, m=manager: _apply_persist_result_on_main(m, r)
    )
    pool.start(worker)


def _cover_download_finished(
    success: bool,
    temp_path: str,
    image_filename: str,
    work_id: int | None,
    work: CrawledWorkData,
    withGUI: bool,
    selected_fields: set[str] | None,
) -> None:
    if success:
        if withGUI:
            global_signals.downloadSuccess.emit(temp_path)
        else:
            insert_cover_async(
                temp_path, image_filename, work_id, work.serial_number, selected_fields
            )


def schedule_cover_download(
    manager: QObject | None,
    work: CrawledWorkData,
    withGUI: bool,
    selected_fields: set[str] | None,
    work_id: int | None,
) -> None:
    """在需要封面且存在 ``manager`` 时启动顺序封面下载。

    由主线程在持久化后台跑完后调用（须能安全创建 ``SequentialDownloader``）。
    在临时目录生成唯一文件名，用 ``work.cover_url_list`` 依次尝试下载；
    完成后走 ``_cover_download_finished``：GUI 发 ``downloadSuccess``，
    非 GUI 则 ``insert_cover_async`` 落盘并更新库。

    Args:
        manager: 爬虫管理器（提供下载线程池与 relay 线程归属）；缺省则无法起任务。
        work: 含番号与封面 URL 列表。
        withGUI: 是否走界面预览分支（与 ``SequentialDownloader`` 行为一致）。
        selected_fields: 为 ``None`` 表示全字段；否则仅当含 ``cover`` 时才下载。
        work_id: 非 GUI 入库后的作品 id，供封面写入后更新 completeness。
    """
    from config import TEMP_PATH

    image_filename = work.serial_number.strip().upper() + ".jpg"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst_name = f"image_{timestamp}.jpg"
    TEMP_PATH.mkdir(parents=True, exist_ok=True)
    temp_path = Path(TEMP_PATH) / dst_name

    if manager and _want_field(selected_fields, "cover"):
        from core.crawler.sequential_download import SequentialDownloader

        task_id = work.serial_number
        total_steps = len(work.cover_url_list or [])
        pool = getattr(manager, "_download_pool", None)
        downloader = SequentialDownloader(
            manager,
            withGUI,
            task_id=task_id,
            total=total_steps,
            thread_pool=pool,
        )
        downloader.finished.connect(
            lambda s, r, wf=work_id, w=work, wg=withGUI, sf=selected_fields: _cover_download_finished(
                s, r, image_filename, wf, w, wg, sf
            )
        )
        downloader.start(work.cover_url_list, temp_path, image_filename)
    elif _want_field(selected_fields, "cover"):
        logging.error("DataUpdate missing manager, cannot start downloader")


def insert_cover_async(
    temp_path: str,
    image_filename: str,
    work_id: int | None,
    serial_number: str,
    selected_fields: set[str] | None,
) -> None:
    """封面落盘与库更新入队；完成后再发 completeness（不阻塞调用线程）。"""
    from core.database.insert import rename_save_image

    def _go():
        rename_save_image(temp_path, image_filename, "cover")
        if work_id is not None and _want_field(selected_fields, "cover"):
            update_work_byhand_(work_id, image_url=image_filename)
        if work_id is not None:
            return read_work_completeness_flags(work_id)
        return None

    def _on_db_done(fut):
        try:
            flags = fut.result()
        except Exception as e:
            logging.error("insert_cover_async 数据库回调失败: %s", e)
            return
        serial_norm = (serial_number or "").strip()
        if serial_norm and isinstance(flags, dict):
            global_signals.workCrawlCompleteness.emit(serial_norm, flags)

    fut = submit_db_raw(_go)
    fut.add_done_callback(_on_db_done)


class DataUpdate:
    """把爬虫结果写入库或推给 GUI；须通过 ``schedule_data_update`` 调度，勿直接构造。"""

    def _want(self, field: str) -> bool:
        return _want_field(self.selected_fields, field)

    def _prepare_and_insert_work_non_gui(self):
        """无 GUI 时：实体解析 + 作品行写入，单次入队。"""
        self._prepare_entities_and_relations_db()
        self._insert2db()
        return read_work_completeness_flags(self.work_id)

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
