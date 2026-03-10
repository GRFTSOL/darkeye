
from PySide6.QtWidgets import QVBoxLayout
from darkeye_ui import LazyWidget
from darkeye_ui.components.token_tab_widget import TokenTabWidget

class StatisticsPage(LazyWidget):
    def __init__(self):
        super().__init__()

    def _lazy_load(self):
        # 懒加载导入
        from .PlotTabPage import PlotTabPage
        from .PersonalDataPage import PersonalDataPage
        
        mainlayout = QVBoxLayout(self)
        mainlayout.setContentsMargins(0, 0, 0, 0)
        
        self.tab_widget=TokenTabWidget()
        plot_tabpage=PlotTabPage()
        p_datapage=PersonalDataPage()

        self.tab_widget.addTab(p_datapage,"信息面版")
        self.tab_widget.addTab(plot_tabpage,"统计")


        mainlayout.addWidget(self.tab_widget)


