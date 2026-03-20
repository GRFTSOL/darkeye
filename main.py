# ========== darkeye_ui 组件库使用说明 ==========
# 1. 主题管理器：在任意页面通过 app_context.get_theme_manager() 获取，传给需要 theme_manager 的组件。
# 2. 示例（在某个 QWidget 页面内）：
#    from app_context import get_theme_manager
#    from darkeye_ui import Button, Label, ToggleSwitch, StateToggleButton, IconPushButton
#    theme_mgr = get_theme_manager()
#    btn = Button("确定", theme_manager=theme_mgr)
#    switch = ToggleSwitch(theme_manager=theme_mgr)
# 3. 布局与图标：from darkeye_ui import FlowLayout, get_builtin_icon
# 4. 主题切换：theme_mgr.set_theme(app, ThemeId.LIGHT/DARK/RED)，然后可重新合并样式或仅刷新依赖 token 的组件。

# Windows CMD 中文乱码修复：在首次输出前将控制台代码页设为 UTF-8
import sys
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        pass


def load_global_style():
    """加载全局样式表（项目 main.qss）"""
    from pathlib import Path
    from config import QSS_PATH
    style = Path(QSS_PATH / "main.qss").read_text(encoding="utf-8")
    return style


def load_app_stylesheet(app):
    """仅通过 ThemeManager 应用 darkeye_ui 组件库样式（mymain.qss + 当前主题 token），并设置全局 ThemeManager。

    注意：全局样式现在完全由 ThemeManager.set_theme 控制，以避免重复加载 QSS 时丢失
    像下拉箭头这类依赖扩展令牌（如 chevron_down_arrow_path）的样式。
    """
    from darkeye_ui.design import ThemeManager, ThemeId
    from app_context import set_theme_manager

    theme_mgr = ThemeManager()
    from config import get_theme_id, get_custom_primary
    try:
        initial_theme = ThemeId[get_theme_id()]
    except (KeyError, TypeError):
        initial_theme = ThemeId.LIGHT
    if initial_theme in (ThemeId.LIGHT, ThemeId.DARK):
        saved_primary = get_custom_primary()
        if saved_primary:
            theme_mgr.set_custom_primary(saved_primary)
    theme_mgr.set_theme(app, initial_theme)
    set_theme_manager(theme_mgr)


def apply_theme(theme_id):
    """根据主题 ID 重新应用 darkeye_ui 主题样式，供设置页主题切换调用。

    统一通过 ThemeManager.set_theme 处理，以保证像下拉箭头这类依赖扩展令牌的样式完整生效。
    """
    from PySide6.QtWidgets import QApplication
    from app_context import get_theme_manager
    from darkeye_ui.design import ThemeId

    app = QApplication.instance()
    if app is None:
        return
    theme_mgr = get_theme_manager()
    if theme_mgr is None:
        return
    if isinstance(theme_id, str):
        theme_id = ThemeId(theme_id)
    theme_mgr.set_theme(app, theme_id)

