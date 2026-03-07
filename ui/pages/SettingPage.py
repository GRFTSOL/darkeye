
from darkeye_ui import LazyWidget

from PySide6.QtWidgets import  QHBoxLayout,QVBoxLayout,QFileDialog,QGridLayout,QWidget,QFormLayout
from PySide6.QtGui import QIcon,QKeySequence,QColor
from PySide6.QtCore import Slot,Qt
import logging
from config import ICONS_PATH
from controller.MessageService import MessageBoxService
from pathlib import Path
from darkeye_ui.components import ModernScrollMenu
from ui.basic import MultiplePathManagement
from config import get_video_path
from config import APP_VERSION

import logging
from config import BASE_DIR,DATABASE,INI_FILE,ICONS_PATH,PRIVATE_DATABASE,DATABASE_BACKUP_PATH,PRIVATE_DATABASE_BACKUP_PATH
from config import get_theme_id, set_theme_id, get_custom_primary, set_custom_primary
from controller.ShortcutRegistry import ShortcutRegistry
from pathlib import Path
from app_context import get_theme_manager
from main import apply_theme
from darkeye_ui.design import ThemeId
from darkeye_ui.components.label import Label
from darkeye_ui.components.button import Button
from darkeye_ui.components.token_radio_button import TokenRadioButton
from darkeye_ui.components.combo_box import ComboBox
from darkeye_ui.components.token_key_sequence_edit import TokenKeySequenceEdit
from darkeye_ui.components.color_picker import ColorPicker
from darkeye_ui.components.toggle_switch import ToggleSwitch
from controller.GlobalSignalBus import global_signals

# 主题下拉选项与 ThemeId 顺序一致
THEME_OPTIONS = [
    (ThemeId.LIGHT, "亮色主题"),
    (ThemeId.DARK, "暗色主题"),
    (ThemeId.RED, "红色"),
    (ThemeId.YELLOW, "黄色"),
    (ThemeId.GREEN, "绿色"),
    (ThemeId.BLUE, "蓝色"),
    (ThemeId.PURPLE, "紫色"),
]

class CommonPage(QWidget):
    def __init__(self):
        super().__init__()
        main_layout = QFormLayout(self)
        self.textchoose=ComboBox()
        self.textsizechoose=ComboBox()
        self.theme_choose = ComboBox()
        for _, label in THEME_OPTIONS:
            self.theme_choose.addItem(label)
        saved_theme = get_theme_id()
        try:
            idx = next(i for i, (tid, _) in enumerate(THEME_OPTIONS) if tid.name == saved_theme)
            self.theme_choose.setCurrentIndex(idx)
        except StopIteration:
            theme_mgr = get_theme_manager()
            if theme_mgr is not None:
                try:
                    idx = next(i for i, (tid, _) in enumerate(THEME_OPTIONS) if tid == theme_mgr.current())
                    self.theme_choose.setCurrentIndex(idx)
                except StopIteration:
                    pass
        self.theme_choose.currentIndexChanged.connect(self._on_theme_changed)

        # 主色选择器（置于主题行上方，仅亮色/暗色主题可调）
        theme_mgr = get_theme_manager()
        self.primary_color_row = QWidget()
        primary_color_layout = QHBoxLayout(self.primary_color_row)
        primary_color_layout.setContentsMargins(0, 0, 0, 0)
        initial_primary = (
            get_custom_primary()
            or (theme_mgr.custom_primary() if theme_mgr else None)
            or (theme_mgr.tokens().color_primary if theme_mgr else "#2563eb")
        )
        self.color_picker = ColorPicker(QColor(initial_primary), shape=ColorPicker.ShapeCircle)
        primary_color_layout.addWidget(self.color_picker)

        self.color_picker.colorConfirmed.connect(self._on_primary_color_changed)
        self._update_primary_picker_state()
        self.greenmode=ToggleSwitch()

        main_layout.addRow(Label("主色"), self.primary_color_row)
        main_layout.addRow(Label("主题"), self.theme_choose)
        main_layout.addRow(Label("绿色模式"),self.greenmode)
        self.greenmode.toggled.connect(global_signals.green_mode_changed.emit)
        #main_layout.addRow("字体选择",self.textchoose)
        #main_layout.addRow("字号选择",self.textsizechoose)


    def _update_primary_picker_state(self):
        theme_mgr = get_theme_manager()
        tid = theme_mgr.current() if theme_mgr else ThemeId.LIGHT
        is_light_or_dark = tid in (ThemeId.LIGHT, ThemeId.DARK)
        self.primary_color_row.setEnabled(is_light_or_dark)
        if not is_light_or_dark:
            if theme_mgr:
                theme_mgr.set_custom_primary(None)
            set_custom_primary(None)
        else:
            self.color_picker.blockSignals(True)
            # 优先从 INI 读取主色
            self.color_picker.set_color(
                get_custom_primary()
                or (theme_mgr.custom_primary() if theme_mgr else None)
                or (theme_mgr.tokens().color_primary if theme_mgr else "#2563eb")
            )
            self.color_picker.blockSignals(False)

    def _on_primary_color_changed(self, hex_color: str):
        theme_mgr = get_theme_manager()
        if theme_mgr:
            theme_mgr.set_custom_primary(hex_color)
        set_custom_primary(hex_color)
        apply_theme(theme_mgr.current() if theme_mgr else ThemeId.LIGHT)

    def _on_theme_changed(self, index: int):
        if 0 <= index < len(THEME_OPTIONS):
            theme_id = THEME_OPTIONS[index][0]
            theme_mgr = get_theme_manager()
            if theme_id not in (ThemeId.LIGHT, ThemeId.DARK):
                if theme_mgr:
                    theme_mgr.set_custom_primary(None)
                set_custom_primary(None)
            else:
                # 切换回亮色/暗色时优先从 INI 恢复主色
                saved = get_custom_primary()
                if theme_mgr and saved:
                    theme_mgr.set_custom_primary(saved)
            set_theme_id(theme_id)
            apply_theme(theme_id)
            self._update_primary_picker_state()


