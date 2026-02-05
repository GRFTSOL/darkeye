

def load_global_style():
    """加载全局样式表"""
    from pathlib import Path
    from config import QSS_PATH
    style = Path(QSS_PATH/"main.qss").read_text(encoding="utf-8")
    return style


if __name__ == "__main__":
    # 初始化性能分析器（必须在log_config之前，因为log_config本身也需要时间）
    from core.utils.profiler import get_profiler
    profiler = get_profiler()
    profiler.checkpoint("程序启动")
    
    # 导入日志配置（测量导入时间）
    profiler.measure_import("core.utils.log_config")
    from core.utils import log_config
    import logging
    logger = logging.getLogger(__name__)
    profiler.checkpoint("日志系统初始化")

    # 仅导入必要的 GUI 启动组件（测量导入时间）
    profiler.measure_import("PySide6.QtWidgets")
    profiler.measure_import("PySide6.QtGui")
    from PySide6.QtWidgets import QApplication, QDialog, QSplashScreen
    from PySide6.QtGui import QPixmap

    
    profiler.measure_import("config")
    from config import ICONS_PATH, is_first_lunch, set_first_luch
    profiler.checkpoint("Qt组件导入完成")

    # 创建应用和启动画面
    with profiler.measure_execution("创建QApplication", sync=True):
        import sys
        app = QApplication(sys.argv)
    profiler.checkpoint("创建应用")

    # 启动画面用 PNG 避免 SVG 解析耗时（约省 1s）
    splash_icon = ICONS_PATH / "logo.png"
    if not splash_icon.exists():
        splash_icon = ICONS_PATH / "logo.svg"
    pixmap = QPixmap(str(splash_icon))
    profiler.checkpoint("加载图片")
    
    with profiler.measure_execution("加载启动画面", sync=True):
        splash = QSplashScreen(pixmap)
        splash.setEnabled(False)
        splash.show()
        app.processEvents()
    profiler.checkpoint("启动画面显示")
    
    # 首次启动协议对话框
    if is_first_lunch():
        profiler.measure_import("ui.dialogs")
        from ui.dialogs import TermsDialog
        
        with profiler.measure_execution("显示首次启动对话框", sync=True):
            dialog = TermsDialog()
            if dialog.exec() == QDialog.Accepted:  # type: ignore[arg-type]
                set_first_luch(False)
            else:
                set_first_luch(True)
                splash.close()
                sys.exit(0)  # 拒绝则退出
        profiler.checkpoint("首次启动对话框完成")

    # 1. 启动 Sim 进程 (耗时操作，尽早启动)
    splash.showMessage("Sim进程启动")
    profiler.measure_import("core.graph.simulation_process_main")
    from core.graph.simulation_process_main import get_global_simulation_process
    
    with profiler.measure_execution("启动Sim进程", sync=True):
        get_global_simulation_process()
    profiler.checkpoint("Sim进程启动完成")

    # 启动本地API服务（异步）
    splash.showMessage("启动本地API服务")
    profiler.measure_import("server")
    from server import start_server
    start_server()
    profiler.checkpoint("API服务器线程启动")

    
    # 数据库初始化（同步，阻塞主线程）
    splash.showMessage("数据库初始化")
    profiler.measure_import("core.database.init")
    profiler.measure_import("core.database.migrations")
    profiler.measure_import("config")
    from core.database.init import init_database, init_private_db
    from core.database.migrations import check_and_upgrade_private_db, check_and_upgrade_public_db
    from config import DATABASE, PRIVATE_DATABASE

    with profiler.measure_execution("数据库初始化（全部）", sync=True):
        with profiler.measure_execution("init_private_db", sync=True):
            init_private_db()  # 先判断有无私库
        
        with profiler.measure_execution("check_and_upgrade_private_db", sync=True):
            check_and_upgrade_private_db()  # 考虑后台执行
        
        with profiler.measure_execution("check_and_upgrade_public_db", sync=True):
            check_and_upgrade_public_db()
        
        with profiler.measure_execution("init_database", sync=True):
            init_database(DATABASE, PRIVATE_DATABASE)
    profiler.checkpoint("数据库初始化完成")

    # 异步启动图初始化（后台进行）
    splash.showMessage("初始化图...")
    profiler.measure_import("core.graph.graph_manager")
    from core.graph.graph_manager import GraphManager
    
    with profiler.measure_execution("GraphManager导入和实例化", sync=True):
        manager = GraphManager.instance()
        manager.initialize()  # 这只是启动后台线程，不阻塞
    profiler.checkpoint("图初始化线程启动完成")

    # 样式表加载
    splash.showMessage("样式表加载")
    with profiler.measure_execution("加载样式表", sync=True):
        app.setStyleSheet(load_global_style())
    profiler.checkpoint("样式表加载完成")

    # 主窗口加载（可能是最重的操作）
    splash.showMessage("主窗口加载")
    profiler.measure_import("ui.main_window")
    from ui.main_window import MainWindow
    
    with profiler.measure_execution("MainWindow构造", sync=True):
        window = MainWindow()
    
    with profiler.measure_execution("MainWindow显示", sync=True):
        window.show()
        splash.finish(window)
    profiler.checkpoint("主窗口显示完成")

    # 打印性能分析摘要
    profiler.print_summary()
    
    logger.info("--------------------程序启动完成，进入事件循环--------------------")
    sys.exit(app.exec())
