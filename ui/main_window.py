from PySide6.QtWidgets import QWidget, QStackedWidget, QHBoxLayout, QMainWindow, QLabel
from PySide6.QtCore import QTimer, Slot
from PySide6.QtGui import QIcon
import logging

from config import ICONS_PATH,APP_VERSION,set_max_window
from controller.ShortcutRegistry import ShortcutRegistry
from controller.ShortcutBindings import setup_mainwindow_actions#这个准备数据的操作是可以放在后台的但是QAction一定要放主线程
from darkeye_ui.components import Sidebar
from ui.navigation.router import Router
from controller.GlobalSignalBus import global_signals



class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("暗之眼 "+"V"+APP_VERSION)
        self.setWindowIcon(QIcon(str(ICONS_PATH / "logo.svg"))) 
        self.resize(1200, 800)
        self.open=False

        #======================整体布局设置==========================
        self.init_ui()
        # self.stackPageConnectMenu() # 已在 init_router 中实现
        self.init_router()

        self.registry = ShortcutRegistry()
        setup_mainwindow_actions(self, self.registry)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_memory)
        self.timer.start(1000)  # 1秒更新一次，减少标题栏重绘

        self.signal_connect()

        # 延后到窗口 show / event loop 启动后再初始化爬虫管理器，避免 import/构造阻塞主窗口首帧
        QTimer.singleShot(0, self._ensure_crawler_manager_initialized)

    @Slot()
    def _ensure_crawler_manager_initialized(self) -> None:
        # 必须在主线程首次创建（CrawlerManager.get_manager 内部会校验）
        from core.crawler.CrawlerManager import get_manager
        self._crawler_manager = get_manager()


    def init_ui(self) -> None:
        '''初始化UI'''
        central = QWidget()
        self.setCentralWidget(central)
        

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0) 
        
        menu_defs = [  # 内置图标名或 .svg 外部文件
            ("home", "首页", "house"),
            ("database", "管理", "database"),
            ("work", "作品", "film"),
            ("chart", "统计", "chart_line"),
            ("actress", "女优", "venus"),
            ("actor", "男优", "mars"),
            ("graph", "关系图", "share_2"),
            ("shelf", "书架", "library_big"),
            ("av", "暗黑界", "scroll_text"),
            ("bell", "通知", "bell"),
        ]
        self.sidebar = Sidebar(menu_defs=menu_defs)#侧边栏的按钮在这里改

        self.stack = QStackedWidget()


        # 左右两栏布局
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.stack)



    def init_router(self) -> None:
        '''配置路由'''
        self.router = Router(self.stack, self.sidebar)
        
        # 1. 定义工厂函数
        def create_home():
            #from ui.pages.CoverBrowser import CoverBrowser
            #from core.recommendation.Recommend import randomRec
            #return CoverBrowser(randomRec())
            from ui.pages.HomePage import HomePage
            return HomePage()

        def create_test_page():
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
            
        def create_shelf():
            from ui.pages.ShelfPage import ShelfPage
            return ShelfPage()

        def create_workspace_demo():
            from ui.pages.WorkspaceDemoPage import WorkspaceDemoPage
            return WorkspaceDemoPage()
            
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
        
        #def create_help():
        #    from ui.pages.HelpPage import HelpPage
        #    return HelpPage()

        def create_inbox():
            from ui.pages.InboxPage import InboxPage
            return InboxPage()

        # 2. 注册路由 (route_name, factory, menu_id)
        # 侧边栏主菜单页面
        # 保留旧首页作为隐藏入口，新的 Dashboard 绑定到侧边栏的“首页”按钮
        self.router.register("home", create_home, "home")
        self.router.register("test_page", create_test_page, None)
        self.router.register("database", create_management, "database")
        self.router.register("chart", create_statistics, "chart")
        self.router.register("mutiwork", create_work, "work") # 作品列表
        self.router.register("actress", create_actress, "actress") # 女优列表
        self.router.register("actor", create_actor, "actor") # 男优列表
        self.router.register("av", create_av, "av")
        self.router.register("graph", create_graph, "graph")
        
        # 详情页/编辑页/其他页面
        self.router.register("shelf", create_shelf, "shelf")
        self.router.register("workspace_demo", create_workspace_demo, None)
        self.router.register("work", create_single_work, "work") # 作品详情
        self.router.register("single_actress", create_single_actress, "actress") # 女优详情
        self.router.register("actress_edit", create_modify_actress, "actress")
        self.router.register("actor_edit", create_modify_actor, "actor")
        self.router.register("work_edit", create_management, "database") # 注意：这里如果想跳到管理页的特定tab，router需要特殊处理
        self.router.register("setting", create_setting, "setting")
        #self.router.register("help", create_help, "help")
        self.router.register("inbox", create_inbox, "bell")
        
        # 3. 建立菜单到路由的映射 (供 Sidebar 点击使用)
        self._menu_to_route = {
            "home": "home",
            "database": "database",
            "chart": "chart",
            "work": "mutiwork",
            "actress": "actress",
            "actor": "actor",
            "graph": "graph",
            "shelf": "shelf",
            "av": "av",
            "setting": "setting",
            #"help": "help",
            "bell": "inbox",
        }
        self.sidebar.itemClicked.connect(self._on_sidebar_clicked)
        self.sidebar.backwardClicked.connect(lambda: Router.instance().back())
        self.sidebar.forwardClicked.connect(lambda: Router.instance().forward())

        '''
        ### 什么时候有必要手动加单例？
        判断标准非常简单，只有满足以下 任意一点 时才需要：

    1. 多路由复用 ：像这次一样，你有多个不同的 route_name （如 view 和 edit ），但逻辑上它们应该显示同一个物理页面实例。
    2. 全局资源独占 ：页面内部持有了必须全局唯一的资源（比如绑定了某个特定的 WebSocket 连接、硬件端口），绝对不允许被实例化两次。
        '''
        # 延后到 show 之后再加载首页，主窗口先显示框架，缩短“主窗口显示完成”耗时
        QTimer.singleShot(0, lambda: self.router.push("home"))


    def signal_connect(self) -> None:
        '''信号连接'''
        from server.bridge import bridge
        bridge.capture_received.connect(self.handle_capture_data)
        


    def closeEvent(self, event) -> None:
        logging.info("--------------------程序关闭--------------------")
        set_max_window(self.isMaximized())
        #if not self.isMaximized():
            #set_size_pos(self.size(), self.pos())
        super().closeEvent(event)
        from core.database.db_utils import clear_temp_folder
        clear_temp_folder()  # 退出时清理临时数据

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
        """更新内存（仅在前台时更新标题，降低开销）"""
        if not self.isVisible() or not self.isActiveWindow():
            return
        import psutil
        import os
        process = psutil.Process(os.getpid())
        mem_main: int = process.memory_info().rss
        main_mb: float = mem_main / 1024 ** 2
        self.setWindowTitle("暗之眼 " + "V" + APP_VERSION + f" 内存使用: {main_mb:.2f} MB")

    @Slot()
    def update_thread_count(self) -> None:
        """更新状态栏显示后台线程数量"""
        from PySide6.QtCore import QThreadPool
        active = QThreadPool.globalInstance().activeThreadCount()

        self.thread_count_label.setText(f"后台线程: {active}")

    @Slot(str)
    def _on_sidebar_clicked(self, menu_id: str) -> None:
        """处理侧边栏点击事件：通过路由跳转"""
        # 1. 前两个：历史后退 / 前进（不通过路由表跳转）
        if menu_id == "back":
            Router.instance().back()
            return
        if menu_id == "forward":
            Router.instance().forward()
            return
        # 2. 帮助按钮：直接触发与快捷键 H 相同的 QAction（open_help）
        if menu_id == "help":
            try:
                action = getattr(self, "registry", None) and self.registry.actions_map.get("open_help")
                if action is not None:
                    action.trigger()
            except Exception:
                logging.exception("触发帮助动作失败")
            return
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


 