def _run_main_app():
    
    # 是否显示启动 splash，可通过命令行参数关闭

    show_splash = False

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
    import os
    os.environ["QSG_RHI_BACKEND"] = "opengl"   # 必须尽早，放在导入/创建 Quick 相关对象之前
    #强制 Qt Quick 使用 OpenGL，与 QOpenGLWidget 兼容（否则 Windows 默认 D3D11 会冲突）

    from PySide6.QtWidgets import QApplication, QDialog, QSplashScreen
    from PySide6.QtGui import QPixmap, QSurfaceFormat
    from PySide6.QtCore import Qt, QTimer

    #OpenGL设置
    QApplication.setAttribute(Qt.AA_UseDesktopOpenGL)#不知道这个要不要加，但是这个好像没有什么用
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setSwapBehavior(QSurfaceFormat.DoubleBuffer)
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)

    profiler.measure_import("config")
    from config import ICONS_PATH, is_first_lunch, set_first_luch
    profiler.checkpoint("Qt组件导入完成")

    # 创建应用和启动画面
    with profiler.measure_execution("创建QApplication", sync=True):
        import sys
        app = QApplication(sys.argv)
    profiler.checkpoint("创建应用")


    #try:
    #    # 强制 Qt Quick 使用 OpenGL，与 QOpenGLWidget 兼容（否则 Windows 默认 D3D11 会冲突）
    #    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
    #    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
    #except ImportError:
    #    pass

    splash = None
    if show_splash:
        # 启动画面用 PNG 避免 SVG 解析耗时
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


    # 首次启动协议对话框（已注释）
    if is_first_lunch():#判断是否是第一次启动
        from ui.dialogs import TermsDialog
        dialog=TermsDialog()

        if dialog.exec() == QDialog.Accepted:# type: ignore[arg-type]
            set_first_luch(False)
        else:
            set_first_luch(True)
            if show_splash and splash is not None:
                splash.close()
            sys.exit(0)  # 拒绝则退出

    # 数据库初始化（同步，阻塞主线程）
    if show_splash and splash is not None:
        splash.showMessage("数据库初始化")
    profiler.measure_import("core.database.init")
    profiler.measure_import("core.database.migrations")
    profiler.measure_import("config")
    from core.database.init import init_database, init_private_db
    from core.database.migrations import check_and_upgrade_private_db, check_and_upgrade_public_db
    from config import DATABASE, PRIVATE_DATABASE

    with profiler.measure_execution("数据库初始化（全部）", sync=True):
        with profiler.measure_execution("init_private_db", sync=True):
            init_private_db()
        with profiler.measure_execution("check_and_upgrade_private_db", sync=True):
            check_and_upgrade_private_db()
        with profiler.measure_execution("check_and_upgrade_public_db", sync=True):
            check_and_upgrade_public_db()
        with profiler.measure_execution("init_database", sync=True):
            init_database(DATABASE, PRIVATE_DATABASE)
    profiler.checkpoint("数据库初始化完成")

    # 异步启动图初始化（后台进行）
    if show_splash and splash is not None:
        splash.showMessage("初始化图...")
    profiler.measure_import("core.graph.graph_manager")
    from core.graph.graph_manager import GraphManager

    with profiler.measure_execution("GraphManager导入和实例化", sync=True):
        manager = GraphManager.instance()
        manager.initialize()
    profiler.checkpoint("图初始化线程启动完成")

    # 样式表加载（项目 main.qss + darkeye_ui 组件库样式，并注册 ThemeManager）
    if show_splash and splash is not None:
        splash.showMessage("样式表加载")
    with profiler.measure_execution("加载样式表", sync=True):
        load_app_stylesheet(app)
    profiler.checkpoint("样式表加载完成")

    # 主窗口加载（可能是最重的操作）
    if show_splash and splash is not None:
        splash.showMessage("主窗口加载")
    profiler.measure_import("ui.main_window")
    from ui.main_window import MainWindow

    with profiler.measure_execution("MainWindow构造", sync=True):
        window = MainWindow()

    with profiler.measure_execution("MainWindow显示", sync=True):
        window.show()
        if show_splash and splash is not None:
            splash.finish(window)
    profiler.checkpoint("主窗口显示完成")

    # 界面已就绪，再在后台启动 API（用户通常不会立刻用，优化开屏速度）
    profiler.measure_import("server")
    from server import start_server
    QTimer.singleShot(0, lambda: start_server())
    profiler.checkpoint("API服务器线程启动（延迟）")

    # 周五 18:00 后自动检查更新（每周一次，弹窗提示）
    from ui.pages.settings.about import maybe_auto_check_update
    QTimer.singleShot(2000, lambda: maybe_auto_check_update(window))

    # 打印性能分析摘要
    profiler.print_summary()

    logger.info("--------------------程序启动完成，进入事件循环--------------------")
    sys.exit(app.exec())


if __name__ == "__main__":
    '''
    # 打包后 multiprocessing 使用 spawn：子进程会重新执行本脚本，必须跳过 GUI 避免无限开窗
    import multiprocessing
    multiprocessing.freeze_support()
    if multiprocessing.current_process().name == "ForceDirectSimulationProcess":
        # 子进程：仅由 multiprocessing 引导执行 simulation worker，不跑主流程
        pass
    else:
    '''
    #现在不需要多进程，就这样
    _run_main_app()

