import sys
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QLabel,
    QTextEdit,
    QCalendarWidget,
    QWidget,
    QVBoxLayout,
)
from PySide6.QtCore import Qt
import PySide6QtAds as ads


class MyMainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PySide6-QtAds 基础示例")
        self.resize(800, 600)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)  # 消除边缘白边

        # 拖拽中间 splitter 时实时更新布局（默认只显示轮廓，松手才更新）
        ads.CDockManager.setConfigFlag(ads.CDockManager.OpaqueSplitterResize, True)
        ads.CDockManager.setConfigFlag(ads.CDockManager.FocusHighlighting, True)
        # 隐藏 Tab 栏右侧的下拉菜单按钮
        ads.CDockManager.setConfigFlag(
            ads.CDockManager.DockAreaHasTabsMenuButton, False
        )
        # 隐藏 Tab 栏右侧的关闭按钮（全局性质）
        ads.CDockManager.setConfigFlag(ads.CDockManager.DockAreaHasCloseButton, False)
        ads.CDockManager.setConfigFlag(ads.CDockManager.DockAreaHasUndockButton, False)

        # 1. 创建 DockManager
        # 它是所有 Dock 窗口的管理者，通常附加在主窗口的中央
        self.dock_manager = ads.CDockManager(self)
        # 1. 禁用双击标题栏浮动
        self.main_layout.addWidget(self.dock_manager)

        # 2. 创建一些要放入 Dock 的内容部件
        label = QLabel("这是一个标签部件")
        editor = QTextEdit()
        calendar = QCalendarWidget()

        # 3. 将内容部件包装成 CDockWidget
        # 参数分别是：唯一标识符、父级、标题、内容部件
        dock_1 = ads.CDockWidget("LabelDock")
        dock_1.setWidget(label)
        dock_1.setWindowTitle("信息展示")

        dock_2 = ads.CDockWidget("EditorDock")
        dock_2.setWidget(editor)
        dock_2.setWindowTitle("代码编辑器")

        dock_3 = ads.CDockWidget("CalendarDock")
        dock_3.setWidget(calendar)
        dock_3.setWindowTitle("日历控件")

        # 禁止关闭、禁止悬浮：只保留可移动（在窗口内拖拽停靠）
        no_close_no_float = ads.CDockWidget.DockWidgetMovable
        my_features = (
            ads.CDockWidget.DockWidgetMovable | ads.CDockWidget.DockWidgetFocusable
        )
        for dock in (dock_1, dock_2, dock_3):
            dock.setFeatures(my_features)

        # 4. 将 Dock 部件添加到管理器中
        # 添加第一个部件
        self.dock_manager.addDockWidget(ads.LeftDockWidgetArea, dock_1)

        # 在第一个部件的下方添加第二个部件
        self.dock_manager.addDockWidget(
            ads.BottomDockWidgetArea, dock_2, dock_1.dockAreaWidget()
        )

        # 在右侧添加第三个部件
        self.dock_manager.addDockWidget(ads.RightDockWidgetArea, dock_3)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 设置样式（可选，ADS 在默认样式下也工作良好）
    # ads.CDockManager.setStyle(ads.CDockPerspectiveStyle)

    window = MyMainWindow()
    window.show()
    sys.exit(app.exec())
