#个人女优详细的面板
from PySide6.QtWidgets import QHBoxLayout, QWidget, QLabel, QVBoxLayout
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, Slot, QThreadPool
from core.database.query import get_record_count_in_days, get_top_actress_by_masturbation_count
import logging
from ui.widgets import ActressCard
from ui.basic.Effect import ShadowEffectMixin
from ui.base import LazyWidget
import numpy as np
from controller.GlobalSignalBus import global_signals
from core.crawler.Worker import Worker
from ui.statistics.force_view_multi_processing import ForceViewControlWidget


from core.graph.graph import generate_graph,generate_random_graph,generate_similar_graph
from core.graph.graph_manager import GraphManager


class ForceDirectPage(LazyWidget):
    def __init__(self):
        super().__init__()


    def _lazy_load(self):
        logging.info("----------力导向图界面----------")

        mainlayout = QVBoxLayout()
        self.setLayout(mainlayout)
        mainlayout.setContentsMargins(0, 0, 0, 0)

        placeholder = QLabel("正在生成力导向图...")
        placeholder.setAlignment(Qt.AlignCenter)# type: ignore[arg-type]
        mainlayout.addWidget(placeholder)


        view = ForceViewControlWidget()
        view.view.session.reload()

        mainlayout.removeWidget(placeholder)
        placeholder.deleteLater()
        mainlayout.addWidget(view)


