from PySide6.QtWidgets import (
    QVBoxLayout,
    QFormLayout,
    QWidget,
    QSizePolicy,
)
from PySide6.QtCore import QObject, Signal, Property, Slot

import copy
import json
import logging
from enum import Enum
from pathlib import Path

from config import ACTORIMAGES_PATH
from utils.utils import mse

from darkeye_ui import LazyWidget
from controller.message_service import MessageBoxService, IMessageService

from ui.myads.workspace_manager import WorkspaceManager, Placement, ContentConfig

from ui.basic import MovableTableView
from core.database.query import get_actor_allname, get_serial_number
from darkeye_ui.components.button import Button
from darkeye_ui.components.label import Label
from darkeye_ui.components.icon_push_button import IconPushButton
from darkeye_ui.components.token_spin_box import TokenSpinBox
from ui.widgets import ActorAvatarDropWidget
from ui.widgets.text.WikiTextEdit import WikiTextEdit


class ButtonState(Enum):
    NORMAL = 1
    WARNING = 2
    DISABLED = 3


class Model:
    """纯放要显示数据的model"""

    def __init__(self):
        self._actor_id: int = None

        self._handsome: int = None
        self._fat: int = None
        self._image_url: str = None
        self._actor_name: list[dict] = []
        self._notes: str = ""

    def to_dict(self):
        return {
            "handsome": self._handsome,
            "fat": self._fat,
            "actor_id": self._actor_id,
            "image_url": self._image_url,
            "actor_name": self._actor_name,
            "notes": self._notes,
        }


