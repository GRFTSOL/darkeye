from PySide6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QLineEdit,
    QTextEdit,
    QSizePolicy,
    QPlainTextEdit,
    QWidget,
    QScrollArea,
    QFrame,
    QMenu,
    QStyle,
    QToolButton,
)
from PySide6.QtCore import (
    Qt,
    QObject,
    Signal,
    Property,
    SignalInstance,
    Slot,
    QThreadPool,
    QTimer,
)
from PySide6.QtGui import QCursor

from ui.myads.pane_widget import PaneWidget
from ui.myads.workspace_manager import WorkspaceManager, Placement, ContentConfig
from ui.widgets.CrawlerToolBox import CrawlerAutoPage
from ui.widgets.crawler_nav_page import CrawlerManualNavPage
import copy
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from enum import Enum


from config import (
    ADD_WORK_WORKSPACE_LAYOUT_PATH,
    FANART_PATH,
    TEMP_PATH,
    WORKCOVER_PATH,
)
from ui.widgets import (
    ActressSelector,
    CompleterLineEdit,
    ActorSelector,
    CoverDropWidget,
)
from ui.widgets.image.FanartStripWidget import FanartStripWidget, LOCAL_ABS_KEY
from ui.widgets.selectors.TagSelector5 import TagSelector5
from core.database.query import (
    get_unique_director,
    get_work_tags,
    get_workinfo_by_workid,
    get_actressid_by_workid,
    get_actorid_by_workid,
    exist_actor,
    get_workid_by_serialnumber,
    exist_actress,
)
from core.database.insert import InsertNewWorkByHand, rename_save_image
from core.database.update import _split_video_url_field, update_work_byhand
from utils.utils import delete_image, mse, play_video, translate_text_sync


from darkeye_ui import LazyWidget
from controller.app_context import get_theme_manager
from controller.message_service import MessageBoxService, IMessageService

from core.crawler.download import download_image_js
from core.crawler.worker import Worker, wire_worker_finished

from ui.navigation.router import Router
from ui.widgets.text.WikiTextEdit import WikiTextEdit
from controller.global_signal_bus import global_signals
from darkeye_ui.components.label import Label
from darkeye_ui.components.input import LineEdit
from darkeye_ui.components.input import PlainTextEdit
from darkeye_ui.components.icon_push_button import IconPushButton
from darkeye_ui.components.button import Button
from darkeye_ui.components.token_spin_box import TokenSpinBox
from ui.widgets.selectors.maker_selector import MakerSelector
from ui.widgets.selectors.label_selector import LabelSelector
from ui.widgets.selectors.series_selector import SeriesSelector
from core.database.db_queue import submit_db_raw
from utils.serial_number import convert_fanza, serial_number_equal


def _download_fanza_pl_cover_via_js(url: str) -> tuple[bool, str, str]:
    """线程池内：用 ``download_image_js`` 拉取 Fanza pl 大图到 ``TEMP_PATH``。

    返回 ``(成功, 绝对路径或空字符串, 错误文案)``。
    """
    save_path = str(TEMP_PATH / f"fanza_pl_{uuid.uuid4().hex}.jpg")
    ok, msg = download_image_js(url, save_path)
    if ok:
        return True, save_path, ""
    return False, "", msg


class ButtonState(Enum):
    NORMAL = 1
    WARNING = 2
    DISABLED = 3


def _property_changed_signal_name(snake_name: str) -> str:
    """serial_number -> serialNumberChanged，与 ViewModel 上 Property 的 notify 信号一致。"""
    head, *rest = snake_name.split("_")
    return head + "".join(s[:1].upper() + s[1:] for s in rest if s) + "Changed"


class Model:
    """纯放数据的model"""

    def __init__(self):
        self._serial_number: str = ""
        self._director: str = ""
        self._release_date: str = ""
        self._runtime: int = 0
        self._notes: str = ""
        self._cn_title: str = ""
        self._cn_story: str = ""
        self._jp_title: str = ""
        self._jp_story: str = ""

        self._cover: str = ""
        self._actress: list[int] = []
        self._actor: list[int] = []
        self._tag: list[int] = []
        self._maker_id: int | None = None
        self._label_id: int | None = None
        self._series_id: int | None = None
        self._fanart: list[dict] = []

    def to_dict(self):
        return {
            "serial_number": self._serial_number,
            "director": self._director,
            "release_date": self._release_date,
            "notes": self._notes,
            "runtime": self._runtime,
            "cn_title": self._cn_title,
            "cn_story": self._cn_story,
            "jp_title": self._jp_title,
            "jp_story": self._jp_story,
            "actress_ids": self._actress,
            "actor_ids": self._actor,
            "tag_ids": self._tag,
            "maker_id": self._maker_id,
            "label_id": self._label_id,
            "series_id": self._series_id,
            "image_url": self._cover,  # 这个的地址应该是一个相对地址
            "fanart": copy.deepcopy(self._fanart),
        }