class ShortcutSettingRow(QWidget):
    def __init__(self, action_id, registry, action_obj, parent=None):
        super().__init__(parent)
        self.action_id = action_id
        self.registry = registry
        self.action_obj = action_obj
        
        layout = QHBoxLayout(self)
        
        # 1. 获取显示的名称
        name = self.registry.defaults[action_id]["name"]
        self.label = Label(name)
        self.label.setFixedWidth(100)
        
        # 2. 获取当前的快捷键
        current_key = self.registry.get_shortcut(action_id)
        
        self.key_edit = TokenKeySequenceEdit()
        self.key_edit.setFixedWidth(150)
        self.key_edit.setKeySequence(QKeySequence(current_key))
        
        # 3. 恢复默认按钮 (可选)
        self.reset_btn = Button("恢复")
        self.reset_btn.setFixedWidth(50)
        self.reset_btn.clicked.connect(self.reset_default)

        layout.addWidget(self.label)
        layout.addWidget(self.key_edit)
        layout.addWidget(self.reset_btn)
        layout.addStretch()

        self.key_edit.editingFinished.connect(self.apply_change)

    def apply_change(self):
        new_key_str = self.key_edit.keySequence().toString()
        # 更新配置类
        self.registry.update_shortcut(self.action_id, new_key_str)
        # 更新实际的 Action
        self.action_obj.setShortcut(QKeySequence(new_key_str))

    def reset_default(self):
        # 恢复注册表中的默认值
        self.registry.reset_to_default(self.action_id)
        default_key = self.registry.get_shortcut(self.action_id)
        # 更新 UI 和 Action
        self.key_edit.setKeySequence(QKeySequence(default_key))
        self.action_obj.setShortcut(QKeySequence(default_key))

class ShortCutSettingPage(QWidget):
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout(self)
        self.registry=ShortcutRegistry()

        for action_id in self.registry.defaults.keys():
            action_obj = self.registry.actions_map[action_id]
            row = ShortcutSettingRow(action_id, self.registry, action_obj)
            main_layout.addWidget(row)

        main_layout.addStretch()
        main_layout.addWidget(Label("<small>配置将自动保存到 shortcuts_config.json</small>"))

class ClawerSettingPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(Label("<h3>爬虫相关设置</h3>"))