class ViewModel(QObject):
    actorIdChanged = Signal(int)

    needUpdateChanged = Signal(bool)
    imageUrlChanged = Signal(str)
    actorNameChanged = Signal(list)
    fatChanged = Signal(int)
    handsomeChanged = Signal(int)
    notesChanged = Signal(str)

    modifyStateChanged = Signal(str, bool)
    btnStateChanged = Signal(str, object)

    def __init__(self, model: Model = None, message_service: IMessageService = None):
        super().__init__()
        self.model: Model = model
        self.msg: MessageBoxService = message_service

        self._cheakable: bool = False
        self.original_actor: dict | None = None
        self._change_detection_connected: bool = False
        self._changed_flags: dict[str, bool] = {
            "handsome": False,
            "fat": False,
            "image_url": False,
            "actor_name": False,
            "notes": False,
        }
        self._btn_state: dict[str, ButtonState] = {
            "commit": ButtonState.DISABLED,
        }

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
    def _actor_names_fingerprint(names: list | None) -> str:
        if not names:
            return "[]"
        return json.dumps(names, ensure_ascii=False, sort_keys=True, default=str)

    @Slot()
    def check_actor_name_change(self) -> None:
        if not self._cheakable or self.original_actor is None:
            return
        cur = self.get_actor_name()
        orig = self.original_actor.get("actor_name")
        self.set_state(
            "actor_name",
            self._actor_names_fingerprint(cur) != self._actor_names_fingerprint(orig),
        )
        self.update_commit_button_state()

    @Slot()
    def check_change(self, field: str, new_value) -> None:
        if not self._cheakable or self.original_actor is None:
            return
        if field not in self._changed_flags:
            return
        original_value = self.original_actor.get(field)
        if original_value is None or new_value is None:
            self.set_state(field, original_value != new_value)
        elif isinstance(original_value, list) and isinstance(new_value, list):
            self.set_state(field, original_value != new_value)
        else:
            self.set_state(field, original_value != new_value)
        self.update_commit_button_state()

    @Slot()
    def check_image_change(self) -> None:
        if not self._cheakable or self.original_actor is None:
            return
        orig_rel = self.original_actor.get("image_url") or ""
        if isinstance(orig_rel, str):
            orig_rel = orig_rel.strip()
        else:
            orig_rel = ""
        cur = self.get_image_url() or ""
        if isinstance(cur, str):
            cur = cur.strip()
        else:
            cur = ""

        if not orig_rel:
            self.set_state("image_url", bool(cur))
        elif not cur:
            self.set_state("image_url", True)
        else:
            orig_path = Path(ACTORIMAGES_PATH) / orig_rel
            p_cur = Path(cur)
            cur_path = p_cur if p_cur.is_absolute() else Path(ACTORIMAGES_PATH) / cur
            try:
                if not orig_path.is_file() or not cur_path.is_file():
                    self.set_state("image_url", str(orig_path) != str(cur_path))
                else:
                    self.set_state("image_url", mse(str(orig_path), str(cur_path)) != 0)
            except Exception:
                self.set_state("image_url", orig_rel != cur)
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
        self.handsomeChanged.connect(
            lambda: self.check_change("handsome", self.get_handsome())
        )
        self.fatChanged.connect(lambda: self.check_change("fat", self.get_fat()))
        self.notesChanged.connect(lambda: self.check_change("notes", self.get_notes()))
        self.actorNameChanged.connect(self.check_actor_name_change)
        self.imageUrlChanged.connect(self.check_image_change)

    def get_actor_id(self):
        return self.model._actor_id

    def set_actor_id(self, value: int):
        if self.model._actor_id != value:
            self.model._actor_id = value
            self.actorIdChanged.emit(value)

    actor_id = Property(int, get_actor_id, set_actor_id, notify=actorIdChanged)

    def get_fat(self):
        return self.model._fat

    def set_fat(self, value: int):
        if self.model._fat != value:
            self.model._fat = value
            self.fatChanged.emit(value)

    fat = Property(int, get_fat, set_fat, notify=fatChanged)

    def get_handsome(self):
        return self.model._handsome

    def set_handsome(self, value: int):
        if self.model._handsome != value:
            self.model._handsome = value
            self.handsomeChanged.emit(value)

    handsome = Property(int, get_handsome, set_handsome, notify=handsomeChanged)

    def get_image_url(self):
        return self.model._image_url

    def set_image_url(self, value: str):
        if self.model._image_url != value:
            self.model._image_url = value
            self.imageUrlChanged.emit(value)

    image_urlA = Property(str, get_image_url, set_image_url, notify=imageUrlChanged)

    def get_actor_name(self):
        logging.debug("读取actor_name数据")
        return self.model._actor_name

    def set_actor_name(self, value: list[dict]):
        logging.debug("设置viewmodel里的actor_name")
        from utils.utils import sort_dict_list_by_keys

        order = ["actor_name_id", "cn", "jp", "kana", "en"]
        value = sort_dict_list_by_keys(value, order)
        if self.model._actor_name != value:
            self.model._actor_name = value
            self.actorNameChanged.emit(value)

    actor_name = Property(list, get_actor_name, set_actor_name, notify=actorNameChanged)

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

    def load(self, actor_id: int):
        """加载"""
        from core.database.query import get_actor_info

        self._cheakable = False
        actor = get_actor_info(actor_id)
        if not actor:
            self.msg.show_warning("错误", "未找到该男优信息")
            self.original_actor = None
            self.update_commit_button_state()
            return
        logging.debug(f"设置actor_id:{actor_id}")
        self.set_handsome(actor.get("handsome") or 0)
        self.set_fat(actor.get("fat") or 0)
        self.set_actor_id(actor_id)
        self.set_image_url(actor.get("image_url") or "")
        self.set_actor_name(get_actor_allname(self.actor_id))
        self.set_notes(actor.get("notes") or "")

        self.original_actor = copy.deepcopy(self.model.to_dict())
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
            str(self.actor_id) + "-" + self.actor_name[0]["jp"] + ".jpg"
        )  # 图片名字的规则,要保证日文名字一定要有
        if self.get_image_url() is None or self.get_image_url() == "":
            data["image_url"] = None
        else:
            from core.database.insert import rename_save_image

            rename_save_image(data["image_url"], image_url, "actor")
            data["image_url"] = image_url

        self._update_actor_and_handle_result(**data)

    def _update_actor_and_handle_result(self, **data):
        from core.database.update import update_actor_byhand

        actor_name = data["actor_name"][0]["jp"]

        if update_actor_byhand(**data):
            self.msg.show_info("更新男优信息成功", f"男优名字: {actor_name}")
            logging.info("更新男优成功，男优名字：%s", actor_name)
            self.load(data.get("actor_id"))
            return True
        else:
            self.msg.show_warning("更新男优信息失败", f"未知原因")
            logging.warning("更新%s男优信息失败", actor_name)
            return False

    @Slot()
    def print(self):
        logging.debug(self.model.to_dict())

    @Slot()
    def delete_actor(self):
        """直接删除一个男优，如果有在作品中的就不删除"""
        from core.database.delete import delete_actor

        success, message = delete_actor(self.actor_id)
        if success:
            self.msg.show_info("提示", message)
            # 更新男优的界面
        else:
            self.msg.show_warning("提示", message)