class ViewModel(QObject):
    """实现数据与视图的双向绑定，这里是数据，使用Property"""

    serialNumberChanged = Signal(str)
    directorChanged = Signal(str)
    releaseDateChanged = Signal(str)
    notesChanged = Signal(str)
    runtimeChanged = Signal(int)

    cnTitleChanged = Signal(str)
    cnStoryChanged = Signal(str)
    jpTitleChanged = Signal(str)
    jpStoryChanged = Signal(str)

    coverChanged = Signal(str)
    actressChanged = Signal("QList<int>")  # 这里不能使用list(int)要么直接list
    actorChanged = Signal("QList<int>")
    tagChanged = Signal("QList<int>")
    makerChanged = Signal(int)
    labelChanged = Signal(int)
    seriesChanged = Signal(int)
    fanartChanged = Signal(list)
    btnStateChanged = Signal(str, ButtonState)

    modifyStateChanged = Signal(str, bool)  # 发出修改什么控件的信号
    workload = Signal(str)  # 发送给view使用
    workInfoReloaded = Signal()

    def __init__(self, model=None, message_service: IMessageService = None):
        super().__init__()
        self.model: Model = model
        self.msg = message_service
        self._changed_flags = {  # 检测内容修改的字典,通过这个控制UI的改变
            "notes": False,
            "release_date": False,
            "director": False,
            "cn_title": False,
            "cn_story": False,
            "jp_title": False,
            "jp_story": False,
            "actress_ids": False,
            "actor_ids": False,
            "tag_ids": False,
            "image_url": False,
            "runtime": False,
            "maker_id": False,
            "label_id": False,
            "series_id": False,
            "fanart": False,
        }
        self._btn_state = {
            "add_work": ButtonState.DISABLED,
            "load": ButtonState.DISABLED,
            "temp_save": ButtonState.DISABLED,
            "temp_load": ButtonState.NORMAL,
        }

    # -------------------- getter / setter --------------------
    def get_serial_number(self) -> str:
        return self.model._serial_number

    def set_serial_number(self, value: str):
        if not value:
            value = ""
        if self.model._serial_number != value.strip().upper():  # 这里全部转成纯大写
            self.model._serial_number = value.strip().upper()
            self.serialNumberChanged.emit(value)

            # 这里写番号转换的函数
            # print("Model updated:", self.model._serial_number)

    def get_director(self) -> str:
        return self.model._director

    def set_director(self, value: str):
        if not value:
            value = ""
        if self.model._director != value.strip():
            self.model._director = value.strip()
            self.directorChanged.emit(value)

    def get_release_date(self) -> str:
        return self.model._release_date

    def set_release_date(self, value: str):
        if not value:
            value = ""
        if self.model._release_date != value.strip():
            self.model._release_date = value.strip()
            self.releaseDateChanged.emit(value)
            # print("Model updated:", self.model._release_date)

    def get_runtime(self) -> int:
        return self.model._runtime

    def set_runtime(self, value: int):
        value = int(value) if value not in (None, "") else 0
        if self.model._runtime != value:
            self.model._runtime = value
            self.runtimeChanged.emit(value)
            # print("Model runtime updated:", self.model._runtime)

    def get_notes(self) -> str:
        return self.model._notes

    def set_notes(self, value: str):
        if not value:
            value = ""
        if self.model._notes != value.strip():
            self.model._notes = value.strip()
            self.notesChanged.emit(value)
            # print("Model Story updated:", self.model._notes)

    def get_cn_title(self) -> str:
        return self.model._cn_title

    def set_cn_title(self, value: str):
        if not value:
            value = ""
        if self.model._cn_title != value.strip():
            self.model._cn_title = value.strip()
            self.cnTitleChanged.emit(value)
            # print("cn_title updated:", self.model._cn_title)

    def get_cn_story(self) -> str:
        return self.model._cn_story

    def set_cn_story(self, value: str):
        if not value:
            value = ""
        if self.model._cn_story != value.strip():
            self.model._cn_story = value.strip()
            self.cnStoryChanged.emit(value)
            # print("cn_story updated:", self.model._cn_story)

    def get_jp_title(self) -> str:
        return self.model._jp_title

    def set_jp_title(self, value: str):
        if not value:
            value = ""
        if self.model._jp_title != value.strip():
            self.model._jp_title = value.strip()
            self.jpTitleChanged.emit(value)
            # print("jp_title updated:", self.model._jp_title)

    def get_jp_story(self) -> str:
        return self.model._jp_story

    def set_jp_story(self, value: str):
        if not value:
            value = ""
        if self.model._jp_story != value.strip():
            self.model._jp_story = value.strip()
            self.jpStoryChanged.emit(value)
            # print("jp_story updated:", self.model._jp_story)

    def get_cover(self) -> str:
        return self.model._cover

    def set_cover(self, value: str):
        if not value:
            value = ""
        if self.model._cover != value:
            logging.debug(f"cover原地址为{self.model._cover}")
            self.model._cover = value
            self.coverChanged.emit(value)
            logging.debug(f"cover地址改变为{value}")

    def get_actress(self) -> list[int]:
        return self.model._actress

    def set_actress(self, value: list[int]):
        if (
            self.model._actress != value
        ):  # 考虑要不要集合操作，不过问题不大，存的时候会有集合操作
            self.model._actress = value
            self.actressChanged.emit(value)
            # print("Model updated:", self.model._actress)

    def get_actor(self) -> list[int]:
        return self.model._actor

    def set_actor(self, value: list[int]):
        if self.model._actor != value:
            self.model._actor = value
            self.actorChanged.emit(value)
            # print("Model updated:", self.model._actor)

    def get_tag(self) -> list[int]:
        return self.model._tag

    def set_tag(self, value: list[int]):
        """设置tag的id列表"""
        if self.model._tag != value:
            self.model._tag = value
            self.tagChanged.emit(value)
            # print("Model updated _tag:", self.model._tag)

    def get_maker(self) -> int | None:
        return self.model._maker_id

    def set_maker(self, value: int | None):
        maker_id = int(value) if value not in (None, "") else None
        if self.model._maker_id != maker_id:
            self.model._maker_id = maker_id
            self.makerChanged.emit(maker_id if maker_id is not None else 0)

    def get_label(self) -> int | None:
        return self.model._label_id

    def set_label(self, value: int | None):
        label_id = int(value) if value not in (None, "") else None
        if self.model._label_id != label_id:
            self.model._label_id = label_id
            self.labelChanged.emit(label_id if label_id is not None else 0)

    def get_series(self) -> int | None:
        return self.model._series_id

    def set_series(self, value: int | None):
        series_id = int(value) if value not in (None, "") else None
        if self.model._series_id != series_id:
            self.model._series_id = series_id
            self.seriesChanged.emit(series_id if series_id is not None else 0)

    def get_fanart(self) -> list[dict]:
        return copy.deepcopy(self.model._fanart)

    def set_fanart(self, value: list[dict]):
        new_v = copy.deepcopy(value)
        if self._fanart_signature(new_v) == self._fanart_signature(self.model._fanart):
            return
        self.model._fanart = new_v
        self.fanartChanged.emit(copy.deepcopy(new_v))

    def _fanart_signature(self, items: list[dict]) -> str:
        rows: list[dict] = []
        for d in items:
            rows.append(
                {
                    "u": (d.get("url") or "").strip(),
                    "f": (d.get("file") or "").strip(),
                    "p": bool(d.get(LOCAL_ABS_KEY)),
                }
            )
        return json.dumps(rows, sort_keys=True, ensure_ascii=False)

    def _fanart_db_signature_from_raw(self, raw: str | None) -> str:
        if not raw:
            return "[]"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return "[]"
        rows: list[dict] = []
        for x in parsed:
            if isinstance(x, dict):
                rows.append(
                    {
                        "u": (x.get("url") or "").strip(),
                        "f": (x.get("file") or "").strip(),
                        "p": False,
                    }
                )
        return json.dumps(rows, sort_keys=True, ensure_ascii=False)

    def set_btn_state(self, key: str, value: bool):
        if key not in self._btn_state:
            raise KeyError(f"Unknown state key: {key}")
        if self._btn_state[key] != value:
            self._btn_state[key] = value
            self.btnStateChanged.emit(key, value)
            # logging.debug("更改按钮状态")

    def _noop_get(self):
        return None

    def set_state(self, key: str, value: bool):
        if key not in self._changed_flags:
            raise KeyError(f"Unknown state key: {key}")

        v = bool(value)
        if self._changed_flags[key] != v:
            self._changed_flags[key] = v
            self.modifyStateChanged.emit(key, v)

    # -------------------- Property --------------------
    modify_state = Property(str, _noop_get, set_state, notify=modifyStateChanged)

    btn_state = Property(str, _noop_get, set_btn_state, notify=btnStateChanged)

    serial_number = Property(
        str, get_serial_number, set_serial_number, notify=serialNumberChanged
    )
    director = Property(str, get_director, set_director, notify=directorChanged)
    release_date = Property(
        str, get_release_date, set_release_date, notify=releaseDateChanged
    )
    notes = Property(str, get_notes, set_notes, notify=notesChanged)

    runtime = Property(int, get_runtime, set_runtime, notify=runtimeChanged)

    cn_title = Property(str, get_cn_title, set_cn_title, notify=cnTitleChanged)
    cn_story = Property(str, get_cn_story, set_cn_story, notify=cnStoryChanged)
    jp_title = Property(str, get_jp_title, set_jp_title, notify=jpTitleChanged)
    jp_story = Property(str, get_jp_story, set_jp_story, notify=jpStoryChanged)

    cover = Property(str, get_cover, set_cover, notify=coverChanged)
    actress = Property(list, get_actress, set_actress, notify=actressChanged)
    actor = Property(list, get_actor, set_actor, notify=actorChanged)
    tag = Property(list, get_tag, set_tag, notify=tagChanged)
    maker = Property(int, get_maker, set_maker, notify=makerChanged)
    label = Property(int, get_label, set_label, notify=labelChanged)
    series = Property(int, get_series, set_series, notify=seriesChanged)
    fanart = Property(list, get_fanart, set_fanart, notify=fanartChanged)

    # ----------------------------------------------------------
    #                    提交修改函数
    # ----------------------------------------------------------
    def _finalize_fanart_json(self, items: list[dict]) -> str | None:
        serial_base = self.get_serial_number().lower().replace("-", "")
        out: list[dict] = []
        for entry in copy.deepcopy(items):
            url = (entry.get("url") or "").strip()
            rel = (entry.get("file") or "").strip()
            loc = (entry.get(LOCAL_ABS_KEY) or "").strip()
            if loc and Path(loc).is_file():
                name = f"{serial_base}_fa_{uuid.uuid4().hex[:8]}.jpg"
                rename_save_image(loc, name, "fanart")
                rel = name
            out.append({"url": url, "file": rel})
        out = [
            x
            for x in out
            if (x.get("url") or "").strip() or (x.get("file") or "").strip()
        ]
        if not out:
            return None
        return json.dumps(out, ensure_ascii=False)

    @staticmethod
    def _delete_orphan_fanart_files(
        old_raw: str | None, new_json_str: str | None
    ) -> None:
        old_files: set[str] = set()
        if old_raw:
            try:
                for o in json.loads(old_raw):
                    if isinstance(o, dict):
                        f = (o.get("file") or "").strip()
                        if f:
                            old_files.add(f)
            except json.JSONDecodeError as e:
                logging.warning(
                    "fanart 旧 JSON 无效，跳过孤儿文件解析: %s",
                    e,
                    exc_info=True,
                )
        new_files: set[str] = set()
        if new_json_str:
            try:
                for o in json.loads(new_json_str):
                    if isinstance(o, dict):
                        f = (o.get("file") or "").strip()
                        if f:
                            new_files.add(f)
            except json.JSONDecodeError as e:
                logging.warning(
                    "fanart 新 JSON 无效，跳过孤儿文件解析: %s",
                    e,
                    exc_info=True,
                )
        for f in old_files - new_files:
            for base in (FANART_PATH, WORKCOVER_PATH):
                p = base / f
                if p.is_file():
                    try:
                        delete_image(str(p))
                    except Exception as e:
                        logging.warning("删除 fanart 孤儿文件失败 %s: %s", f, e)
                    break

    def submit(self):
        """手动添加作品记录
        data={
            "serial_number":
            "director":
            "release_date":
            "notes":
            "cn_title":
            "cn_story":
            "jp_title":
            "jp_story":
            "actress_ids":
            "actor_ids":
            "tag_ids":
            "image_url":
            "runtime":
            "maker_id":
        }
        """
        # 获得基本数据
        logging.debug("添加记录")
        data = self.model.to_dict()
        old_fanart_raw: str | None = None
        if self.work_id is not None:
            old_fanart_raw = (
                self.original_work.get("fanart") if self.original_work else None
            )

        fan_items: list[dict] = data.pop("fanart", [])
        data["fanart"] = self._finalize_fanart_json(fan_items)

        image_url = (
            self.get_serial_number().upper() + ".jpg"
        )  # 这个图片就番号.jpg就行了

        if self.get_cover() is None or self.get_cover() == "":
            data["image_url"] = None
        else:
            logging.debug("model内image_url %s", data["image_url"])
            rename_save_image(data["image_url"], image_url, "cover")
            data["image_url"] = image_url

        ok = False
        if self.work_id is not None:  # work已在库中
            ok = self._update_work_and_handle_result(self.work_id, **data)
            self.set_btn_state("add_work", ButtonState.DISABLED)
        else:  # work未在库中,插入新的作品
            ok = self._insert_work_and_handle_result(**data)

        if ok and old_fanart_raw:
            self._delete_orphan_fanart_files(old_fanart_raw, data.get("fanart"))

        self._load_from_db()  # 保存后重新加载一遍

    def _update_work_and_handle_result(self, work_id, **data):
        """更新作品并弹窗"""
        serial_number = data["serial_number"]
        del data["serial_number"]  # 这个字段多余，不要了
        if update_work_byhand(work_id, **data):
            self.msg.show_info("更新作品信息成功", f"番号: {serial_number}")
            logging.info("更新作品成功，番号：%s", serial_number)
            from controller.global_signal_bus import global_signals

            global_signals.workDataChanged.emit()
            return True
        else:
            self.msg.show_warning("更新作品信息失败", f"未知原因")
            logging.warning("更新%s作品信息失败", serial_number)
            return False

    def _insert_work_and_handle_result(self, **data):
        """插入作品并弹窗"""
        serial_number = data["serial_number"]
        if InsertNewWorkByHand(**data):
            self.msg.show_info("添加作品成功", f"番号: {serial_number}")
            from controller.global_signal_bus import global_signals

            global_signals.workDataChanged.emit()  # 发送给那些需要重新加载的东西
            logging.info("添加作品成功，番号：%s", serial_number)
            return True
        else:
            self.msg.show_warning("添加作品失败", "未知原因")
            logging.warning("添加%s作品信息失败", serial_number)
            return False

    # ----------------------------------------------------------
    #                    加载数据
    # ----------------------------------------------------------
    def on_work_selected(self):
        """当选择番号时，核心控制

        包括更新各种控件的状态，空时全部清空
        """
        # 加载进来后要保存原始值

        self._cheakable = False  # 关闭检测

        # 检测空的不能添加
        if self.get_serial_number().strip() == "":
            self._clear_all_info()
            self.set_btn_state("add_work", ButtonState.DISABLED)
            self.set_btn_state("temp_save", ButtonState.DISABLED)  # 关闭临时保存
            self.set_btn_state("load", ButtonState.DISABLED)  # 闭锁加载按钮
            logging.debug("番号为空")
            return

        # 非空，但是番号不在库中
        work_id = submit_db_raw(
            lambda: get_workid_by_serialnumber(self.get_serial_number().strip())
        ).result()
        if work_id is None:
            self.set_btn_state("load", ButtonState.DISABLED)  # 闭锁加载按钮
            self.set_btn_state("temp_save", ButtonState.NORMAL)  # 打开临时加载按钮
            self.work_id = None
            # 这里应该是清空所有的信息面板
            self._clear_all_info()
            self.set_btn_state("add_work", ButtonState.NORMAL)
            self.set_change_widget_default()
            return

        logging.debug("番号在库中")
        # 番号在库中
        self.work_id = work_id
        self.set_btn_state("load", ButtonState.WARNING)  # 打开加载按钮
        self.set_btn_state("temp_save", ButtonState.DISABLED)  # 闭锁临时加载
        self.set_btn_state("add_work", ButtonState.DISABLED)
        self.set_change_widget_default()

    def _load_from_db(self):
        """从数据库内加单个作品的数据"""
        logging.debug(
            "加载作品数据----------------------------------------------------------------"
        )
        self.work_id = submit_db_raw(
            lambda: get_workid_by_serialnumber(self.get_serial_number().strip())
        ).result()
        if self.work_id == None:
            return
        inf = get_workinfo_by_workid(self.work_id)

        # 这里加载图，应用ego filter
        self.workload.emit(f"w{self.work_id}")

        def replace_nan_with_empty(d: dict):
            for k, v in d.items():
                if v is None:
                    d[k] = ""
            return d

        replace_nan_with_empty(inf)

        self._cheakable = False  # 关闭检测

        self.set_release_date(inf["release_date"])
        self.set_director(inf["director"])
        self.set_runtime(inf["runtime"])
        self.set_notes(inf["notes"])
        self.set_cn_title(inf["cn_title"])  # Nano与空值的处理
        self.set_cn_story(inf["cn_story"])
        self.set_jp_title(inf["jp_title"])
        self.set_jp_story(inf["jp_story"])
        self.set_maker(inf.get("maker_id"))
        self.set_label(inf.get("label_id"))
        self.set_series(inf.get("series_id"))

        actress_ids: list = get_actressid_by_workid(self.work_id)
        self.set_actress(actress_ids)
        logging.debug("加载的女优id为：%s", actress_ids)

        actor_ids: list = get_actorid_by_workid(self.work_id)
        self.set_actor(actor_ids)
        logging.debug("加载的男优id为：%s", actor_ids)

        tag_ids = get_work_tags(self.work_id)
        self.set_tag(tag_ids)

        raw_fanart = inf.get("fanart") or ""
        if raw_fanart:
            try:
                parsed = json.loads(raw_fanart)
                self.set_fanart(
                    [
                        {
                            "url": str(x.get("url", "") or ""),
                            "file": str(x.get("file", "") or ""),
                        }
                        for x in parsed
                        if isinstance(x, dict)
                    ]
                )
            except json.JSONDecodeError:
                self.set_fanart([])
        else:
            self.set_fanart([])

        # logging.debug(f"加载的image_url为:{inf['image_url']}")
        if inf["image_url"] is None or inf["image_url"] == "":
            self.set_cover("")
            # logging.debug("封面为空")
        else:
            self.set_cover(str(Path(WORKCOVER_PATH / inf["image_url"])))
        logging.info("加载番号:%s 作品信息", self.get_serial_number())

        # 保存原始的内容为修改模式做比较

        inf["actress_ids"] = actress_ids
        inf["actor_ids"] = actor_ids
        inf["tag_ids"] = tag_ids
        inf["maker_id"] = inf.get("maker_id", None) or None
        inf["label_id"] = inf.get("label_id", None) or None
        inf["series_id"] = inf.get("series_id", None) or None
        self.original_work = inf
        # logging.debug(f"加载的原始内容\n{self.original_work}")

        # 重新信号连接，进入修改模式,关键点就是保存原始内容，重置修改旗子，按钮状态默认不能按

        self._cheakable = True
        # logging.debug("开始修改检测")

        self.set_btn_state("add_work", ButtonState.DISABLED)
        # 样式还原
        self.set_change_widget_default()
        logging.debug("加载信息完成")
        self.workInfoReloaded.emit()

    def _clear_all_info(self):
        """清空所有的面板里的内容除了input_serial_number"""
        self.set_release_date("")
        self.set_director("")
        self.set_runtime(0)
        self.set_notes("")
        self.set_cn_title("")
        self.set_cn_story("")
        self.set_jp_title("")
        self.set_jp_story("")
        self.set_cover("")
        self.set_actress([])
        self.set_actor([])
        self.set_tag([])
        self.set_maker(None)
        self.set_label(None)
        self.set_series(None)
        self.set_fanart([])

    # ----------------------------------------------------------
    #                    检测有无修改并指示
    # ----------------------------------------------------------

    def setup_change_detection(self):
        """为每个控件设置变更检测"""
        self._cheakable = False  # True时开启检测变更
        logging.debug("关闭修改检测")
        # 文本类控件
        self.notesChanged.connect(lambda: self.check_change("notes", self.get_notes()))
        self.releaseDateChanged.connect(
            lambda: self.check_change("release_date", self.get_release_date())
        )
        self.directorChanged.connect(
            lambda: self.check_change("director", self.get_director())
        )

        # 多行文本控件
        self.cnTitleChanged.connect(
            lambda: self.check_change("cn_title", self.get_cn_title())
        )
        self.cnStoryChanged.connect(
            lambda: self.check_change("cn_story", self.get_cn_story())
        )
        self.jpTitleChanged.connect(
            lambda: self.check_change("jp_title", self.get_jp_title())
        )
        self.jpStoryChanged.connect(
            lambda: self.check_change("jp_story", self.get_jp_story())
        )

        # 选择器类控件
        self.actressChanged.connect(
            lambda: self.check_change("actress_ids", self.get_actress())
        )
        self.actorChanged.connect(
            lambda: self.check_change("actor_ids", self.get_actor())
        )
        self.tagChanged.connect(lambda: self.check_change("tag_ids", self.get_tag()))
        self.makerChanged.connect(
            lambda: self.check_change("maker_id", self.get_maker())
        )
        self.labelChanged.connect(
            lambda: self.check_change("label_id", self.get_label())
        )
        self.seriesChanged.connect(
            lambda: self.check_change("series_id", self.get_series())
        )

        # spinbox
        self.runtimeChanged.connect(
            lambda: self.check_change("runtime", self.get_runtime())
        )

        # 图片控件
        self.coverChanged.connect(self.check_image_change)
        self.fanartChanged.connect(self.check_fanart_change)

    @Slot()
    def check_fanart_change(self):
        if not self._cheakable:
            return
        orig_raw = self.original_work.get("fanart") if self.original_work else None
        orig_sig = self._fanart_db_signature_from_raw(
            orig_raw if isinstance(orig_raw, str) else None
        )
        cur_sig = self._fanart_signature(self.get_fanart())
        self.set_state("fanart", orig_sig != cur_sig)
        self.update_button_state()

    @Slot()
    def check_change(self, field, new_value):
        """
        通用字段变更检测方法，用于比较原始值与新值是否发生变化，并更新变更状态标志

        Args:
            field (str): 要检测的字段名（对应self.original_work中的键）
            new_value (Any): 待比较的新值

        Returns:
            None: 结果会直接更新到self.changed_flags字典中

        处理逻辑：
        1. None值特殊处理：直接比较是否相等
        2. 列表类型处理：转换为集合比较元素差异（忽略顺序）
        3. 其他类型：直接值比较
        最终结果会记录在changed_flags字典中并触发按钮状态更新
        """
        if not self._cheakable:
            return
        original_value = self.original_work[field]
        # logging.debug(f"比较字段{field}")
        # 特殊处理None值比较
        if original_value is None or new_value is None:
            self.set_state(field, (original_value != new_value))
        elif isinstance(original_value, list) and isinstance(
            new_value, list
        ):  # 如果是两个列表就是两个集合元素的比较
            self.set_state(field, (set(original_value) != set(new_value)))
        else:
            self.set_state(field, (original_value != new_value))
            # print(original_value)
            # print(new_value)
        # logging.info("检测到内容变更，变更字典为%s",self._changed_flags)
        self.update_button_state()

    @Slot()
    def check_image_change(self):
        """特殊处理图片变更检测"""
        if not self._cheakable:
            return
        if (
            self.original_work["image_url"] is None
            or self.original_work["image_url"] == ""
        ):  # 空的变有的当然直接变更
            self.set_state("image_url", True)
        else:
            flag = (
                mse(
                    str(Path(WORKCOVER_PATH / self.original_work["image_url"])),
                    self.get_cover(),
                )
                != 0
            )
            self.set_state("image_url", flag)
        logging.debug("检测到内容变更，变更字典为%s", self._changed_flags)
        self.update_button_state()

    def update_button_state(self):
        if any(self._changed_flags.values()):
            self.set_btn_state("add_work", ButtonState.WARNING)
        else:
            self.set_btn_state("add_work", ButtonState.DISABLED)

    def set_change_widget_default(self):
        """各种控件状态设置为原始状态"""
        for key in self._changed_flags:
            self.set_state(key, False)

    @Slot()
    def jump_detail_page(self):
        """跳转到显示页面"""
        work_id = submit_db_raw(
            lambda: get_workid_by_serialnumber(self.get_serial_number().strip())
        ).result()
        if work_id:
            # Router.instance().push("work", work_id=work_id)
            Router.instance().push("shelf", work_id=work_id)

    def append_tags(self, tag_list: list[int]):
        """添加tag,不重复"""
        new_tag_list = list(set(self.tag) | set(tag_list))
        self.set_tag(new_tag_list)

    # ----------------------------------------------------------
    #                        翻译函数
    # ----------------------------------------------------------

    @Slot()
    def _trans_title(self):
        """调用google第三方翻译，不稳定，将日文翻译成中文写到框内"""
        worker = Worker(
            lambda: translate_text_sync(self.get_jp_title(), fallback="empty")
        )
        wire_worker_finished(worker, self._on_trans_title)
        QThreadPool.globalInstance().start(worker)

    @Slot()
    def _trans_story(self):
        """调用google第三方翻译，不稳定，将日文翻译成中文写到框内"""
        worker = Worker(
            lambda: translate_text_sync(self.get_jp_story(), fallback="empty")
        )  # 传一个函数名进去
        wire_worker_finished(worker, self._on_trans_story)
        QThreadPool.globalInstance().start(worker)

    @Slot(str)
    def _on_trans_title(self, result: str):
        if result:
            self.set_cn_title(result)
        else:
            self.msg.show_warning("翻译失败", "网络/代理不稳定或触发限流，请稍后重试。")

    @Slot(str)
    def _on_trans_story(self, result: str):
        if result:
            self.set_cn_story(result)
        else:
            self.msg.show_warning("翻译失败", "网络/代理不稳定或触发限流，请稍后重试。")


