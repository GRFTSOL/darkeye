def openAddActorDialog():
    from ui.dialogs import AddActorDialog

    dialog = AddActorDialog()
    dialog.exec()


def openAddSexualArousalDialog():
    from ui.dialogs import AddSexualArousalDialog

    dialog = AddSexualArousalDialog()
    dialog.exec()


def openAddMasturbationDialog():
    from ui.dialogs import AddMasturbationDialog

    dialog = AddMasturbationDialog()
    dialog.exec()


def openAddQuickWorkDialog():
    from ui.dialogs import AddQuickWork

    dialog = AddQuickWork()
    dialog.exec()


def openAddMakeLoveDialog():
    from ui.dialogs import AddMakeLoveDialog

    dialog = AddMakeLoveDialog()
    dialog.exec()


from ui.pages.management.AddWorkTabPage3 import AddWorkTabPage3


def openAddActressDialog(addworktab: AddWorkTabPage3):
    from ui.dialogs import AddActressDialog

    dialog = AddActressDialog()
    dialog.success.connect(addworktab.actressselector.handle_actress_result)
    dialog.exec()  # 模态显示对话框，阻塞主窗口直到关闭
