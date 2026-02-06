from PySide6.QtWidgets import QWidget,QStackedWidget,QHBoxLayout, QVBoxLayout,QLabel,QStatusBar,QMainWindow
from PySide6.QtCore import QTimer,Slot,QThreadPool
from PySide6.QtGui import QIcon
import os,psutil,logging

from config import ICONS_PATH,APP_VERSION,set_max_window
from ui.basic import IconPushButton,ToggleSwitch,StateToggleButton
from controller.GlobalSignalBus import global_signals
from core.database.query import get_serial_number
from ui.widgets.text.CompleterLineEdit import CompleterLineEdit
from controller import ShortcutRegistry
from controller.ShortcutBindings import setup_mainwindow_actions
from ui.widgets.Sidebar2 import Sidebar2
from ui.navigation.router import Router
from ui.widgets.StatusBarNotification import TaskListWindow, StatusBarNotification
from controller.StatusManager import StatusManager
from controller.TaskService import TaskManager
from server.bridge import bridge
from core.crawler.CrawlerManager import get_manager
get_manager()

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
        # self.stackPageConnectMenu() # 已在 init_router 中实现
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
             ("shelf", "书架", "scroll-text.svg"),
             ("av", "暗黑界", "scroll-text.svg"), 
         ]
        self.sidebar = Sidebar2(menu_defs=menu_defs)#侧边栏的按钮在这里改
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
        
        # 1. 定义工厂函数
        def create_home():
            from ui.pages.CoverBrowser import CoverBrowser
            from core.recommendation.Recommend import randomRec
            return CoverBrowser(randomRec())

        def create_dashboard():
            from ui.pages.DashboardPage import DashboardPage
            return DashboardPage()

        _management_page = None
        def create_management():
            nonlocal _management_page
            if _management_page is None:
                from ui.pages.ManagementPage import ManagementPage
                _management_page = ManagementPage()
            return _management_page
            
        def create_statistics():
            from ui.pages.StatisticsPage import StatisticsPage
            return StatisticsPage()
            
        def create_work():
            from ui.pages.WorkPage import WorkPage
            return WorkPage()
            
        def create_actress():
            from ui.pages.ActressPage import ActressPage
            return ActressPage()
            
        def create_actor():
            from ui.pages.ActorPage import ActorPage
            return ActorPage()
            
        def create_av():
            from ui.pages.AvPage import AvPage
            return AvPage()
            
        def create_graph():
            from ui.pages.ForceDirectPage import ForceDirectPage
            return ForceDirectPage()
            
        def create_shelf_demo():
            from ui.pages.ShelfDemoPage import ShelfDemoPage
            return ShelfDemoPage()
            
        def create_single_work():
            from ui.pages.SingleWorkPage import SingleWorkPage
            return SingleWorkPage()
            
        def create_single_actress():
            from ui.pages.SingleActressPage import SingleActressPage
            return SingleActressPage()
            
        def create_modify_actress():
            from ui.pages.ModifyActressPage import ModifyActressPage
            return ModifyActressPage()
            
        def create_modify_actor():
            from ui.pages.ModifyActorPage import ModifyActorPage
            return ModifyActorPage()
            
        def create_setting():
            from ui.pages.SettingPage import SettingPage
            return SettingPage()

        # 2. 注册路由 (route_name, factory, menu_id)
        # 侧边栏主菜单页面
        # 保留旧首页作为隐藏入口，新的 Dashboard 绑定到侧边栏的“首页”按钮
        self.router.register("home", create_home, None)
        self.router.register("dashboard", create_dashboard, "home")
        self.router.register("database", create_management, "database")
        self.router.register("chart", create_statistics, "chart")
        self.router.register("mutiwork", create_work, "work") # 作品列表
        self.router.register("actress", create_actress, "actress") # 女优列表
        self.router.register("actor", create_actor, "actor") # 男优列表
        self.router.register("av", create_av, "av")
        self.router.register("graph", create_graph, "graph")
        
        # 详情页/编辑页/其他页面
        self.router.register("shelf_demo", create_shelf_demo, None)
        self.router.register("work", create_single_work, "work") # 作品详情
        self.router.register("single_actress", create_single_actress, "actress") # 女优详情
        self.router.register("actress_edit", create_modify_actress, "actress")
        self.router.register("actor_edit", create_modify_actor, "actor")
        self.router.register("work_edit", create_management, "database") # 注意：这里如果想跳到管理页的特定tab，router需要特殊处理
        self.router.register("setting", create_setting, "")
        
        # 3. 建立菜单到路由的映射 (供 Sidebar 点击使用)
        self._menu_to_route = {
            "home": "dashboard",
            "database": "database",
            "chart": "chart",
            "work": "mutiwork",
            "actress": "actress",
            "actor": "actor",
            "graph": "graph",
            "shelf": "shelf_demo",
            "av": "av"
        }
        self.sidebar.itemClicked.connect(self._on_sidebar_clicked)
        '''
        ### 什么时候有必要手动加单例？
        判断标准非常简单，只有满足以下 任意一点 时才需要：

    1. 多路由复用 ：像这次一样，你有多个不同的 route_name （如 view 和 edit ），但逻辑上它们应该显示同一个物理页面实例。
    2. 全局资源独占 ：页面内部持有了必须全局唯一的资源（比如绑定了某个特定的 WebSocket 连接、硬件端口），绝对不允许被实例化两次。
        '''
        # 延后到 show 之后再加载首页，主窗口先显示框架，缩短“主窗口显示完成”耗时
        QTimer.singleShot(0, lambda: self.router.push("dashboard"))

    def _on_sidebar_clicked(self, menu_id: str):
        if menu_id in self._menu_to_route:
            self.router.push(self._menu_to_route[menu_id])

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
        
    # stackPageConnectMenu has been removed and integrated into init_router

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
        cur_route = self.router.get_current_route()
        cur_page = self.stack.currentWidget()
        if not cur_page: return
        
        from utils.utils import capture_full
        
        match cur_route:
            case "home":
                capture_full(cur_page)
            case "mutiwork":  
                # 需要确认 cur_page 是否有 lazy_area 属性，因为现在是动态加载的
                if hasattr(cur_page, "lazy_area"):
                    capture_full(cur_page.lazy_area.widget())
            case "actress":
                if hasattr(cur_page, "lazy_area"):
                    capture_full(cur_page.lazy_area.widget())
            case "single_actress":
                if hasattr(cur_page, "single_actress_info"):
                    capture_full(cur_page.single_actress_info)

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

        
 