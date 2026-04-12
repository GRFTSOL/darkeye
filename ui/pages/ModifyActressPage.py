from PySide6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QFormLayout,
    QWidget,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QObject, Signal, Property, Slot

import copy
import json
import logging
from enum import Enum
from pathlib import Path

from config import ACTRESSIMAGES_PATH
from utils.utils import mse


from darkeye_ui import LazyWidget
from controller.message_service import MessageBoxService, IMessageService

from ui.myads.workspace_manager import WorkspaceManager, Placement, ContentConfig

from ui.basic import MovableTableView
from core.database.query import get_actress_allname, get_serial_number
from ui.widgets import ActressAvatarDropWidget
from ui.widgets.text.WikiTextEdit import WikiTextEdit
from server.bridge import ServerBridge

from darkeye_ui.components.toggle_switch import ToggleSwitch
from darkeye_ui.components.button import Button
from darkeye_ui.components.combo_box import ComboBox
from darkeye_ui.components.label import Label
from darkeye_ui.components.icon_push_button import IconPushButton
from darkeye_ui.components.input import LineEdit
from darkeye_ui.components.token_spin_box import TokenSpinBox


class ButtonState(Enum):
    NORMAL = 1
    WARNING = 2
    DISABLED = 3


class Model:
    """纯放要显示数据的model"""

    def __init__(self):
        self._actress_id: int = None

        self._height: int = None
        self._cup: str = None
        self._birthday: str = None
        self._hip: int = None
        self._waist: int = None
        self._bust: int = None
        self._debut_date: str = None
        self._need_update: bool = False
        # minnano-av 页面缓存的演员编号（可能来自 DB/插件的字符串）
        self._minnano_id: str = None
        self._image_urlA: str = None
        self._actress_name: list[dict] = []
        self._notes: str = ""

    def to_dict(self):
        return {
            "actress_id": self._actress_id,
            "height": self._height,
            "cup": self._cup,
            "birthday": self._birthday,
            "hip": self._hip,
            "waist": self._waist,
            "bust": self._bust,
            "debut_date": self._debut_date,
            "need_update": self._need_update,
            "minnano_url": self._minnano_id,
            "image_urlA": self._image_urlA,
            "actress_name": self._actress_name,
            "notes": self._notes,
        }


