def open_add_actor_dialog():
    from ui.dialogs import AddActorDialog

    dialog = AddActorDialog()
    dialog.exec()


def open_add_sexual_arousal_dialog():
    from ui.dialogs import AddSexualArousalDialog

    dialog = AddSexualArousalDialog()
    dialog.exec()


def open_add_masturbation_dialog():
    from ui.dialogs import AddMasturbationDialog

    dialog = AddMasturbationDialog()
    dialog.exec()


def open_add_quick_work_dialog():
    from ui.dialogs import AddQuickWork

    dialog = AddQuickWork()
    dialog.exec()


def open_add_make_love_dialog():
    from ui.dialogs import AddMakeLoveDialog

    dialog = AddMakeLoveDialog()
    dialog.exec()


from ui.pages.management.AddWorkTabPage3 import AddWorkTabPage3


def open_add_actress_dialog(addworktab: AddWorkTabPage3):
    from ui.dialogs import AddActressDialog

    dialog = AddActressDialog()
    dialog.success.connect(addworktab.actressselector.handle_actress_result)
    dialog.exec()  # 模态显示对话框，阻塞主窗口直到关闭
