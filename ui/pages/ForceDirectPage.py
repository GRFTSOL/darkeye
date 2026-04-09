from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtCore import Qt
import logging
from darkeye_ui import LazyWidget
from darkeye_ui.components.label import Label


class ForceDirectPage(LazyWidget):
    def __init__(self):
        super().__init__()

    def _lazy_load(self):
        logging.info("----------力导向图界面----------")

        from core.graph.force_directed_view_widget import ForceDirectedViewWidget

        mainlayout = QVBoxLayout()
        self.setLayout(mainlayout)
        mainlayout.setContentsMargins(0, 0, 0, 0)

        placeholder = Label("正在生成力导向图...")
        placeholder.setAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
        mainlayout.addWidget(placeholder)

        view = ForceDirectedViewWidget()
        view.set_page_graph_filter_toggle_visible(True)

        mainlayout.removeWidget(placeholder)
        placeholder.deleteLater()
        mainlayout.addWidget(view)
        view.session.new_load()