class DBSettingPage(QWidget):
    '''这个是数据库相关设置页面'''
    def __init__(self):
        super().__init__()
        
        self.msg=MessageBoxService(self)
        path_label=Label(f"软件的工作文件夹{str(BASE_DIR)}")
        path_label2=Label(f"软件的公共数据库文件位置{str(DATABASE)}")
        path_label3=Label(f"ini文件的位置{INI_FILE}")

        self.btn_vacuum=Button("数据库清理碎片")#包括清理两个数据库
        self.btn_cover_check=Button("图片数据一致性检查")

        self.btn_commit=Button("保存设置")
        self.btn_commit.setVisible(False)
        
        self.btn_backupDB = Button()
        self.btn_backupDB.setText("备份公共数据库")
        self.btn_backupDB.setToolTip("将现有的数据库打上时间戳备份")
        self.btn_backupDB.setIcon(QIcon(str(ICONS_PATH / "database.svg")))


        self.btn_restoreDB = Button()
        self.btn_restoreDB.setText("还原公共数据库")
        self.btn_restoreDB.setToolTip("在备份的数据库里选择一个数据还原，覆盖现有的数据库")
        self.btn_restoreDB.setIcon(QIcon(str(ICONS_PATH / "database.svg")))


        self.btn_backupDB2 = Button()
        self.btn_backupDB2.setText("备份私有数据库")
        self.btn_backupDB2.setToolTip("将现有的数据库打上时间戳备份")
        self.btn_backupDB2.setIcon(QIcon(str(ICONS_PATH / "database.svg")))


        self.btn_restoreDB2 = Button()
        self.btn_restoreDB2.setText("还原私有数据库")
        self.btn_restoreDB2.setToolTip("在备份的数据库里选择一个数据还原，覆盖现有的数据库")
        self.btn_restoreDB2.setIcon(QIcon(str(ICONS_PATH / "database.svg")))



        layout1=QGridLayout()

        layout1.addWidget(self.btn_vacuum,0,0)
        layout1.addWidget(self.btn_cover_check,0,1)
        layout1.addWidget(self.btn_backupDB,1,0)
        layout1.addWidget(self.btn_restoreDB,1,1)
        layout1.addWidget(self.btn_backupDB2,2,0)
        layout1.addWidget(self.btn_restoreDB2,2,1)

        #总装
        layout=QVBoxLayout(self)
        layout.addLayout(layout1)
        layout.addWidget(self.btn_commit)
        layout.addWidget(path_label)
        layout.addWidget(path_label2)
        layout.addWidget(path_label3)

        self.signal_connect()


    def signal_connect(self):
        from core.database.db_utils import sqlite_vaccum
        self.btn_cover_check.clicked.connect(self.check_image_consistency)
        self.btn_vacuum.clicked.connect(sqlite_vaccum)
        self.btn_commit.clicked.connect(self.submit)

        self.btn_backupDB.clicked.connect(lambda:self.backup_db("public"))
        self.btn_restoreDB.clicked.connect(lambda:self.restoreDB("public"))
        self.btn_backupDB2.clicked.connect(lambda:self.backup_db("private"))
        self.btn_restoreDB2.clicked.connect(lambda:self.restoreDB("private"))


    @Slot()
    def check_image_consistency(self):
        '''检查数据库中的图片一致性的问题'''
        from core.database.db_utils import image_consistency
        image_consistency(True,"cover")
        image_consistency(True,"actress")
        image_consistency(True,"actor")
        self.msg.show_info("提示","处理好图片一致性问题，删除多余图片")
        
    @Slot()
    def submit(self):
        #获得基本数据
        logging.debug("保存设置")


    @Slot()
    def restoreDB(self,access_level:str):
        #选择一个备份的数据库还原
        #这个目前有，这个是直接覆盖，风险问题，数据库在写入，后面再改全局单例数据库管理器来管理所有的连接
        if access_level=="public":
            backup_path=DATABASE_BACKUP_PATH
            target_path=DATABASE
        elif access_level=="private":
            backup_path=PRIVATE_DATABASE_BACKUP_PATH
            target_path=PRIVATE_DATABASE     
        else:
            logging.info("错误，未选择等级")

        from core.database.backup_utils import restore_database,restore_backup_safely
        file_path, _ = QFileDialog.getOpenFileName(
            self,               # 父组件
            "选择一个数据库",      # 对话框标题
            str(backup_path),                 # 起始路径
            "*.db"  # 文件过滤器
        )

        if not file_path:
            return
    
        if not self.msg.ask_yes_no("确认恢复","是否用该备份覆盖现有数据库？操作不可撤销！"):
            return

        success = restore_backup_safely(Path(file_path), target_path)
        if success:
            self.msg.show_info("恢复成功", "数据库恢复完成。")
        else:
            self.msg.show_critical("恢复失败", "数据库恢复失败，请检查文件是否有效。")

    @Slot()
    def backup_db(self,access_level:str):
        '''备份数据库'''
        if access_level=="public":
            backup_path=DATABASE_BACKUP_PATH
            target_path=DATABASE
        elif access_level=="private":
            backup_path=PRIVATE_DATABASE_BACKUP_PATH
            target_path=PRIVATE_DATABASE     
        else:
            logging.info("错误，未选择等级")

        from core.database.backup_utils import backup_database
        try:
            path=backup_database(target_path,backup_path)
            self.msg.show_info("备份成功",f"备份路径{path}")
        except Exception as e:
            self.msg.show_critical(self,"备份失败",f"{str(e)}")

