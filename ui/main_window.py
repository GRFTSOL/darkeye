from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QToolButton, QFrame, QStyle,QStatusBar,
)
from PySide6.QtCore import Qt, QPropertyAnimation, QSize, Signal, QEasingCurve

import os,psutil,logging
from PySide6.QtWidgets import QWidget,QStackedWidget,QPushButton,QHBoxLayout, QVBoxLayout,QLineEdit,QLabel,QStatusBar,QMainWindow
from PySide6.QtCore import Qt,Signal,QTimer,Slot,QSize,QThreadPool,QObject,QEvent,QRect
from PySide6.QtGui import QIcon,QKeySequence,QShortcut,QPainter,QColor,QAction
from config import ICONS_PATH,APP_VERSION,set_max_window
from ui.pages import WorkPage,ManagementPage,StatisticsPage,ActressPage,AvPage,SingleActressPage,SingleWorkPage,ModifyActressPage,ActorPage,ModifyActorPage,SettingPage
from ui.pages import CoverBrowser
from core.recommendation.Recommend import recommendStart,randomRec
from ui.basic import IconPushButton,ToggleSwitch,StateToggleButton
from controller.GlobalSignalBus import global_signals
from core.database.query import get_serial_number
from ui.widgets.text.CompleterLineEdit import CompleterLineEdit
from controller import ShortcutRegistry
from controller.ShortcutBindings import setup_mainwindow_actions
from ui.widgets.Sidebar import Sidebar
from ui.navigation.router import Router
from ui.widgets.StatusBarNotification import TaskListWindow, StatusBarNotification
from controller.StatusManager import StatusManager
from controller.TaskService import TaskManager
from ui.pages.ForceDirectPage import ForceDirectPage
from server.bridge import bridge

from core.crawler.CrawlerManager import crawler_manager2

