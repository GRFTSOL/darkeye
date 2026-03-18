from PySide6.QtGui import QAction, QKeySequence, QDesktopServices
from PySide6.QtCore import QUrl


def setup_mainwindow_actions(window, registry):
    '''把快捷键与action进行绑定'''
    from ui.dialogs.open import (
        openAddMasturbationDialog,
        openAddQuickWorkDialog,
        openAddMakeLoveDialog,
        openAddSexualArousalDialog
    )
    from utils.utils import capture_full

    add_masturbation = QAction("添加撸管记录", window)
    add_masturbation.setShortcut(
        QKeySequence(registry.get_shortcut("add_masturbation_record"))
    )
    add_masturbation.triggered.connect(openAddMasturbationDialog)
    registry.actions_map["add_masturbation_record"] = add_masturbation

    add_quick_work = QAction("快速添加番号", window)
    add_quick_work.setShortcut(
        QKeySequence(registry.get_shortcut("add_quick_work"))
    )
    add_quick_work.triggered.connect(openAddQuickWorkDialog)
    registry.actions_map["add_quick_work"] = add_quick_work

    add_makelove = QAction("添加做爱记录", window)
    add_makelove.setShortcut(
        QKeySequence(registry.get_shortcut("add_makelove_record"))
    )
    add_makelove.triggered.connect(openAddMakeLoveDialog)
    registry.actions_map["add_makelove_record"] = add_makelove

    add_sexual_rousal = QAction("添加晨勃记录", window)
    add_sexual_rousal.setShortcut(
        QKeySequence(registry.get_shortcut("add_sexual_rousal_record"))
    )
    add_sexual_rousal.triggered.connect(openAddSexualArousalDialog)
    registry.actions_map["add_sexual_rousal_record"] = add_sexual_rousal

    open_help_action = QAction("打开帮助", window)
    open_help_action.setShortcut(
        QKeySequence(registry.get_shortcut("open_help"))
    )
    open_help_action.triggered.connect(
        lambda: QDesktopServices.openUrl(QUrl("https://de4321.github.io/darkeye/"))
    )
    registry.actions_map["open_help"] = open_help_action

    focus_search = QAction("搜索", window)
    focus_search.setShortcut(
        QKeySequence(registry.get_shortcut("search"))
    )
    #focus_search.triggered.connect(lambda: window.topbar.QLE.setFocus())
    registry.actions_map["search"] = focus_search

    all_capture = QAction("全软件截图", window)
    all_capture.setShortcut(
        QKeySequence(registry.get_shortcut("allcapture"))
    )
    all_capture.triggered.connect(lambda: capture_full(window))
    registry.actions_map["allcapture"] = all_capture

    capture = QAction("部分截图", window)
    capture.setShortcut(
        QKeySequence(registry.get_shortcut("capture"))
    )
    capture.triggered.connect(window.handle_capture)
    registry.actions_map["capture"] = capture

    window.addActions(list(registry.actions_map.values()))