class ViewModel(QObject):
    actressIdChanged = Signal(int)
    heightChanged = Signal(int)
    cupChanged = Signal(str)
    birthdayChanged = Signal(str)
    hipChanged = Signal(int)
    waistChanged = Signal(int)
    bustChanged = Signal(int)
    debutDateChanged = Signal(str)
    needUpdateChanged = Signal(bool)
    # 用 str 以避免 Qt 的 Signal(int) 在接收到空字符串/非数字时转换失败
    minnanoIdChanged = Signal(str)
    imageUrlAChanged = Signal(str)
    actressNameChanged = Signal(list)
    notesChanged = Signal(str)

    modifyStateChanged = Signal(str, bool)
    btnStateChanged = Signal(str, object)

    def __init__(self, model: Model = None, message_service: IMessageService = None):
        super().__init__()
        self.model: Model = model
        self.msg: MessageBoxService = message_service

        self._cheakable: bool = False
        self.original_actress: dict | None = None
        self._change_detection_connected: bool = False
        self._changed_flags: dict[str, bool] = {
            "height": False,
            "cup": False,
            "birthday": False,
            "hip": False,
            "waist": False,
            "bust": False,
            "debut_date": False,
            "need_update": False,
            "minnano_url": False,
            "image_urlA": False,
            "actress_name": False,
            "notes": False,
        }
        self._btn_state: dict[str, ButtonState] = {
            "commit": ButtonState.DISABLED,
        }

        bridge = ServerBridge()

        bridge.minnanoActressCaptureReceived.connect(self.apply_minnano_capture)

    def set_state(self, key: str, value: bool) -> None:
        if key not in self._changed_flags:
            raise KeyError(f"Unknown change flag key: {key}")
        v = bool(value)
        if self._changed_flags[key] != v:
            self._changed_flags[key] = v
            self.modifyStateChanged.emit(key, v)

    def set_change_widget_default(self) -> None:
        for key in self._changed_flags:
            self.set_state(key, False)

    def set_btn_state(self, key: str, value: ButtonState) -> None:
        if key not in self._btn_state:
            raise KeyError(f"Unknown button state key: {key}")
        if self._btn_state[key] != value:
            self._btn_state[key] = value
            self.btnStateChanged.emit(key, value)

    @staticmethod
    def _actress_names_fingerprint(names: list | None) -> str:
        if not names:
            return "[]"
        return json.dumps(names, ensure_ascii=False, sort_keys=True, default=str)

    @Slot()
    def check_actress_name_change(self) -> None:
        if not self._cheakable or self.original_actress is None:
            return
        cur = self.get_actress_name()
        orig = self.original_actress.get("actress_name")
        self.set_state(
            "actress_name",
            self._actress_names_fingerprint(cur)
            != self._actress_names_fingerprint(orig),
        )
        self.update_commit_button_state()

    @Slot()
    def check_change(self, field: str, new_value) -> None:
        if not self._cheakable or self.original_actress is None:
            return
        if field not in self._changed_flags:
            return
        original_value = self.original_actress.get(field)
        if field == "need_update":
            self.set_state(field, bool(original_value) != bool(new_value))
        elif original_value is None or new_value is None:
            self.set_state(field, original_value != new_value)
        elif isinstance(original_value, list) and isinstance(new_value, list):
            self.set_state(field, original_value != new_value)
        else:
            self.set_state(field, original_value != new_value)
        self.update_commit_button_state()

    @Slot()
    def check_image_change(self) -> None:
        if not self._cheakable or self.original_actress is None:
            return
        orig_rel = self.original_actress.get("image_urlA") or ""
        if isinstance(orig_rel, str):
            orig_rel = orig_rel.strip()
        else:
            orig_rel = ""
        cur = self.get_image_urlA() or ""
        if isinstance(cur, str):
            cur = cur.strip()
        else:
            cur = ""

        if not orig_rel:
            self.set_state("image_urlA", bool(cur))
        elif not cur:
            self.set_state("image_urlA", True)
        else:
            orig_path = Path(ACTRESSIMAGES_PATH) / orig_rel
            p_cur = Path(cur)
            cur_path = p_cur if p_cur.is_absolute() else Path(ACTRESSIMAGES_PATH) / cur
            try:
                if not orig_path.is_file() or not cur_path.is_file():
                    self.set_state("image_urlA", str(orig_path) != str(cur_path))
                else:
                    self.set_state(
                        "image_urlA", mse(str(orig_path), str(cur_path)) != 0
                    )
            except Exception:
                self.set_state("image_urlA", orig_rel != cur)
        self.update_commit_button_state()

    def update_commit_button_state(self) -> None:
        if any(self._changed_flags.values()):
            self.set_btn_state("commit", ButtonState.WARNING)
        else:
            self.set_btn_state("commit", ButtonState.DISABLED)

    def setup_change_detection(self) -> None:
        if self._change_detection_connected:
            return
        self._change_detection_connected = True
        self.heightChanged.connect(
            lambda: self.check_change("height", self.get_height())
        )
        self.cupChanged.connect(lambda: self.check_change("cup", self.get_cup()))
        self.birthdayChanged.connect(
            lambda: self.check_change("birthday", self.get_birthday())
        )
        self.hipChanged.connect(lambda: self.check_change("hip", self.get_hip()))
        self.waistChanged.connect(lambda: self.check_change("waist", self.get_waist()))
        self.bustChanged.connect(lambda: self.check_change("bust", self.get_bust()))
        self.debutDateChanged.connect(
            lambda: self.check_change("debut_date", self.get_debut_date())
        )
        self.needUpdateChanged.connect(
            lambda: self.check_change("need_update", self.get_need_update())
        )
        self.minnanoIdChanged.connect(
            lambda: self.check_change("minnano_url", self.get_minnano_id())
        )
        self.notesChanged.connect(lambda: self.check_change("notes", self.get_notes()))
        self.actressNameChanged.connect(self.check_actress_name_change)
        self.imageUrlAChanged.connect(self.check_image_change)

    def get_actress_id(self):
        return self.model._actress_id

    def set_actress_id(self, value: int):
        if self.model._actress_id != value:
            self.model._actress_id = value
            self.actressIdChanged.emit(value)

    actress_id = Property(int, get_actress_id, set_actress_id, notify=actressIdChanged)

    def get_height(self):
        return self.model._height

    def set_height(self, value: int):
        if self.model._height != value:
            self.model._height = value
            self.heightChanged.emit(value)

    height = Property(int, get_height, set_height, notify=heightChanged)

    def get_cup(self):
        return self.model._cup

    def set_cup(self, value: str):
        if self.model._cup != value:
            self.model._cup = value
            self.cupChanged.emit(value)
            # logging.debug(f"cup changed to {value}")

    cup = Property(str, get_cup, set_cup, notify=cupChanged)

    def get_birthday(self):
        return self.model._birthday

    def set_birthday(self, value: str):
        if self.model._birthday != value:
            self.model._birthday = value
            self.birthdayChanged.emit(value)

    birthday = Property(str, get_birthday, set_birthday, notify=birthdayChanged)

    def get_hip(self):
        return self.model._hip

    def set_hip(self, value: int):
        if self.model._hip != value:
            self.model._hip = value
            self.hipChanged.emit(value)

    hip = Property(int, get_hip, set_hip, notify=hipChanged)

    def get_waist(self):
        return self.model._waist

    def set_waist(self, value: int):
        if self.model._waist != value:
            self.model._waist = value
            self.waistChanged.emit(value)

    waist = Property(int, get_waist, set_waist, notify=waistChanged)

    def get_bust(self):
        return self.model._bust

    def set_bust(self, value: int):
        if self.model._bust != value:
            self.model._bust = value
            self.bustChanged.emit(value)

    bust = Property(int, get_bust, set_bust, notify=bustChanged)

    def get_debut_date(self):
        return self.model._debut_date

    def set_debut_date(self, value: str):
        if self.model._debut_date != value:
            self.model._debut_date = value
            self.debutDateChanged.emit(value)

    debut_date = Property(str, get_debut_date, set_debut_date, notify=debutDateChanged)

    def get_need_update(self):
        return self.model._need_update

    def set_need_update(self, value: bool):
        if self.model._need_update != value:
            self.model._need_update = value
            self.needUpdateChanged.emit(value)

    need_update = Property(
        bool, get_need_update, set_need_update, notify=needUpdateChanged
    )

    def get_image_urlA(self):
        return self.model._image_urlA

    def set_image_urlA(self, value: str):
        if self.model._image_urlA != value:
            self.model._image_urlA = value
            self.imageUrlAChanged.emit(value)

    image_urlA = Property(str, get_image_urlA, set_image_urlA, notify=imageUrlAChanged)

    def get_actress_name(self):
        # logging.debug("读取actress_name数据")
        return self.model._actress_name

    def set_actress_name(self, value: list[dict]):
        logging.debug("设置viewmodel里的actress_name")
        from utils.utils import sort_dict_list_by_keys

        order = [
            "actress_name_id",
            "cn",
            "jp",
            "kana",
            "en",
            "level",
            "redirect_actress_name_id",
        ]
        value = sort_dict_list_by_keys(value, order)
        if self.model._actress_name != value:
            self.model._actress_name = value
            self.actressNameChanged.emit(value)

    actress_name = Property(
        list, get_actress_name, set_actress_name, notify=actressNameChanged
    )

    def get_notes(self):
        return self.model._notes

    def set_notes(self, value: str):
        if not value:
            value = ""
        normalized = value.strip()
        if self.model._notes != normalized:
            self.model._notes = normalized
            self.notesChanged.emit(normalized)

    notes = Property(str, get_notes, set_notes, notify=notesChanged)

    def get_minnano_id(self):
        return self.model._minnano_id

    def set_minnano_id(self, value):
        """
        minnano-av id 有时来自 DB（可能是 None/空字符串），有时来自插件（int）。
        这里统一转成字符串，确保 QLineEdit 能正确显示。
        """
        if value is None:
            normalized = ""
        elif isinstance(value, int):
            normalized = str(value)
        else:
            normalized = str(value).strip()

        if self.model._minnano_id != normalized:
            self.model._minnano_id = normalized
            self.minnanoIdChanged.emit(normalized)

    minnano_id = Property(str, get_minnano_id, set_minnano_id, notify=minnanoIdChanged)

    def load(self, actress_id: int):
        """加载"""
        from core.database.query import get_actress_info

        self._cheakable = False
        actress = get_actress_info(actress_id)
        if not actress:
            self.msg.show_warning("错误", "未找到该女优信息")
            self.original_actress = None
            self.update_commit_button_state()
            return
        logging.debug(f"设置actress_id:{actress_id}")
        self.set_actress_id(actress_id)
        self.set_height(actress.get("height") or 0)
        self.set_cup(actress.get("cup") or "")
        self.set_minnano_id(actress.get("minnano_url") or "")

        self.set_birthday(actress.get("birthday") or "")
        self.set_hip(actress.get("hip") or 0)
        self.set_waist(actress.get("waist") or 0)
        self.set_bust(actress.get("bust") or 0)
        self.set_debut_date(actress.get("debut_date") or "")
        self.set_image_urlA(actress.get("image_urlA") or "")
        self.set_actress_name(get_actress_allname(self.actress_id))
        self.set_need_update(bool(actress.get("need_update")))
        self.set_notes(actress.get("notes") or "")

        self.original_actress = copy.deepcopy(self.model.to_dict())
        self._cheakable = True
        self.set_change_widget_default()
        self.update_commit_button_state()

    @Slot()
    def submit(self):
        """手动修改记录"""
        # 获得基本数据

        logging.debug("添加记录")
        data = self.model.to_dict()  # 从viewmodel里取

        image_url = (
            str(self.actress_id) + "-" + self.actress_name[0]["jp"] + ".jpg"
        )  # 图片名字的规则,要保证日文名字一定要有
        if self.get_image_urlA() is None or self.get_image_urlA() == "":
            data["image_urlA"] = None
        else:
            from core.database.insert import rename_save_image

            rename_save_image(data["image_urlA"], image_url, "actress")
            data["image_urlA"] = image_url

        self._update_actress_and_handle_result(**data)

    def _update_actress_and_handle_result(self, **data):
        from core.database.update import update_actress_byhand

        actress_name = data["actress_name"][0]["jp"]

        if update_actress_byhand(**data):
            self.msg.show_info("更新女优信息成功", f"女优名字: {actress_name}")
            logging.info("更新女优成功，女优名字：%s", actress_name)
            # 刷新，重新加载
            self.load(data.get("actress_id"))
            return True
        else:
            self.msg.show_warning("更新女优信息失败", f"未知原因")
            logging.warning("更新%s女优信息失败", actress_name)
            return False

    @Slot()
    def clawer_update(self):
        """GET /api/v1/actress/ 拉取 minnano，仅填入 MVVM；核对后点提交再写库。"""
        from PySide6.QtCore import QThreadPool

        from core.crawler.minnanoav import fetch_actress_minnano_for_edit_worker
        from core.crawler.worker import Worker, wire_worker_finished

        jp = self.actress_name[0]["jp"]
        logging.info(self.actress_id)
        logging.info(jp)
        worker = Worker(
            fetch_actress_minnano_for_edit_worker,
            jp,
            self.actress_id,
            self.get_minnano_id(),
        )
        wire_worker_finished(worker, self._on_clawer_update_finished)
        QThreadPool.globalInstance().start(worker)
        self.msg.show_info(
            "爬虫更新",
            "正在通过 Firefox 拉取 minnano，请稍候…",
        )

    @Slot(object)
    def _on_clawer_update_finished(self, result):
        if result is None:
            self.msg.show_warning(
                "爬虫更新",
                "处理失败，请查看日志。",
                top_level=True,
            )
            return
        kind, payload = result[0], result[1]
        if kind == "data":
            raw = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(raw, dict):
                self.msg.show_warning(
                    "minnano 更新失败",
                    "未收到有效数据。",
                    top_level=True,
                )
                return
            self.apply_minnano_capture(
                {
                    "context": {
                        "persist": False,
                        "actress_id": self.actress_id,
                    },
                    "data": raw,
                    "_silent_completion": True,
                }
            )
            return
        err = ""
        if isinstance(payload, dict):
            err = str(payload.get("error") or "")
        err_s = err
        hints = {
            "multiple_search_results": (
                "minnano 搜索到多名女优，请填写 minnano id 后重试或使用手动跳转。"
            ),
            "minnano_auto_no_match": "未在 minnano 找到匹配条目。",
            "minnano_auto_unexpected_page": "页面状态异常，无法自动采集。",
            "minnano_scrape_unavailable": "页面脚本未就绪，请刷新后重试。",
            "no_data": "未收到 minnano 数据，请重试或检查插件。",
        }
        low = err_s.lower()
        if "no browser extension" in low or "503" in err_s:
            self.msg.show_warning(
                "爬虫更新",
                "未连接浏览器插件：请打开 Firefox 并启用 DarkEye 扩展。",
                top_level=True,
            )
            return
        if "504" in err_s or "timed out" in low:
            self.msg.show_warning(
                "爬虫更新",
                "等待插件响应超时，请重试。",
                top_level=True,
            )
            return
        if not err_s:
            self.msg.show_warning(
                "爬虫更新",
                "无法连接本地服务，请确认 DarkEye 已启动。",
                top_level=True,
            )
            return
        self.msg.show_warning(
            "minnano 更新失败",
            hints.get(err_s, err_s),
            top_level=True,
        )

    def update_minnano_id(self, value):
        """将女优的minnano_id直接写入数据库"""
        from core.database.update import update_actress_minnano_id

        logging.info(f"设置女优{self.actress_id}的minnano_id为{value}")
        update_actress_minnano_id(self.actress_id, value)

    @Slot(dict)
    def apply_minnano_capture(self, body: dict):
        """插件 minnano 页「采集」：回填表单并关闭「需要更新」（仍须提交后写库）。"""
        import copy
        from datetime import datetime
        from pathlib import Path

        from config import TEMP_PATH
        from core.crawler.download import download_image_js

        if not body or self.actress_id is None:
            return
        ctx = body.get("context") or {}
        if ctx.get("persist"):
            # 旧 persist 路径回传忽略（当前女优采集走 HTTP + actress-fetch-result）
            return
        aid = ctx.get("actress_id")
        aid_int = None
        if aid is not None:
            try:
                aid_int = int(aid)
            except (TypeError, ValueError):
                aid_int = None

        if aid_int is not None and self.actress_id != aid_int:
            self.msg.show_warning(
                "提示",
                "采集上下文与当前编辑女优不一致，已忽略。",
                top_level=True,
            )
            return

        data = body.get("data") or {}
        mid = data.get("minnano_actress_id")
        if mid is not None and str(mid).strip() != "":
            try:
                mid_int = int(str(mid).strip())
                self.set_minnano_id(str(mid_int))
            except (ValueError, TypeError):
                logging.warning("无效的 minnano_actress_id: %s", mid)

        self.set_height(int(data.get("身高") or 0))
        self.set_bust(int(data.get("胸围") or 0))
        self.set_waist(int(data.get("腰围") or 0))
        self.set_hip(int(data.get("臀围") or 0))
        self.set_cup(str(data.get("罩杯") or ""))
        self.set_birthday(str(data.get("出生日期") or ""))
        self.set_debut_date(str(data.get("出道日期") or ""))

        names = copy.deepcopy(self.get_actress_name() or [])
        jp = (data.get("日文名") or "").strip()
        kana = (data.get("假名") or "").strip()
        en = (data.get("英文名") or "").strip()
        aliases = data.get("alias_chain") or []

        if not names:
            names = [
                {
                    "actress_name_id": None,
                    "cn": "",
                    "jp": jp,
                    "kana": kana,
                    "en": en,
                    "redirect_actress_name_id": None,
                    "level": 1,
                }
            ]
        else:
            names[0]["jp"] = jp or names[0].get("jp", "")
            names[0]["kana"] = kana or names[0].get("kana", "")
            names[0]["en"] = en or names[0].get("en", "")

        for i, al in enumerate(aliases):
            if not isinstance(al, dict):
                continue
            row_idx = i + 1
            jp_a = (al.get("jp") or "").strip()
            kana_a = (al.get("kana") or "").strip()
            en_a = (al.get("en") or "").strip()
            if row_idx < len(names):
                names[row_idx]["jp"] = jp_a or names[row_idx].get("jp", "")
                names[row_idx]["kana"] = kana_a or names[row_idx].get("kana", "")
                names[row_idx]["en"] = en_a or names[row_idx].get("en", "")
            else:
                names.append(
                    {
                        "actress_name_id": None,
                        "cn": "",
                        "jp": jp_a,
                        "kana": kana_a,
                        "en": en_a,
                        "redirect_actress_name_id": None,
                        "level": row_idx + 1,
                    }
                )
        self.set_actress_name(names)

        url_img = data.get("头像地址")
        if url_img:
            try:
                TEMP_PATH.mkdir(parents=True, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest = Path(TEMP_PATH) / f"minnano_{self.actress_id}_{ts}.jpg"
                ok, _ = download_image_js(url_img, str(dest))
                if ok:
                    self.set_image_urlA(str(dest.resolve()))
            except Exception as e:
                logging.warning("下载 minnano 头像失败: %s", e)

        self.set_need_update(False)

        if not body.get("_silent_completion"):
            self.msg.show_info(
                "采集完成",
                "已从 minnano 填入表单，请核对后点击提交。",
                top_level=True,
            )

    @Slot(bool)
    def on_result(self, result: bool, actressName: str):  # Qsignal回传信息
        pass
        # from controller.global_signal_bus import global_signals
        # taskmanager=TaskManager.instance()
        # if result:
        #    taskmanager.complete_task(task,"查询完成")
        # else:
        #    taskmanager.error_task(task,"查询失败")

    @Slot()
    def print(self):
        logging.debug(self.model.to_dict())

    @Slot()
    def delete_actress(self):
        """直接删除一个女优，如果有在作品中的就不删除"""
        from core.database.delete import delete_actress

        success, message = delete_actress(self.actress_id)
        if success:
            self.msg.show_info("提示", message)
            from controller.global_signal_bus import global_signals

            global_signals.actressDataChanged.emit()
        else:
            self.msg.show_warning("提示", message)

    @Slot()
    def show_actress(self):
        """跳转到展示单个女优界面"""
        logging.debug(f"准备跳转展示女优界面{self.get_actress_id()}")

        from ui.navigation.router import Router

        Router.instance().push("single_actress", actress_id=self.get_actress_id())


class ModifyActressPage(LazyWidget):
    """
    用于修改女优信息的页面
    """

    def __init__(self):
        super().__init__()

    def _lazy_load(self):
        logging.info("----------修改女优信息页面----------")
        self.config()
        self.init_ui()
        self.bind_model()
        self.signal_connect()

    def init_ui(self):
        mainlayout = QVBoxLayout(self)
        mainlayout.setContentsMargins(0, 0, 0, 0)

        self._workspace_manager = WorkspaceManager(self)
        mainlayout.addWidget(self._workspace_manager.widget())
        root = self._workspace_manager.get_root_pane()

        def make_config(
            title: str, w: QWidget, closeable: bool = True
        ) -> ContentConfig:
            cfg = self._workspace_manager.create_content_config()
            return cfg.set_window_title(title).set_widget(w).set_closeable(closeable)

        self.moveable_name = MovableTableView()
        self.avatar = ActressAvatarDropWidget("actress")

        self.notes_panel = QWidget()
        notes_vlayout = QVBoxLayout(self.notes_panel)
        notes_vlayout.setContentsMargins(0, 0, 0, 0)
        notes_vlayout.addWidget(Label("自由记录"))
        self.input_notes = WikiTextEdit()
        self.input_notes.set_completer_func(get_serial_number)
        self.input_notes.setMinimumWidth(280)
        self.input_notes.setMinimumHeight(120)
        self.input_notes.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        notes_vlayout.addWidget(self.input_notes, 1)

        self.moveable_name.tableView.setMinimumHeight(160)
        self.moveable_name.tableView.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self.input_height = TokenSpinBox()
        self.input_height.setRange(0, 190)
        self.input_waist = TokenSpinBox()
        self.input_waist.setRange(0, 120)
        self.input_hip = TokenSpinBox()
        self.input_hip.setRange(0, 120)
        self.input_bust = TokenSpinBox()
        self.input_bust.setRange(0, 120)
        self.input_cup = ComboBox()
        self.input_cup.addItems(
            ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M"]
        )

        self.input_birthday = LineEdit()
        self.input_debut_date = LineEdit()
        self.need_update = ToggleSwitch(width=40, height=20)
        self.btn_commit = Button("提交修改")
        self.btn_claw_update = Button("爬虫尝试更新(需手动提交)")
        # self.btn_printModel=QPushButton("打印数据")
        self.btn_minnano = Button("跳转手动选择(需手动提交)")
        self.btn_minnano.setToolTip("这个是对于那些多女优的搜索结果的，需要自己确认")
        self.smallwidget = QWidget()  # 放一些小按钮
        self.smalllayout = QHBoxLayout(self.smallwidget)
        self.btn_delete = IconPushButton(icon_name="trash_2")
        self.btn_show = IconPushButton(icon_name="eye")

        self.input_minnano_id = LineEdit()

        self.smalllayout.addWidget(self.btn_show)
        self.smalllayout.addWidget(self.btn_delete)

        avatar_container = QWidget()
        avatar_layout = QVBoxLayout(avatar_container)
        avatar_layout.setContentsMargins(0, 0, 0, 0)
        avatar_layout.addWidget(self.avatar, 1)
        avatar_container.setMinimumWidth(260)

        form_container = QWidget()
        form_container.setMinimumWidth(260)
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(0, 0, 0, 0)
        formlayout = QFormLayout()
        form_layout.addLayout(formlayout)
        formlayout.addRow(Label("身高(cm)"), self.input_height)
        formlayout.addRow(Label("罩杯"), self.input_cup)
        formlayout.addRow(Label("胸围(cm)"), self.input_bust)
        formlayout.addRow(Label("腰围(cm)"), self.input_waist)
        formlayout.addRow(Label("臀围(cm)"), self.input_hip)
        formlayout.addRow(Label("生日(yyyy-mm-dd)"), self.input_birthday)
        formlayout.addRow(Label("出道日期(yyyy-mm-dd)"), self.input_debut_date)
        formlayout.addRow(Label("需要更新"), self.need_update)
        formlayout.addRow(Label("minnano-av id"), self.input_minnano_id)

        actions_container = QWidget()
        actions_layout = QVBoxLayout(actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.addWidget(self.btn_commit)
        actions_layout.addWidget(self.btn_claw_update)
        actions_layout.addWidget(self.btn_minnano)
        actions_layout.addWidget(self.smallwidget)

        name_container = QWidget()
        name_layout = QVBoxLayout(name_container)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.addWidget(self.moveable_name, 1)

        # root: 左列 | 右侧（名字表 | 自由记录）
        pane_right = self._workspace_manager.split(root, Placement.Right, ratio=0.68)
        pane_notes = self._workspace_manager.split(
            pane_right, Placement.Right, ratio=0.4
        )
        # root: 头像 | 下方（表单 | 操作）
        pane_lower = self._workspace_manager.split(root, Placement.Bottom, ratio=0.6)

        pane_actions = self._workspace_manager.split(
            pane_right, Placement.Bottom, ratio=0.22
        )

        self._workspace_manager.fill_pane(
            root, make_config("头像", avatar_container, closeable=False)
        )
        self._workspace_manager.fill_pane(
            pane_lower, make_config("基础信息", form_container, closeable=False)
        )
        self._workspace_manager.fill_pane(
            pane_actions, make_config("操作", actions_container, closeable=False)
        )
        self._workspace_manager.fill_pane(
            pane_right, make_config("名字表", name_container, closeable=False)
        )
        self._workspace_manager.fill_pane(
            pane_notes, make_config("自由记录", self.notes_panel, closeable=False)
        )

    def config(self):
        """配置model与view"""

        self.msg = MessageBoxService(self)  # 弹窗服务
        self.model = Model()
        self.vm = ViewModel(self.model, self.msg)  # 依赖注入
        self._notes_binding_lock = False

    def signal_connect(self):
        self.btn_claw_update.clicked.connect(self.vm.clawer_update)
        # self.btn_printModel.clicked.connect(self.vm.print)
        self.btn_commit.clicked.connect(self.vm.submit)
        self.btn_minnano.clicked.connect(self.jump_minnano)
        self.btn_delete.clicked.connect(self.vm.delete_actress)
        self.btn_show.clicked.connect(self.vm.show_actress)

    def bind_model(self):
        """双向绑定"""
        # 实际上下面都会有循环绑定的问题，后面需要改
        self.input_height.valueChanged.connect(self.vm.set_height)
        self.vm.heightChanged.connect(self.input_height.setValue)

        self.input_hip.valueChanged.connect(self.vm.set_hip)
        self.vm.hipChanged.connect(self.input_hip.setValue)

        self.input_waist.valueChanged.connect(self.vm.set_waist)
        self.vm.waistChanged.connect(self.input_waist.setValue)

        self.input_bust.valueChanged.connect(self.vm.set_bust)
        self.vm.bustChanged.connect(self.input_bust.setValue)

        self.input_cup.currentTextChanged.connect(self.vm.set_cup)
        self.vm.cupChanged.connect(self.input_cup.setCurrentText)  # 这里有问题

        self.input_birthday.textChanged.connect(self.vm.set_birthday)
        self.vm.birthdayChanged.connect(self.input_birthday.setText)

        self.input_debut_date.textChanged.connect(self.vm.set_debut_date)
        self.vm.debutDateChanged.connect(self.input_debut_date.setText)

        self.need_update.toggled.connect(self.vm.set_need_update)
        self.vm.needUpdateChanged.connect(self.need_update.setChecked)

        # minnano_id的绑定
        self.input_minnano_id.textChanged.connect(self.vm.set_minnano_id)
        self.vm.minnanoIdChanged.connect(self.input_minnano_id.setText)

        # tablemodel与viewmodel的绑定
        # TODO 这里存在循环绑定的问题
        self.moveable_name.model.dataUpdated.connect(self.vm.set_actress_name)
        self.vm.actressNameChanged.connect(
            self.moveable_name.updatedata
        )  # 这个实际上有点违反原则，pyside6信号传字典时顺序不可控

        self.vm.imageUrlAChanged.connect(
            self.avatar.set_image
        )  # 这些绑定实际上都是有点问题的，不过先不管了
        self.avatar.coverChanged.connect(  # coverdroplabel 可以在图片改变后发信号更新模型
            lambda: self.vm.set_image_urlA(self.avatar.get_image())
        )

        self.input_notes.textChanged.connect(self._notes_ui_to_vm)
        self.vm.notesChanged.connect(self._notes_vm_to_ui)

        self.vm.setup_change_detection()
        self.vm.modifyStateChanged.connect(self.modify_state_change)
        self.vm.btnStateChanged.connect(self.update_commit_btn)
        self.update_commit_btn("commit", ButtonState.DISABLED)

    @Slot(str, bool)
    def modify_state_change(self, key: str, value: bool) -> None:
        highlight_line = "QLineEdit#DesignInput { border: 2px solid #FFA500; }"
        highlight_spin = "QSpinBox#DesignSpinBox { border: 2px solid #FFA500; }"
        highlight_combo = "QComboBox#DesignComboBox { border: 2px solid #FFA500; }"
        highlight_text = "QTextEdit#DesignTextEdit { border: 2px solid #FFA500; }"
        highlight_table = "QTableView#DesignTableView { border: 2px solid #FFA500; }"
        highlight_toggle = (
            "QWidget#DesignToggleSwitch { border: 2px solid #FFA500; "
            "border-radius: 4px; }"
        )

        mapping = [
            ("height", self.input_height, highlight_spin, ""),
            ("hip", self.input_hip, highlight_spin, ""),
            ("waist", self.input_waist, highlight_spin, ""),
            ("bust", self.input_bust, highlight_spin, ""),
            ("cup", self.input_cup, highlight_combo, ""),
            ("birthday", self.input_birthday, highlight_line, ""),
            ("debut_date", self.input_debut_date, highlight_line, ""),
            ("minnano_url", self.input_minnano_id, highlight_line, ""),
            ("need_update", self.need_update, highlight_toggle, ""),
            ("notes", self.input_notes, highlight_text, ""),
            ("actress_name", self.moveable_name.tableView, highlight_table, ""),
        ]
        for field, widget, style_on, style_off in mapping:
            if key == field:
                widget.setStyleSheet(style_on if value else style_off)
                return
        if key == "image_urlA":
            self.avatar.set_dirty_highlight(value)

    @Slot(str, object)
    def update_commit_btn(self, key: str, state) -> None:
        if key != "commit":
            return
        if state == ButtonState.WARNING:
            self.btn_commit.setEnabled(True)
            self.btn_commit.setStyleSheet(
                """
                QPushButton {
                    background-color: #FFA500;
                    color: white;
                    border-radius: 5px;
                    padding: 6px;
                }
                """
            )
        elif state == ButtonState.DISABLED:
            self.btn_commit.setEnabled(False)
            self.btn_commit.setStyleSheet(
                """
                QPushButton {
                    background-color: #999999;
                    color: #CCCCCC;
                    border-radius: 5px;
                    padding: 6px;
                }
                """
            )

    def _notes_ui_to_vm(self):
        if self._notes_binding_lock:
            return
        self._notes_binding_lock = True
        self.vm.set_notes(self.input_notes.toPlainText())
        self._notes_binding_lock = False

    def _notes_vm_to_ui(self, text: str):
        if self._notes_binding_lock:
            return
        self._notes_binding_lock = True
        self.input_notes.blockSignals(True)
        self.input_notes.clear()
        self.input_notes.setPlainText(text or "")
        self.input_notes.blockSignals(False)
        self._notes_binding_lock = False

    def update(self, actress_id: int):
        """加载"""
        self.vm.load(actress_id)

    @Slot()
    def jump_minnano(self):
        from core.crawler.jump import jump_minnanoav

        jp_name = self.vm.get_actress_name()
        jp_name = jp_name[0]["jp"]
        jump_minnanoav(jp_name)