class TopBar(QWidget):
    '''顶栏'''
    def __init__(self, parent=None):
        super().__init__(parent)

        self.main_layout=QHBoxLayout(self)

        self.btn_back=IconPushButton("chevron-left.svg",iconsize=24,outsize=24,color="#000000")
        self.main_layout.addWidget(self.btn_back)
        self.btn_back.clicked.connect(lambda: Router.instance().back())
        self.btn_back.setToolTip("返回上一页")
        self.btn_forward=IconPushButton("chevron-right.svg",iconsize=24,outsize=24,color="#000000")
        self.main_layout.addWidget(self.btn_forward)
        self.btn_forward.clicked.connect(lambda: Router.instance().forward())
        self.btn_forward.setToolTip("前进到下一页")


        self.QLE=CompleterLineEdit(get_serial_number)
        #self.QLE.setClearButtonEnabled(True)
        self.QLE.setMaximumWidth(200)
        self.QLE.setFixedHeight(32)
        self.QLE.setStyleSheet("""
            QLineEdit {
                color: black;  
                background-color: transparent;  /* 可选：背景透明或其他颜色 */
                border: 2px solid black;        /* 白色边框 */ 
            }
        """)
        self.btn_help=IconPushButton("circle-question-mark.svg",iconsize=24,outsize=24,color="#000000")

        self.btn_settings=IconPushButton("settings.svg",iconsize=24,outsize=24,color="#000000")

        self.main_layout.addWidget(self.QLE)
        self.main_layout.addStretch()
        self.main_layout.addWidget(self.btn_settings)
        self.main_layout.addWidget(self.btn_help)
        self.btn_settings.clicked.connect(lambda: Router.instance().push("setting"))

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("暗之眼 "+"V"+APP_VERSION)
        self.setWindowIcon(QIcon(str(ICONS_PATH / "logo.svg"))) 
        self.resize(1000, 700)
        

        #======================整体布局设置==========================
        self.init_ui()
        self.stackPageConnectMenu()
        self.init_router()

        self.registry = ShortcutRegistry()
        setup_mainwindow_actions(self, self.registry)

        self.signal_connect()


    def init_ui(self) -> None:
        '''初始化UI'''
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0) 
        
        menu_defs = [
             ("home", "首页", "house.svg"), 
             ("database", "管理", "database.svg"), 
             ("work", "作品", "film.svg"), 
             ("chart", "统计", "chart-line.svg"), 
             ("actress", "女优", "venus.svg"), 
             ("actor", "男优", "mars.svg"), 
             ("graph","关系图","share-2.svg"),
             ("av", "暗黑界", "scroll-text.svg"), 
         ]
        self.sidebar = Sidebar(menu_defs=menu_defs)#侧边栏的按钮在这里改
        self.right_widget=QWidget()
        self.right_layout=QVBoxLayout(self.right_widget)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(0)

        self.topbar=TopBar()
        self.myStatusBar = self.init_status_bar()

        self.stack = QStackedWidget()
        self.right_layout.addWidget(self.topbar)
        self.right_layout.addWidget(self.stack)
        self.right_layout.addWidget(self.myStatusBar)

        #左右两栏布局
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.right_widget)

    def init_router(self) -> None:
        '''配置路由'''
        self.router = Router(self.stack, self.sidebar)
        
        # 注册所有页面及其关联的菜单ID
        # 格式: register(route_name, page_widget, menu_id)
        
        # 1. 侧边栏主菜单页面
        self.router.register("home", self.page_home, "home")
        self.router.register("database", self.page_management, "database")
        self.router.register("chart", self.page_statistics, "chart")
        self.router.register("mutiwork", self.page_work, "work") # 作品列表
        self.router.register("actress", self.page_actress, "actress") # 女优列表
        self.router.register("actor", self.page_actor, "actor") # 男优列表
        self.router.register("av", self.page_av, "av")
        self.router.register("graph", self.page_graph, "graph")
        
        # 2. 详情页/编辑页/其他页面
        self.router.register("work", self.page_single_work, "work") # 作品详情，关联到 work 菜单
        self.router.register("single_actress", self.page_single_actress, "actress") # 女优详情，关联到 actress 菜单
        self.router.register("actress_edit", self.page_modify_actress, "actress")
        self.router.register("actor_edit", self.page_modify_actor, "actor")
        self.router.register("work_edit", self.page_management, "database") # 注意：这里如果想跳到管理页的特定tab，router需要特殊处理
        self.router.register("setting", self.page_setting, "")
        
        # 初始化路由状态（默认进入首页）
        self.router.push("home")

    def init_status_bar(self) -> QStatusBar:
        status_bar = QStatusBar()
        self.statusmanager = StatusManager(status_bar)

        self.memlabel = QLabel("内存占用:0 MB")
        status_bar.addPermanentWidget(self.memlabel)

        self.thread_count_label = QLabel("后台线程: 0")
        status_bar.addPermanentWidget(self.thread_count_label)

        self.greenbutton = StateToggleButton("sprout.svg", "#5E5E5E", "sprout.svg", "#00FF40", 16, 16)
        self.greenbutton.stateChanged.connect(global_signals.green_mode_changed.emit)
        status_bar.addPermanentWidget(self.greenbutton)

        self.taskwindow = TaskListWindow(self)
        self.notifier = StatusBarNotification(self.taskwindow)
        self.taskmanager = TaskManager.instance(self.taskwindow, self.notifier)
        status_bar.addPermanentWidget(self.notifier)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_memory)
        self.timer.timeout.connect(self.update_thread_count)
        self.timer.start(500)

        return status_bar

    def signal_connect(self) -> None:
        '''信号连接'''
        self.topbar.btn_help.clicked.connect(self.registry.actions_map["open_help"].trigger)
        self.topbar.QLE.returnPressed.connect(lambda:Router.instance().push("mutiwork", serial_number=self.topbar.QLE.text().strip()))#路由跳转
        bridge.capture_received.connect(self.handle_capture_data)
        
    def stackPageConnectMenu(self) -> None:
        '''切换页面设置与菜单的连接'''
        self.page_home=CoverBrowser(randomRec())
        self.page_management=ManagementPage()
        self.page_statistics=StatisticsPage()
        self.page_work=WorkPage()
        self.page_actress=ActressPage()
        self.page_actor=ActorPage()
        self.page_av=AvPage()
        self.page_single_actress=SingleActressPage()
        self.page_single_work=SingleWorkPage()
        self.page_modify_actress=ModifyActressPage()
        self.page_modify_actor=ModifyActorPage()
        self.page_setting=SettingPage()
        self.page_graph=ForceDirectPage()

        self.stack.addWidget(self.page_home)
        self.stack.addWidget(self.page_management)
        self.stack.addWidget(self.page_statistics)
        self.stack.addWidget(self.page_work)
        self.stack.addWidget(self.page_actress)
        self.stack.addWidget(self.page_actor)
        self.stack.addWidget(self.page_av)
        self.stack.addWidget(self.page_graph)

        self.stack.addWidget(self.page_single_actress)
        self.stack.addWidget(self.page_single_work)
        self.stack.addWidget(self.page_modify_actress)
        self.stack.addWidget(self.page_modify_actor)
        self.stack.addWidget(self.page_setting)

        self._menu_to_route = {
            "home": "home",
            "database": "database",
            "chart": "chart",
            "work": "mutiwork",
            "actress": "actress",
            "actor": "actor",
            "graph":"graph",
            "av": "av"
        }
        self.sidebar.itemClicked.connect(self._on_sidebar_clicked)

    def closeEvent(self, event) -> None:
        logging.info("--------------------程序关闭--------------------")
        set_max_window(self.isMaximized())
        #if not self.isMaximized():
            #set_size_pos(self.size(), self.pos())
        super().closeEvent(event)
        #数据库
        from core.database.connection import QSqlDatabaseManager
        #这个QSqlDatabase是长连接，最后关闭
        db_manager = QSqlDatabaseManager()
        db_manager.close_all()
        from core.database.db_utils import clear_temp_folder
        clear_temp_folder()#退出时清理临时数据

    @Slot()
    def handle_capture(self) -> None:
        logging.debug("触发快捷键C")
        cur_page=self.stack.currentWidget()
        from utils.utils import capture_full
        match cur_page:
            case self.page_home:
                capture_full(self.page_home)
            case self.page_work:  
                capture_full(self.page_work.lazy_area.widget())
            case self.page_actress:
                capture_full(self.page_actress.lazy_area.widget())
            case self.page_single_actress:
                capture_full(self.page_single_actress.single_actress_info)

    @Slot()
    def update_memory(self) -> None:
        '''更新内存'''
        process = psutil.Process(os.getpid())
        mem_main: int = process.memory_info().rss
        mem_children: int = sum((p.memory_info().rss for p in process.children(recursive=True)), 0)
        total_mb: float = (mem_main + mem_children) / 1024 ** 2
        main_mb: float = mem_main / 1024 ** 2
        children_mb: float = mem_children / 1024 ** 2
        self.memlabel.setText(f"内存使用: {total_mb:.2f} MB (主:{main_mb:.2f}, 子:{children_mb:.2f})")

    @Slot()
    def update_thread_count(self) -> None:
        """更新状态栏显示后台线程数量"""
        active = QThreadPool.globalInstance().activeThreadCount()

        self.thread_count_label.setText(f"后台线程: {active}")

    @Slot(str)
    def _on_sidebar_clicked(self, menu_id: str) -> None:
        """处理侧边栏点击事件：通过路由跳转"""
        route_name = self._menu_to_route.get(menu_id)
        if route_name:
            self.router.push(route_name)

    @Slot(dict)
    def handle_capture_data(self, data: dict) -> None:
        """
        处理来自插件的抓取数据
        """
        logging.info(f"Main thread received capture data: {data.get('url')}")
        self.myStatusBar.showMessage(f"收到抓取数据: {data.get('title', 'Unknown')}", 5000)
        
        content_str = data.get("content", "")
        
        # 解析番号数组，去除空白并过滤空字符串
        serial_numbers = [s.strip() for s in content_str.split(',') if s.strip()]
        
        logging.info(f"收到抓取数据,标题: {data.get('title')}\nURL: {data.get('url')}\n番号列表({len(serial_numbers)}个): {serial_numbers}")
        
        if serial_numbers:
            from ui.dialogs.AddQuickWork import AddQuickWork
            dialog = AddQuickWork()
            dialog.load_serials(serial_numbers)
            dialog.exec()

        
 