class LastPage(QWidget):
    '''这个是尾页'''
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout1=QHBoxLayout()
        layout2=QHBoxLayout()
        layout3=QHBoxLayout()
        form_layout = QFormLayout()


        githubLabel = Label()
        githubLabel.setText(
            '<a href="https://github.com/de4321/darkeye">https://github.com/de4321/darkeye</a>'
        )
        githubLabel.setTextFormat(Qt.RichText)
        githubLabel.setTextInteractionFlags(Qt.TextBrowserInteraction)
        githubLabel.setOpenExternalLinks(True)   # 关键

        layout1.addWidget(Label(f"当前版本{APP_VERSION}"))
        layout1.addWidget(Button("检查更新"))
        layout1.addWidget(Button("意见反馈"))
        layout1.addWidget(Button("版本记录"))

        layout2.addWidget(TokenRadioButton("自动更新"))
        layout2.addWidget(TokenRadioButton("有新版本时提醒我"))

        layout3.addWidget(Label("下载移动客户端"))
        layout3.addWidget(Button("Android版"))


        form_layout.addRow(Label("GitHub地址"),githubLabel)
        layout.addLayout(layout1)
        layout.addLayout(layout2)
        layout.addLayout(layout3)
        layout.addLayout(form_layout)

class VideoSettingPage(QWidget):
    '''这个是视频相关设置页面'''
    def __init__(self):
        super().__init__()

        self.init_ui()
        self.pathManagement.load_paths(get_video_path())#加载视频路径
        self.save.clicked.connect(self.accept)
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        self.pathManagement=MultiplePathManagement(label_text="视频文件夹路径管理：")
        self.pathManagement.setMinimumHeight(300)
        layout.addWidget(self.pathManagement)

        self.save=Button("保存")
        
        layout.addWidget(self.save)
        
        

    def accept(self):
        # 保存路径设置
        paths=self.pathManagement.get_paths()
        # 这里可以添加代码将paths保存到配置文件或应用设置中
        from config import update_video_path
        update_video_path(paths)
        logging.info(f"保存的视频路径设置写入.ini: {paths}")


class SettingPage(LazyWidget):
    def __init__(self):
        super().__init__()


    def _lazy_load(self):
        page_video = VideoSettingPage()
        page_clawer = ClawerSettingPage()
        page_db = DBSettingPage()
        page_first = LastPage()
        page_short_cut=ShortCutSettingPage()
        page_common=CommonPage()


        # 核心字典：定义 导航名 -> 对应Widget实例
        my_content = {
            "常规":page_common,
            "视频": page_video,
            "爬虫": page_clawer,
            "数据库": page_db,
            "快捷键":page_short_cut,
            "关于软件": page_first
        }
        mainlayout=QVBoxLayout(self)
        window = ModernScrollMenu(my_content)
        mainlayout.addWidget(window)
