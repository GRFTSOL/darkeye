
from PySide6.QtWidgets import QWidget,QVBoxLayout,QTabWidget
from .PlotTabPage import PlotTabPage
from .PersonalDataPage import PersonalDataPage


class StatisticsPage(QWidget):
    def __init__(self):
        super().__init__()
        '''
        from ui.statistics.force_view_multi_processing import manybody_block_kernel
        import numpy as np
        pos = np.zeros((100, 2), np.float32)
        mass = np.ones(100, np.float32)
        vel = np.zeros_like(pos)
        manybody_block_kernel(pos, mass, vel, 1.0, 1.0, 1e4, 32)
        
        '''
        mainlayout = QVBoxLayout(self)
        mainlayout.setContentsMargins(0, 0, 0, 0)
        
        self.tab_widget=QTabWidget()
        plot_tabpage=PlotTabPage()
        p_datapage=PersonalDataPage()

        self.tab_widget.addTab(p_datapage,"信息面版")
        self.tab_widget.addTab(plot_tabpage,"统计")


        mainlayout.addWidget(self.tab_widget)


