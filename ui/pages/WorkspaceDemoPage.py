"""工作区 Demo 页面：嵌入 WorkspaceDemoWidget，作为路由 workspace_demo 的目标。"""

from PySide6.QtWidgets import QWidget, QVBoxLayout

from ui.demo.workspace_widget import WorkspaceDemoWidget


class WorkspaceDemoPage(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(WorkspaceDemoWidget())
