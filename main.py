import sys
from PySide6.QtWidgets import QApplication,QDialog,QSplashScreen

from ui.main_window import MainWindow
from core.utils import log_config #全局导入一次就可以用logging来打印了
import logging
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from core.database.init import init_database,init_private_db
from config import DATABASE,PRIVATE_DATABASE,is_first_lunch,set_first_luch,ICONS_PATH
from core.database.migrations import check_and_upgrade_private_db,check_and_upgrade_public_db
from core.graph.simulation_process_main import get_global_simulation_process
from core.graph.graph_manager import GraphManager
from server import start_server
import time
from PySide6.QtCore import QTimer

def load_global_style():
    """加载全局样式表"""
    from pathlib import Path
    from config import QSS_PATH
    style = Path(QSS_PATH/"main.qss").read_text(encoding="utf-8")
    return style

if __name__ == "__main__":
    t_start = time.perf_counter()
    app = QApplication()

    #下面是启动屏
    pixmap = QPixmap(str(ICONS_PATH / "splash.png"))
    if pixmap.isNull():
        pixmap = QPixmap(str(ICONS_PATH / "logo.svg"))
    splash = QSplashScreen(pixmap)
    splash.show()
    app.processEvents()

    if is_first_lunch():#判断是否是第一次启动
        from ui.dialogs import TermsDialog
        dialog=TermsDialog()

        if dialog.exec() == QDialog.Accepted:# type: ignore[arg-type]
            set_first_luch(False)
        else:
            set_first_luch(True)
            splash.close()
            sys.exit(0)  # 拒绝则退出

    splash.showMessage("Sim进程启动")
    get_global_simulation_process()
    splash.showMessage("Graph图初始化")
    manager = GraphManager.instance()
    manager.initialize()
    splash.showMessage("启动本地API服务")
    start_server()# 启动本地API服务

    init_private_db()#先判断有无私库
    check_and_upgrade_private_db()#考虑后台执行
    check_and_upgrade_public_db()#

    init_database(DATABASE,PRIVATE_DATABASE)
    splash.showMessage("数据库初始化完成")
    logging.info("--------------------加载样式--------------------")
    app.setStyleSheet(load_global_style())
    splash.showMessage("样式表加载完成")
    logging.info("--------------------程序启动--------------------")

    window = MainWindow()
    window.show()
    splash.finish(window)

    def on_gui_ready():
        t_end = time.perf_counter()
        elapsed = t_end - t_start
        # 使用 print 或 logging 输出
        logging.info(f"GUI 加载时间: {elapsed:.4f} seconds")
    QTimer.singleShot(0, on_gui_ready)
    logging.info("--------------------程序启动完成--------------------")
    sys.exit(app.exec())