class AddWorkTabPage3(LazyWidget):
    # 添加作品的窗口
    """现在有两个模式，修改模式，与添加模式，具体的区分是在于番号是否在库内，修改模式就要进行内容修改检测"""

    def __init__(self):
        super().__init__()

    def _build_default_addwork_workspace(self) -> None:
        """默认分割与填充（与首次进入页面时的布局一致）。"""
        w = self._workspace_manager
        root = w.get_root_pane()

        def cfg(slot: str) -> ContentConfig:
            title, widget, closeable = self._addwork_slot_widgets[slot]
            c = w.create_content_config(content_id=f"addwork_{slot}")
            return c.set_window_title(title).set_widget(widget).set_closeable(closeable)

        pane_basic = w.split(root, Placement.Right, ratio=0.7)
        pane_tag = w.split(pane_basic, Placement.Right, ratio=0.25)
        pane_cn_text = w.split(pane_basic, Placement.Bottom, ratio=0.42)
        pane_fanart = w.split(pane_tag, Placement.Bottom, ratio=0.2)
        pane_force = w.split(pane_tag, Placement.Right, ratio=0.5)
        pane_actress = w.split(root, Placement.Bottom, ratio=0.5)
        pane_editor = w.split(pane_force, Placement.Bottom, ratio=0.4)

        w.fill_pane(root, cfg("settings"))
        w.fill_pane(root, cfg("crawler"))
        w.fill_pane(root, cfg("nav"))
        w.fill_pane(root, cfg("cover"))
        w.fill_pane(pane_basic, cfg("basic"))

        w.fill_pane(pane_cn_text, cfg("jp_text"))
        w.fill_pane(pane_cn_text, cfg("cn_text"))
        w.fill_pane(pane_actress, cfg("actor"))
        w.fill_pane(pane_actress, cfg("actress"))
        w.fill_pane(pane_tag, cfg("tag"))
        w.fill_pane(pane_fanart, cfg("fanart"))
        w.fill_pane(pane_force, cfg("force"))
        w.fill_pane(pane_editor, cfg("editor"))

    def _addwork_get_content_descriptor(
        self, pane: PaneWidget, content_id: str
    ) -> dict | None:
        widget = pane.get_content_widget(content_id)
        if widget is None:
            return None
        slot = widget.property("addwork_slot")
        if slot in (None, ""):
            return None
        slot_s = str(slot)
        return {
            "addwork_slot": slot_s,
            "content_id": content_id,
            "title": pane.get_content_title(content_id),
            "closeable": self._workspace_manager.is_content_closeable(content_id),
        }

    def _addwork_content_factory(self, desc: dict) -> ContentConfig | None:
        slot = desc.get("addwork_slot")
        if not slot or slot not in self._addwork_slot_widgets:
            return None
        default_title, widget, default_closeable = self._addwork_slot_widgets[slot]
        title = desc.get("title", default_title)
        content_id = desc.get("content_id", f"addwork_{slot}")
        closeable = desc.get("closeable", default_closeable)
        cfg = self._workspace_manager.create_content_config(content_id=content_id)
        return cfg.set_window_title(title).set_widget(widget).set_closeable(closeable)

    def _on_save_addwork_workspace_layout(self) -> None:
        path = ADD_WORK_WORKSPACE_LAYOUT_PATH
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._workspace_manager.save_layout(
                path,
                get_content_descriptor=self._addwork_get_content_descriptor,
            )
            self.msg.show_info("布局已保存", f"已写入：\n{path}")
        except Exception as e:
            logging.exception("保存添加作品工作区布局失败")
            self.msg.show_warning("保存失败", str(e))

    def _on_restore_initial_addwork_workspace(self) -> None:
        path = ADD_WORK_WORKSPACE_LAYOUT_PATH
        try:
            self._workspace_manager.reset_to_single_empty_pane()
            self._build_default_addwork_workspace()
        except Exception as e:
            logging.exception("恢复添加作品默认工作区失败")
            self.msg.show_warning("恢复失败", str(e))
            return
        try:
            if path.exists():
                path.unlink()
        except OSError as e:
            logging.warning("删除已保存的布局文件失败: %s", e)
        self.msg.show_info(
            "已恢复初始布局",
            "工作区已恢复为默认拆分与标签顺序。\n"
            "若曾保存过布局，已删除保存文件，下次启动也使用默认布局。",
        )

    def _lazy_load(self):
        logging.info("----------加载打开添加/更改作品信息界面----------")

        self.original_work = {}  # 加载后原始的数据，用于检测内容修改
        self.msg = MessageBoxService(self)  # 弹窗服务
        self._fanza_pl_fetching = False
        self.model = Model()
        self.viewmodel = ViewModel(self.model, self.msg)
        self.init_ui()

        self.beaute()
        self.signal_connect()
        self.viewmodel.setup_change_detection()
        self.bind_model()

        # 设置按钮初始的状态

        self.update_commit_btn("add_work", ButtonState.DISABLED)
        self.update_commit_btn("load", ButtonState.DISABLED)
        self._refresh_local_video_button()

    def init_ui(self) -> None:
        from core.database.db_queue import submit_db_raw
        from core.database.query import (
            get_serial_number,
            get_maker_name,
            get_label_name,
            get_series_name,
        )

        # ---------- 控件创建（与原先一致） ----------

        self.coverdroplabel = CoverDropWidget(aspect_ratio=0.7)

        self.label_serial_umber = Label("番      号：")
        self.input_serial_number = CompleterLineEdit(
            lambda: submit_db_raw(get_serial_number).result()
        )

        self.btn_load_form_db = Button("加载")
        self.btn_jump_detail = IconPushButton(icon_name="eye")
        self.label_time = Label("发布日期：")
        self.input_time = LineEdit()
        self.input_time.setPlaceholderText("YYYY-MM-DD")
        self.label_director = Label("导      演：")
        self.input_director = CompleterLineEdit(
            lambda: submit_db_raw(get_unique_director).result()
        )
        self.label_runtime = Label("影片长度：")
        self.input_runtime = TokenSpinBox()
        self.input_runtime.setRange(0, 9999)
        self.input_runtime.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.btn_add_work = Button()
        self.label_cn_title = Label("中文标题")
        self.cn_title = PlainTextEdit()
        self.label_jp_title = Label("日文标题")
        self.jp_title = PlainTextEdit()
        self.label_cn_story = Label("中文剧情")
        self.cn_story = PlainTextEdit()
        self.label_jp_story = Label("日文剧情")
        self.jp_story = PlainTextEdit()
        self.btn_trans_title = IconPushButton(
            icon_name="languages", icon_size=16, out_size=16
        )
        self.btn_trans_title.setToolTip(
            "翻译日文标题成中文并写在「中文标题与剧情」窗格标题框内"
        )
        self.btn_trans_story = IconPushButton(
            icon_name="languages", icon_size=16, out_size=16
        )
        self.btn_trans_story.setToolTip(
            "翻译日文剧情成中文并写在「中文标题与剧情」窗格剧情框内"
        )
        jp_title_label_layout = QHBoxLayout()
        jp_story_label_layout = QHBoxLayout()
        jp_title_label_layout.addWidget(self.label_jp_title)
        jp_title_label_layout.addWidget(self.btn_trans_title)
        jp_story_label_layout.addWidget(self.label_jp_story)
        jp_story_label_layout.addWidget(self.btn_trans_story)

        self.label_maker = Label("片      商：")
        self.input_maker = MakerSelector(submit_db_raw(get_maker_name).result())

        self.label_label = Label("厂      牌：")
        self.input_label = LabelSelector(submit_db_raw(get_label_name).result())

        self.label_series = Label("系      列：")
        self.input_series = SeriesSelector(submit_db_raw(get_series_name).result())

        self.actressselector = ActressSelector()
        self.actorselector = ActorSelector()
        self.tag_selector = TagSelector5()
        self.tag_selector.left_widget.setFixedWidth(140)
        self.tag_selector.left_view.setFixedWidth(116)
        self.tag_selector.btn_expand.click()

        self.forceview = None
        self.forceview_placeholder = Label("正在生成力导向图...")
        self.forceview_placeholder.setAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
        self.viewmodel.workload.connect(self.on_set_directview)

        self.input_notes = WikiTextEdit()
        self.input_notes.set_completer_func(get_serial_number)

        # ---------- 工作区子容器（先于 WorkspaceManager，便于布局序列化） ----------
        # 爬虫区
        self.crawler_auto_page = CrawlerAutoPage()
        self.crawler_auto_page.btn_get_crawler = IconPushButton(
            icon_name="arrow_down_to_line", icon_size=24, out_size=32
        )
        self.crawler_auto_page.append_row_widget(
            self.crawler_auto_page.btn_get_crawler, column=1
        )

        crawler_container = QWidget()
        crawler_layout = QVBoxLayout(crawler_container)
        crawler_layout.setContentsMargins(0, 0, 0, 0)
        crawler_layout.addWidget(self.crawler_auto_page)
        crawler_container.setMinimumHeight(200)

        # 外部导航栏
        self.navpage = CrawlerManualNavPage()
        nav_scroll = QScrollArea()
        nav_scroll.setWidget(self.navpage)
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        nav_container = QWidget()
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.addWidget(nav_scroll)
        nav_container.setMinimumHeight(200)

        # 封面栏
        cover_container = QWidget()
        cover_layout = QVBoxLayout(cover_container)
        cover_layout.setContentsMargins(0, 0, 0, 0)
        cover_layout.addWidget(self.coverdroplabel)

        # 基础信息（番号等，与中文/日文文案各为独立窗格）
        basic_info_container = QWidget()
        basic_layout = QVBoxLayout(basic_info_container)
        left_small_layout1 = QHBoxLayout()
        left_small_layout1.addWidget(self.label_serial_umber)
        left_small_layout1.addWidget(self.input_serial_number)
        left_small_layout1.addWidget(self.btn_load_form_db)
        left_small_layout1.addWidget(self.btn_jump_detail)
        left_small_layout2 = QHBoxLayout()
        left_small_layout2.addWidget(self.label_time)
        left_small_layout2.addWidget(self.input_time)
        left_small_layout3 = QHBoxLayout()
        left_small_layout3.addWidget(self.label_director)
        left_small_layout3.addWidget(self.input_director)
        left_small_layout4 = QHBoxLayout()
        left_small_layout4.addWidget(self.label_runtime)
        left_small_layout4.addWidget(self.input_runtime)
        left_small_layout5 = QHBoxLayout()
        left_small_layout5.addWidget(self.label_maker)
        left_small_layout5.addWidget(self.input_maker)
        left_small_layout6 = QHBoxLayout()
        left_small_layout6.addWidget(self.label_label)
        left_small_layout6.addWidget(self.input_label)
        left_small_layout7 = QHBoxLayout()
        left_small_layout7.addWidget(self.label_series)
        left_small_layout7.addWidget(self.input_series)

        self.label_local_video = Label("本地视频：")
        self.btn_local_video = QToolButton()
        self.btn_local_video.setAutoRaise(False)
        self.btn_local_video.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self.btn_local_video.setToolTip("播放本地视频（与 DVD 书架相同，按 video_url）")
        self.btn_local_video.setFixedSize(36, 28)
        left_small_layout8 = QHBoxLayout()
        left_small_layout8.addWidget(self.label_local_video)
        left_small_layout8.addWidget(self.btn_local_video)
        left_small_layout8.addStretch(1)

        basic_layout.addLayout(left_small_layout1)
        basic_layout.addLayout(left_small_layout2)
        basic_layout.addLayout(left_small_layout3)
        basic_layout.addLayout(left_small_layout4)
        basic_layout.addLayout(left_small_layout5)
        basic_layout.addLayout(left_small_layout6)
        basic_layout.addLayout(left_small_layout7)
        basic_layout.addLayout(left_small_layout8)
        basic_layout.addWidget(self.btn_add_work)

        cn_text_container = QWidget()
        cn_text_layout = QVBoxLayout(cn_text_container)
        cn_text_layout.addWidget(self.label_cn_title)
        cn_text_layout.addWidget(self.cn_title, 1)
        cn_text_layout.addWidget(self.label_cn_story)
        cn_text_layout.addWidget(self.cn_story, 3)

        jp_text_container = QWidget()
        jp_text_layout = QVBoxLayout(jp_text_container)
        jp_text_layout.addLayout(jp_title_label_layout)
        jp_text_layout.addWidget(self.jp_title, 1)
        jp_text_layout.addLayout(jp_story_label_layout)
        jp_text_layout.addWidget(self.jp_story, 3)

        # 女优选择器
        actress_container = QWidget()
        actress_layout = QVBoxLayout(actress_container)
        actress_layout.setContentsMargins(0, 0, 0, 0)
        actress_layout.addWidget(self.actressselector)

        # 男优选择器
        actor_container = QWidget()
        actor_layout = QVBoxLayout(actor_container)
        actor_layout.setContentsMargins(0, 0, 0, 0)
        actor_layout.addWidget(self.actorselector)

        # 标签选择器（独立窗格；Fanart 由 myads 另分一格，见下方 split）
        tag_container = QWidget()
        tag_layout = QVBoxLayout(tag_container)
        tag_layout.setContentsMargins(0, 0, 0, 0)
        tag_layout.addWidget(self.tag_selector)

        self.fanart_frame = QFrame()
        self.fanart_frame.setObjectName("addwork_fanart_outer_frame")
        fanart_frame_layout = QVBoxLayout(self.fanart_frame)
        fanart_frame_layout.setContentsMargins(0, 0, 0, 0)
        self.fanart_strip = FanartStripWidget(
            FANART_PATH, legacy_cover_path=WORKCOVER_PATH
        )
        fanart_frame_layout.addWidget(self.fanart_strip, 1)

        # 力导向图区
        self.forceview_container = QWidget()
        forceview_container_layout = QVBoxLayout(self.forceview_container)
        forceview_container_layout.setContentsMargins(0, 0, 0, 0)
        forceview_container_layout.addWidget(self.forceview_placeholder)

        # 自由记录区
        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.addWidget(self.input_notes)

        self._addwork_settings_container = QWidget()
        settings_layout = QVBoxLayout(self._addwork_settings_container)
        settings_layout.setContentsMargins(8, 8, 8, 8)
        settings_layout.addWidget(Label("工作区"))
        self._btn_save_addwork_layout = Button("保存布局")
        self._btn_save_addwork_layout.clicked.connect(
            self._on_save_addwork_workspace_layout
        )
        settings_layout.addWidget(self._btn_save_addwork_layout)
        self._btn_restore_addwork_layout = Button("恢复初始布局")
        self._btn_restore_addwork_layout.setToolTip(
            "恢复为程序默认拆分与标签，并删除已保存的布局文件"
        )
        self._btn_restore_addwork_layout.clicked.connect(
            self._on_restore_initial_addwork_workspace
        )
        settings_layout.addWidget(self._btn_restore_addwork_layout)
        settings_layout.addStretch(1)

        self._addwork_slot_widgets: dict[str, tuple[str, QWidget, bool]] = {
            "crawler": ("爬虫区", crawler_container, False),
            "nav": ("外部导航", nav_container, False),
            "cover": ("封面栏", cover_container, False),
            "basic": ("基础信息", basic_info_container, False),
            "settings": ("设置", self._addwork_settings_container, False),
            "jp_text": ("日文标题与剧情", jp_text_container, False),
            "cn_text": ("中文标题与剧情", cn_text_container, False),
            "actor": ("男优选择器", actor_container, False),
            "actress": ("女优选择器", actress_container, False),
            "tag": ("标签选择器", tag_container, False),
            "fanart": ("剧照", self.fanart_frame, False),
            "force": ("图谱", self.forceview_container, False),
            "editor": ("自由记录区", editor_container, False),
        }
        for _slot, (_t, w, __) in self._addwork_slot_widgets.items():
            w.setProperty("addwork_slot", _slot)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self._workspace_manager = WorkspaceManager(self)
        main_layout.addWidget(self._workspace_manager.widget())

        layout_path = ADD_WORK_WORKSPACE_LAYOUT_PATH
        if layout_path.exists():
            try:
                self._workspace_manager.load_layout(
                    layout_path,
                    content_factory=self._addwork_content_factory,
                )
            except Exception as e:
                logging.warning(
                    "加载添加作品工作区布局失败，使用默认布局: %s",
                    e,
                    exc_info=True,
                )
                self._build_default_addwork_workspace()
        else:
            self._build_default_addwork_workspace()

        QTimer.singleShot(0, self._init_forceview)

    def bind_model(self) -> None:
        """双向绑定"""
        self._updating_flags = {}  # 单独弄一个标记是否在更新，避免绑定循环问题
        # --------- 模型 -> UI ----------
        self.viewmodel.coverChanged.connect(
            self.coverdroplabel.set_image
        )  # 这些绑定实际上都是有点问题的，设置后会循环绑定的问题。

        self.viewmodel.actressChanged.connect(self.actressselector.load_with_ids)
        self.viewmodel.actorChanged.connect(self.actorselector.load_with_ids)
        self.viewmodel.tagChanged.connect(self.tag_selector.load_with_ids)
        self.viewmodel.makerChanged.connect(self.maker_model_to_ui)
        self.viewmodel.labelChanged.connect(self.label_model_to_ui)
        self.viewmodel.seriesChanged.connect(self.series_model_to_ui)

        self._updating_flags["fanart"] = False
        self.viewmodel.fanartChanged.connect(self.fanart_model_to_ui)
        self.fanart_strip.fanartChanged.connect(self.fanart_ui_to_model)

        # 这个是单向的model -> UI 没有问题
        self.viewmodel.btnStateChanged.connect(self.update_commit_btn)
        self.viewmodel.modifyStateChanged.connect(self.modify_state_change)
        # --------- UI -> 模型 ----------

        # 对于选择器，可以在选择变化时更新模型,这些信号都是自定义的
        self.actressselector.selectionChanged.connect(
            lambda: self.viewmodel.set_actress(self.actressselector.get_selected_ids())
        )
        self.actorselector.selectionChanged.connect(
            lambda: self.viewmodel.set_actor(self.actorselector.get_selected_ids())
        )
        self.tag_selector.selectionChanged.connect(
            lambda: self.viewmodel.set_tag(self.tag_selector.get_selected_ids())
        )
        self.input_maker.currentTextChanged.connect(lambda: self.maker_ui_to_model())
        self.input_label.currentTextChanged.connect(lambda: self.label_ui_to_model())
        self.input_series.currentTextChanged.connect(lambda: self.series_ui_to_model())
        self.coverdroplabel.coverChanged.connect(  # coverdroplabel 可以在图片改变后发信号更新模型
            lambda: self.viewmodel.set_cover(self.coverdroplabel.get_image())
        )

        bindings_map2: dict[str, QLineEdit] = {
            "serial_number": self.input_serial_number,
            "director": self.input_director,
            "release_date": self.input_time,
        }
        for prop_name, widget in bindings_map2.items():
            self._updating_flags[prop_name] = False
            widget.textChanged.connect(
                lambda text, p=prop_name: self.lineedit_ui_to_model(p, text)
            )
            vm_signal: SignalInstance = getattr(
                self.viewmodel, _property_changed_signal_name(prop_name)
            )
            vm_signal.connect(
                lambda text, w=widget, p=prop_name: self.lineedit_model_to_ui(
                    w, p, text
                )
            )

        # runtime 使用数字选择器做双向绑定
        self._updating_flags["runtime"] = False
        self.input_runtime.valueChanged.connect(
            lambda value: self.runtime_ui_to_model(value)
        )
        self.viewmodel.runtimeChanged.connect(
            lambda value: self.runtime_model_to_ui(value)
        )

        # 这样可以完整的处理好同一个类型的绑定问题，避免其回环，UI->model单向，model->UI单向，各自独立
        bindings_map: dict[str, QTextEdit] = {
            "cn_title": self.cn_title,
            "cn_story": self.cn_story,
            "jp_title": self.jp_title,
            "jp_story": self.jp_story,
            "notes": self.input_notes,
        }
        for prop_name, widget in bindings_map.items():
            self._updating_flags[prop_name] = False
            widget.textChanged.connect(
                lambda p=prop_name, w=widget: self.textedit_ui_to_model(w, p)
            )  # 匿名函数作为槽函数
            vm_signal: SignalInstance = getattr(
                self.viewmodel, _property_changed_signal_name(prop_name)
            )
            vm_signal.connect(
                lambda text, w=widget, p=prop_name: self.textedit_model_to_ui(
                    w, p, text
                )
            )  # 匿名函数作为槽函数

    def _init_forceview(self):
        if self.forceview is not None:
            return
        try:
            from core.graph.force_directed_view_widget import ForceDirectedViewWidget

            self.forceview = ForceDirectedViewWidget()
        except Exception as e:
            logging.error("初始化力导向图失败: %s", e)
            return

        layout = self.forceview_container.layout()
        if self.forceview_placeholder is not None:
            layout.removeWidget(self.forceview_placeholder)
            self.forceview_placeholder.setParent(None)
            self.forceview_placeholder.deleteLater()
            self.forceview_placeholder = None
        layout.addWidget(self.forceview)
        from core.graph.graph_manager import GraphManager
        from core.graph.graph_filter import EmptyFilter

        manager = GraphManager.instance()
        if manager._initialized:
            self.forceview.session.set_filter(EmptyFilter())
            self.forceview.session.new_load()
        else:
            manager.initialize()
            manager.initializationFinished.connect(self.forceview.session.new_load)

    # 处理绑定循环的问题
    def textedit_ui_to_model(self, widget: QPlainTextEdit, prop_name: str):
        if self._updating_flags.get(prop_name, False):
            return
        self._updating_flags[prop_name] = True
        setter_method = getattr(self.viewmodel, f"set_{prop_name}")
        setter_method(widget.toPlainText())
        self._updating_flags[prop_name] = False

    def textedit_model_to_ui(self, widget: QPlainTextEdit, prop_name: str, text: str):
        if self._updating_flags.get(prop_name, False):
            return
        self._updating_flags[prop_name] = True
        widget.clear()
        widget.setPlainText(text)
        self._updating_flags[prop_name] = False

    def lineedit_ui_to_model(self, prop_name: str, text: str):
        if self._updating_flags.get(prop_name, False):
            return
        self._updating_flags[prop_name] = True
        setter_method = getattr(self.viewmodel, f"set_{prop_name}")
        setter_method(text)
        self._updating_flags[prop_name] = False

    def lineedit_model_to_ui(self, widget: QTextEdit, prop_name: str, text):
        if self._updating_flags.get(prop_name, False):
            return
        self._updating_flags[prop_name] = True
        widget.setText(text)
        self._updating_flags[prop_name] = False

    def runtime_ui_to_model(self, value: int):
        if self._updating_flags.get("runtime", False):
            return
        self._updating_flags["runtime"] = True
        self.viewmodel.set_runtime(value)
        self._updating_flags["runtime"] = False

    def runtime_model_to_ui(self, value: int):
        if self._updating_flags.get("runtime", False):
            return
        self._updating_flags["runtime"] = True
        self.input_runtime.setValue(int(value) if value is not None else 0)
        self._updating_flags["runtime"] = False

    def maker_ui_to_model(self):
        if self._updating_flags.get("maker_id", False):
            return
        self._updating_flags["maker_id"] = True
        maker_id = self.input_maker.get_maker()
        self.viewmodel.set_maker(maker_id if maker_id is not None else None)
        self._updating_flags["maker_id"] = False

    def maker_model_to_ui(self, maker_id: int):
        if self._updating_flags.get("maker_id", False):
            return
        self._updating_flags["maker_id"] = True
        self.input_maker.set_maker(maker_id if maker_id and maker_id > 0 else None)
        self._updating_flags["maker_id"] = False

    def label_ui_to_model(self):
        if self._updating_flags.get("label_id", False):
            return
        self._updating_flags["label_id"] = True
        label_id = self.input_label.get_label()
        self.viewmodel.set_label(label_id if label_id is not None else None)
        self._updating_flags["label_id"] = False

    def label_model_to_ui(self, label_id: int):
        if self._updating_flags.get("label_id", False):
            return
        self._updating_flags["label_id"] = True
        self.input_label.set_label(label_id if label_id and label_id > 0 else None)
        self._updating_flags["label_id"] = False

    def series_ui_to_model(self):
        if self._updating_flags.get("series_id", False):
            return
        self._updating_flags["series_id"] = True
        series_id = self.input_series.get_series_id()
        self.viewmodel.set_series(series_id if series_id is not None else None)
        self._updating_flags["series_id"] = False

    def series_model_to_ui(self, series_id: int):
        if self._updating_flags.get("series_id", False):
            return
        self._updating_flags["series_id"] = True
        self.input_series.set_series_id(
            series_id if series_id and series_id > 0 else None
        )
        self._updating_flags["series_id"] = False

    def fanart_model_to_ui(self, items: list[dict]):
        if self._updating_flags.get("fanart", False):
            return
        self._updating_flags["fanart"] = True
        try:
            self.fanart_strip.set_entries(items)
        finally:
            self._updating_flags["fanart"] = False

    def fanart_ui_to_model(self, items: list[dict]):
        if self._updating_flags.get("fanart", False):
            return
        self._updating_flags["fanart"] = True
        try:
            self.viewmodel.set_fanart(items)
        finally:
            self._updating_flags["fanart"] = False

    # ----------------------------------------------------------
    #                       信号连接
    # ----------------------------------------------------------
    def signal_connect(self):
        """按钮信号连接"""
        self.viewmodel.serialNumberChanged.connect(
            self.viewmodel.on_work_selected
        )  # 核心
        self.viewmodel.serialNumberChanged.connect(self._sync_fanart_add_enabled)
        self.viewmodel.serialNumberChanged.connect(
            lambda *_a: QTimer.singleShot(0, self._refresh_local_video_button)
        )
        self.viewmodel.workInfoReloaded.connect(self._refresh_local_video_button)
        self.btn_local_video.clicked.connect(self._on_local_video_play_clicked)
        self.input_serial_number.returnPressed.connect(
            self.viewmodel._load_from_db
        )  # 按enter后查询

        self.btn_load_form_db.clicked.connect(self.viewmodel._load_from_db)
        self.btn_jump_detail.clicked.connect(self.viewmodel.jump_detail_page)

        self.btn_trans_title.clicked.connect(self.viewmodel._trans_title)
        self.btn_trans_story.clicked.connect(self.viewmodel._trans_story)

        self.navpage.set_serial_number_provider(lambda: self.input_serial_number.text())

        self.coverdroplabel.lowQualityCoverBadgeClicked.connect(
            self._on_low_quality_cover_badge_clicked
        )

        self.btn_add_work.clicked.connect(self.viewmodel.submit)
        self.crawler_auto_page.btn_get_crawler.clicked.connect(self.crawler2)

        global_signals.guiUpdate.connect(self.update_gui)
        global_signals.downloadSuccess.connect(self.update_cover)
        global_signals.workDataChanged.connect(self.input_serial_number.reload_items)
        global_signals.workDataChanged.connect(self.input_director.reload_items)
        global_signals.workDataChanged.connect(
            self._on_work_data_changed_sync_local_video
        )
        global_signals.makerDataChanged.connect(self.input_maker.reload_makers)
        global_signals.labelDataChanged.connect(self.input_label.reload_labels)
        global_signals.seriesDataChanged.connect(self.input_series.reload_series)

        self._sync_fanart_add_enabled()

        _tm = get_theme_manager()
        if _tm is not None:
            _tm.themeChanged.connect(
                lambda _tid: self._apply_local_video_button_style()
            )

    # ----------------------------------------------------------
    #          爬虫函数，QCheckBox触发，未MVVM,与UI耦合
    # ----------------------------------------------------------
    def crawler2(self):
        """用浏览器插件手动跳转javlibrary"""
        from core.crawler.crawler_manager import get_manager

        get_manager().start_crawl(self.viewmodel.serial_number, True)

    @Slot(object)
    def update_gui(self, data):
        """更新gui"""
        if self.crawler_auto_page.cb_release_date.isChecked():
            self.viewmodel.set_release_date(data["release_date"])
        if self.crawler_auto_page.cb_director.isChecked():
            self.viewmodel.set_director(data["director"])
        if self.crawler_auto_page.cb_actress.isChecked():
            self.viewmodel.set_actress(data["actress_list"])
        if self.crawler_auto_page.cb_actor.isChecked():
            self.viewmodel.set_actor(data["actor_list"])
        if self.crawler_auto_page.cb_cn_title.isChecked():
            self.viewmodel.set_cn_title(data["cn_title"])
        if self.crawler_auto_page.cb_cn_story.isChecked():
            self.viewmodel.set_cn_story(data["cn_story"])
        if self.crawler_auto_page.cb_jp_title.isChecked():
            self.viewmodel.set_jp_title(data["jp_title"])
        if self.crawler_auto_page.cb_jp_story.isChecked():
            self.viewmodel.set_jp_story(data["jp_story"])
        if self.crawler_auto_page.cb_tag.isChecked():
            cur_tag_id = self.viewmodel.get_tag()
            self.viewmodel.set_tag(list(set(cur_tag_id) | set(data["tag_id_list"])))
        if self.crawler_auto_page.cb_runtime.isChecked():
            self.viewmodel.set_runtime(data["runtime"])
        if self.crawler_auto_page.cb_maker.isChecked():
            self.input_maker.reload_makers()
            self.viewmodel.set_maker(data.get("maker_id", data.get("maker")))
        if self.crawler_auto_page.cb_series.isChecked():
            self.input_series.reload_series()
            self.viewmodel.set_series(data.get("series_id", data.get("series")))
        if self.crawler_auto_page.cb_label.isChecked():
            self.input_label.reload_labels()
            self.viewmodel.set_label(data.get("label_id", data.get("label")))
        if self.crawler_auto_page.cb_fanart.isChecked():
            raw_fanart = data.get("fanart") or []
            url_list: list[str] = []
            if isinstance(raw_fanart, list):
                for u in raw_fanart:
                    if isinstance(u, str) and u.strip():
                        url_list.append(u.strip())
            if url_list:
                self.fanart_strip.set_url_list(url_list)
            elif raw_fanart:
                logging.warning(
                    "爬虫返回的剧照无有效 URL，保留编辑页现有 Fanart（可能为网络或页面解析异常）"
                )
            else:
                logging.info(
                    "爬虫未返回剧照列表，保留编辑页现有 Fanart（网络异常时常为空）"
                )

    def update_cover(self, file_path: str):
        """更新封面"""
        logging.info(f"更新封面:{file_path}")
        if self.crawler_auto_page.cb_cover.isChecked():
            self.viewmodel.set_cover(file_path)

    @Slot()
    def _on_low_quality_cover_badge_clicked(self) -> None:
        """非高清角标：用 curl 拉取 Fanza pl 大图。"""
        if self._fanza_pl_fetching:
            return
        sn = self.viewmodel.get_serial_number().strip()
        if not sn:
            self.msg.show_info("提示", "请先填写番号")
            return
        cid = convert_fanza(sn.upper())
        url = f"https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/{cid}/{cid}pl.jpg"
        self._fanza_pl_fetching = True

        worker = Worker(lambda u=url: _download_fanza_pl_cover_via_js(u))
        wire_worker_finished(worker, self._on_fanza_pl_curl_download_finished)
        QThreadPool.globalInstance().start(worker)

    @Slot(object)
    def _on_fanza_pl_curl_download_finished(self, result: object) -> None:
        """线程池下载 Fanza pl 完成后回到主线程更新封面。"""
        self._fanza_pl_fetching = False
        if result is None:
            self.msg.show_warning("下载失败", "未知错误")
            return
        if not isinstance(result, tuple) or len(result) != 3:
            self.msg.show_warning("下载失败", "内部错误")
            return
        ok, path, err = result
        if ok and path:
            self.viewmodel.set_cover(path)
            return
        self.msg.show_warning("下载失败", err or "未知错误")

    def on_set_directview(self, id: str):
        if self.forceview is None:
            self._init_forceview()
        if self.forceview is None:
            return
        from core.graph.graph_filter import EgoFilter

        self.forceview.session.set_filter(
            EgoFilter(center_id=id, radius=3)
        )  # 这里设置过滤
        self.forceview.session.new_load()

    @Slot()
    def _sync_fanart_add_enabled(self, *_args):
        self.fanart_strip.set_can_add(bool(self.viewmodel.get_serial_number().strip()))

    def _apply_local_video_button_style(self) -> None:
        btn = self.btn_local_video
        mgr = get_theme_manager()
        if mgr is None:
            return
        t = mgr.tokens()
        r = t.radius_md
        if btn.isEnabled():
            btn.setStyleSheet(
                f"""
                QToolButton {{
                    background: {t.color_primary};
                    color: {t.color_text_inverse};
                    border: none;
                    border-radius: {r};
                    padding: 4px;
                }}
                QToolButton:hover {{
                    background: {t.color_primary_hover};
                }}
                """
            )
        else:
            btn.setStyleSheet(
                f"""
                QToolButton {{
                    background: {t.color_bg_input};
                    color: {t.color_text_disabled};
                    border: 1px solid {t.color_border};
                    border-radius: {r};
                    padding: 4px;
                }}
                """
            )

    def _refresh_local_video_button(self) -> None:
        vm = self.viewmodel
        cur = vm.get_serial_number().strip()
        ow = getattr(vm, "original_work", None) or {}
        enabled = False
        if (
            getattr(vm, "work_id", None) is not None
            and bool(ow)
            and cur
            and serial_number_equal(cur, str(ow.get("serial_number", "") or ""))
        ):
            paths = _split_video_url_field(ow.get("video_url"))
            enabled = len(paths) > 0
        self.btn_local_video.setEnabled(enabled)
        self._apply_local_video_button_style()

    @Slot()
    def _on_local_video_play_clicked(self) -> None:
        wid = self.viewmodel.work_id
        if wid is None:
            return
        info = get_workinfo_by_workid(wid)
        if not info:
            self.msg.show_info("提示", "没有可播放的视频")
            return
        path_strs = _split_video_url_field(info.get("video_url"))
        if not path_strs:
            self.msg.show_info("提示", "没有可播放的视频")
            return
        menu = QMenu(self)
        for path_str in path_strs:
            p = Path(path_str).expanduser()
            act = menu.addAction(p.name)
            act.setData(str(p))
        chosen = menu.exec(QCursor.pos())
        if chosen:
            play_video(Path(chosen.data()))

    @Slot()
    def _on_work_data_changed_sync_local_video(self) -> None:
        vm = self.viewmodel
        if getattr(vm, "work_id", None) is None:
            self._refresh_local_video_button()
            return
        ow = getattr(vm, "original_work", None)
        if not ow:
            self._refresh_local_video_button()
            return
        cur = vm.get_serial_number().strip()
        if not cur or not serial_number_equal(
            cur, str(ow.get("serial_number", "") or "")
        ):
            self._refresh_local_video_button()
            return
        inf = get_workinfo_by_workid(vm.work_id)
        if inf:
            ow["video_url"] = inf.get("video_url")
        self._refresh_local_video_button()

    # ----------------------------------------------------------
    #                         UI样式修改
    # ----------------------------------------------------------
    def beaute(self):
        """控件美化"""
        self.btn_load_form_db.setStyleSheet(
            """
            QPushButton {
                background-color: orange;
                color: white;
            }
            QPushButton:disabled {
                background-color: gray;
                color: darkGray;
            }
        """
        )

    @Slot(str, ButtonState)
    def update_commit_btn(self, key: str, state: ButtonState):
        """
        self._btn_state={
            'add_work':ButtonState.DISABLED,
            'load':ButtonState.WARNING,
            'temp_save':ButtonState.DISABLED,
            'temp_load':ButtonState.NORMAL
        }
        """
        match key:
            case "add_work":
                if state == ButtonState.NORMAL:
                    self.btn_add_work.setEnabled(True)
                    self.btn_add_work.setText("添加")
                    self.btn_add_work.setStyleSheet(
                        """
                        QPushButton {
                            background-color: #4CAF50;
                            color: white;
                            border-radius: 5px;
                            padding: 6px;
                        }
                    """
                    )
                elif state == ButtonState.WARNING:
                    self.btn_add_work.setEnabled(True)
                    self.btn_add_work.setText("修改")
                    self.btn_add_work.setStyleSheet(
                        """           
                            QPushButton {
                            background-color: #FFA500;
                            color: white;
                            border-radius: 5px;
                            padding: 6px;}
                        """
                    )
                elif state == ButtonState.DISABLED:
                    self.btn_add_work.setEnabled(False)
                    self.btn_add_work.setText("----")
                    self.btn_add_work.setStyleSheet(
                        """
                        QPushButton {
                            background-color: #999999;
                            color: #CCCCCC;
                            border-radius: 5px;
                            padding: 6px;
                        }
                    """
                    )
            case "load":
                if state == ButtonState.WARNING:
                    self.btn_load_form_db.setDisabled(False)
                elif state == ButtonState.DISABLED:
                    self.btn_load_form_db.setDisabled(True)

    def modify_state_change(self, key, value):
        highlight_line = "QLineEdit { border: 2px solid #FFA500; }"
        highlight_text = "QPlainTextEdit { border: 2px solid #FFA500; }"
        highlight_list = "QListView { border: 2px solid #FFA500; }"
        highlight_spin = "QSpinBox { border: 2px solid #FFA500; }"
        highlight_combo = "QComboBox { border: 2px solid #FFA500; }"
        highlight_cover_border = "2px dashed orange"
        normal_cover_border = None
        highlight_text2 = "QTextEdit { border: 2px solid #FFA500; }"
        highlight_frame = (
            "QFrame#addwork_fanart_outer_frame { border: 2px solid #FFA500; }"
        )

        mapping = [
            ("notes", self.input_notes, highlight_text2, ""),
            ("director", self.input_director, highlight_line, ""),
            ("release_date", self.input_time, highlight_line, ""),
            ("runtime", self.input_runtime, highlight_spin, ""),
            ("maker_id", self.input_maker, highlight_combo, ""),
            ("label_id", self.input_label, highlight_combo, ""),
            ("series_id", self.input_series, highlight_combo, ""),
            ("cn_title", self.cn_title, highlight_text, ""),
            ("jp_title", self.jp_title, highlight_text, ""),
            ("cn_story", self.cn_story, highlight_text, ""),
            ("jp_story", self.jp_story, highlight_text, ""),
            (
                "actress_ids",
                self.actressselector.receive_actress_view,
                highlight_list,
                "",
            ),
            ("actor_ids", self.actorselector.receive_actor_view, highlight_list, ""),
        ]

        for field, widget, style_on, style_off in mapping:
            if key == field:
                if value:
                    widget.setStyleSheet(style_on)
                else:
                    widget.setStyleSheet(style_off)
        if key == "image_url":
            if value:
                self.coverdroplabel.set_border_override(highlight_cover_border)
            else:
                self.coverdroplabel.set_border_override(normal_cover_border)
        if key == "fanart":
            if value:
                self.fanart_frame.setStyleSheet(highlight_frame)
            else:
                self.fanart_frame.setStyleSheet("")
        # 控制方法有两种，一种是直接控制，还有种是控件写出一个接口
        if key == "tag_ids":
            if value:
                self.tag_selector.set_state(False)
            else:
                self.tag_selector.set_state(True)