class ModifyActorPage(LazyWidget):
    # 修改男优信息
    """ """

    def __init__(self):
        super().__init__()

    def _lazy_load(self):
        logging.info("----------修改男优信息页面----------")
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
        self.avatar = ActorAvatarDropWidget()

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

        self.input_handsome = TokenSpinBox()
        self.input_handsome.setRange(0, 2)

        self.input_fat = TokenSpinBox()
        self.input_fat.setRange(0, 2)

        self.btn_commit = Button("提交修改")
        self.btn_delete = IconPushButton(icon_name="trash_2")

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
        formlayout.addRow(Label("颜值"), self.input_handsome)
        formlayout.addRow(Label("胖瘦"), self.input_fat)

        actions_container = QWidget()
        actions_layout = QVBoxLayout(actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.addWidget(self.btn_commit)
        actions_layout.addWidget(self.btn_delete)

        name_container = QWidget()
        name_layout = QVBoxLayout(name_container)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.addWidget(self.moveable_name, 1)

        pane_right = self._workspace_manager.split(root, Placement.Right, ratio=0.68)
        pane_notes = self._workspace_manager.split(
            pane_right, Placement.Right, ratio=0.33
        )
        pane_lower = self._workspace_manager.split(root, Placement.Bottom, ratio=0.6)
        pane_actions = self._workspace_manager.split(
            pane_lower, Placement.Bottom, ratio=0.22
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

        # self.btn_printModel.clicked.connect(self.vm.print)
        self.btn_commit.clicked.connect(self.vm.submit)
        self.btn_delete.clicked.connect(self.vm.delete_actor)

    def bind_model(self):
        """双向绑定"""
        # 实际上下面都会有循环绑定的问题，后面需要改

        self.input_handsome.valueChanged.connect(self.vm.set_handsome)
        self.vm.handsomeChanged.connect(self.input_handsome.setValue)

        self.input_fat.valueChanged.connect(self.vm.set_fat)
        self.vm.fatChanged.connect(self.input_fat.setValue)

        # tablemodel与viewmodel的绑定
        # TODO 这里存在循环绑定的问题
        self.moveable_name.model.dataUpdated.connect(self.vm.set_actor_name)
        self.vm.actorNameChanged.connect(
            self.moveable_name.updatedata
        )  # 这个实际上有点违反原则，pyside6信号传字典时顺序不可控

        self.vm.imageUrlChanged.connect(
            self.avatar.set_image
        )  # 这些绑定实际上都是有点问题的，不过先不管了
        self.avatar.coverChanged.connect(  # coverdroplabel 可以在图片改变后发信号更新模型
            lambda: self.vm.set_image_url(self.avatar.get_image())
        )

        self.input_notes.textChanged.connect(self._notes_ui_to_vm)
        self.vm.notesChanged.connect(self._notes_vm_to_ui)

        self.vm.setup_change_detection()
        self.vm.modifyStateChanged.connect(self.modify_state_change)
        self.vm.btnStateChanged.connect(self.update_commit_btn)
        self.update_commit_btn("commit", ButtonState.DISABLED)

    @Slot(str, bool)
    def modify_state_change(self, key: str, value: bool) -> None:
        highlight_spin = "QSpinBox#DesignSpinBox { border: 2px solid #FFA500; }"
        highlight_text = "QTextEdit#DesignTextEdit { border: 2px solid #FFA500; }"
        highlight_table = "QTableView#DesignTableView { border: 2px solid #FFA500; }"

        mapping = [
            ("handsome", self.input_handsome, highlight_spin, ""),
            ("fat", self.input_fat, highlight_spin, ""),
            ("notes", self.input_notes, highlight_text, ""),
            ("actor_name", self.moveable_name.tableView, highlight_table, ""),
        ]
        for field, widget, style_on, style_off in mapping:
            if key == field:
                widget.setStyleSheet(style_on if value else style_off)
                return
        if key == "image_url":
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

    def update(self, actor_id: int):
        """加载"""
        self.vm.load(actor_id)
