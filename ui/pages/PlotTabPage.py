
from PySide6.QtWidgets import QHBoxLayout, QWidget,QSizePolicy,QVBoxLayout,QSplitter
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from PySide6.QtCore import Slot
from ui.statistics.MplCanvas import MplCanvas
import logging
from darkeye_ui import LazyWidget
from darkeye_ui.components.button import Button
from darkeye_ui.components.token_radio_button import TokenRadioButton
from darkeye_ui.components.token_group_box import TokenGroupBox

class PlotTabPage(LazyWidget):
    def __init__(self):
        super().__init__()


    def _lazy_load(self):
        logging.info("----------数据分析图窗口----------")

        self.canvas = MplCanvas(self)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # 让 canvas 尽量填充

        self.btn_ageDistribution = Button("作品拍摄时女优年龄分布直方图")
        self.btn_workReleaseYearDistribution = Button("作品发行年份分布直方图")
        self.btn_actressDebutYearDistribution = Button("女优出道年份分布直方图")
        self.btn_heightDistribution = Button("女优身高分布直方图")
        self.btn_BWH_Distribution = Button("女优身材3D分布图")
        self.btn_cupDistribution = Button("女优罩杯分布饼图")
        self.btn_directorStat = Button("导演统计柱状图")
        self.btn_makerStat = Button("制作商统计柱状图")
        self.btn_mostLikeActress= Button("最喜欢的女优柱状图")
        self.btn_ActressBodyHWratio= Button("女优身材腰臀比气泡图")

        self.btn_actress_debutage_distribution= Button("女优出道年龄分布直方图")
        self.btn_TagWordClould=Button("Tag词云生成")

        btn_YearReport=Button("撸管年回忆录")
        btn_YearReport.setEnabled(False)
        self.btn_addTimeDistribution=Button("按添加时间统计作品数")
        
        radio_group = TokenGroupBox("选择统计范围")
        self.rbtn_public=TokenRadioButton("公共数据库")
        self.rbtn_collect = TokenRadioButton("收藏库内")
        self.rbtn_singlwork = TokenRadioButton("撸过")
        self.rbtn_plane = TokenRadioButton("撸过加权")
        self.rbtn_singlwork.setChecked(True)

        group_layout=QVBoxLayout(radio_group)
        group_layout.addWidget(self.rbtn_public)
        group_layout.addWidget(self.rbtn_collect)
        group_layout.addWidget(self.rbtn_singlwork)
        group_layout.addWidget(self.rbtn_plane)
        #radio_group.setFixedHeight(125)

        # 创建水平分隔器
        left_widget=QWidget()
        right_widget=QWidget()

        splitter = QSplitter()
        splitter.setStretchFactor(0, 1)  # 左侧拉伸因子
        splitter.setStretchFactor(1, 9)  # 右侧拉伸因子
        splitter.setStyleSheet("""
                                QSplitter::handle {
                                    background: #cccccc;
                                    width: 1px;
                                    height: 1px;
                                    border: none;
                                    margin: 0;
                                }
                                QSplitter::handle:hover {
                                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                                            stop:0 #888, stop:1 #666);
                                }
                            """)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        # 设置分隔器可以响应鼠标拖动
        splitter.setChildrenCollapsible(False)  # 防止子部件被完全折叠

        toolbar_layout = QVBoxLayout(right_widget)
        canvas_layout=QVBoxLayout(left_widget)#上下分，上面导航toolbar下面画布
        
        canvas_layout.addWidget(NavigationToolbar(self.canvas, self))
        canvas_layout.addWidget(self.canvas)

        statistics_group=TokenGroupBox("多样化统计")
        statistics_group_layout=QVBoxLayout(statistics_group)
        statistics_group_layout.setContentsMargins(5,0,5,0)
        statistics_group_layout.addWidget(radio_group)
        statistics_group_layout.addWidget(self.btn_ageDistribution)
        statistics_group_layout.addWidget(self.btn_workReleaseYearDistribution)
        statistics_group_layout.addWidget(self.btn_actressDebutYearDistribution)
        statistics_group_layout.addWidget(self.btn_heightDistribution)
        statistics_group_layout.addWidget(self.btn_ActressBodyHWratio)
        statistics_group_layout.addWidget(self.btn_cupDistribution)
        statistics_group_layout.addWidget(self.btn_directorStat)
        statistics_group_layout.addWidget(self.btn_makerStat)
        statistics_group_layout.addWidget(self.btn_TagWordClould)
        
        toolbar_layout.addWidget(statistics_group)

        toolbar_layout.addWidget(self.btn_BWH_Distribution)
        toolbar_layout.addWidget(self.btn_mostLikeActress)
        toolbar_layout.addWidget(self.btn_addTimeDistribution)
        toolbar_layout.addWidget(self.btn_actress_debutage_distribution)

        toolbar_layout.addWidget(btn_YearReport)


        #总装
        outlayout=QVBoxLayout(self)
        outlayout.addWidget(splitter)

        self.signal_connect()

    def signal_connect(self):
        '''信号连接'''
        self.btn_ageDistribution.clicked.connect(self.age_distribution)
        self.btn_heightDistribution.clicked.connect(self.height_distribution)
        self.btn_cupDistribution.clicked.connect(self.cup_distribution)
        self.btn_BWH_Distribution.clicked.connect(self.canvas.Draw3DsizeDis)
        self.btn_directorStat.clicked.connect(self.director_bar)
        self.btn_ActressBodyHWratio.clicked.connect(self.actress_body_wh_ratio)
        self.btn_mostLikeActress.clicked.connect(self.canvas.draw_mostlikeActress)
        self.btn_makerStat.clicked.connect(self.studio_bar)
        self.btn_addTimeDistribution.clicked.connect(self.canvas.draw_addTimeDistribution)
        self.btn_TagWordClould.clicked.connect(self.tagWordCloud)
        self.btn_workReleaseYearDistribution.clicked.connect(self.workReleaseYear_distribution)
        self.btn_actressDebutYearDistribution.clicked.connect(self.ActressDebutYearDistribution)
        self.btn_actress_debutage_distribution.clicked.connect(self.canvas.plotActressDebutAge)

    @Slot()
    def ActressDebutYearDistribution(self):
        '''女优出道年份分布直方图'''
        if self.rbtn_collect.isChecked():
            self.canvas.plotActressDebutYear(0)
        elif self.rbtn_singlwork.isChecked():
            self.canvas.plotActressDebutYear(1)
        elif self.rbtn_plane.isChecked():
            self.canvas.plotActressDebutYear(2)
        elif self.rbtn_public.isChecked():
            self.canvas.plotActressDebutYear(-1)

    @Slot()
    def age_distribution(self):
        #根据选择的状态绘制不同的图
        if self.rbtn_collect.isChecked():
            self.canvas.plotWorkActressAge(0)
        elif self.rbtn_singlwork.isChecked():
            self.canvas.plotWorkActressAge(1)
        elif self.rbtn_plane.isChecked():
            self.canvas.plotWorkActressAge(2)
        elif self.rbtn_public.isChecked():
            self.canvas.plotWorkActressAge(-1)

    @Slot()
    def workReleaseYear_distribution(self):
        '''作品发行年份分布直方图'''
        if self.rbtn_collect.isChecked():
            self.canvas.plotWorkReleaseYear(0)
        elif self.rbtn_singlwork.isChecked():
            self.canvas.plotWorkReleaseYear(1)
        elif self.rbtn_plane.isChecked():
            self.canvas.plotWorkReleaseYear(2)
        elif self.rbtn_public.isChecked():
            self.canvas.plotWorkReleaseYear(-1)

    @Slot()
    def height_distribution(self):
        #根据选择的状态绘制不同的图
        if self.rbtn_collect.isChecked():
            self.canvas.draw_height_distribution(0)
        elif self.rbtn_singlwork.isChecked():
            self.canvas.draw_height_distribution(1)
        elif self.rbtn_plane.isChecked():
            self.canvas.draw_height_distribution(2)
        elif self.rbtn_public.isChecked():
            self.canvas.draw_height_distribution(-1)

    @Slot()
    def cup_distribution(self):
        #根据选择的状态绘制不同的图
        if self.rbtn_collect.isChecked():
            self.canvas.draw_cup_distribution_pie(0)
        elif self.rbtn_singlwork.isChecked():
            self.canvas.draw_cup_distribution_pie(1)
        elif self.rbtn_plane.isChecked():
            self.canvas.draw_cup_distribution_pie(2)
        elif self.rbtn_public.isChecked():
            self.canvas.draw_cup_distribution_pie(-1)

    @Slot()
    def actress_body_wh_ratio(self):
        #女优身材臀腰比
        if self.rbtn_collect.isChecked():
            self.canvas.draw_actressBodyWH_ratio(0)
        elif self.rbtn_singlwork.isChecked():
            self.canvas.draw_actressBodyWH_ratio(1)
        elif self.rbtn_plane.isChecked():
            self.canvas.draw_actressBodyWH_ratio(2)
        elif self.rbtn_public.isChecked():
            self.canvas.draw_actressBodyWH_ratio(-1)

    @Slot()
    def director_bar(self):
        if self.rbtn_collect.isChecked():
            self.canvas.draw_directorBar(0)
        elif self.rbtn_singlwork.isChecked():
            self.canvas.draw_directorBar(1)
        elif self.rbtn_plane.isChecked():
            self.canvas.draw_directorBar(2)
        elif self.rbtn_public.isChecked():
            self.canvas.draw_directorBar(-1)

    @Slot()
    def studio_bar(self):
        if self.rbtn_collect.isChecked():
            self.canvas.draw_studioBar(0)
        elif self.rbtn_singlwork.isChecked():
            self.canvas.draw_studioBar(1)
        elif self.rbtn_plane.isChecked():
            self.canvas.draw_studioBar(2)
        elif self.rbtn_public.isChecked():
            self.canvas.draw_studioBar(-1)

    def tagWordCloud(self):
        if self.rbtn_collect.isChecked():
            self.canvas.draw_workTagCloud(0)
        elif self.rbtn_singlwork.isChecked():
            self.canvas.draw_workTagCloud(1)
        elif self.rbtn_plane.isChecked():
            self.canvas.draw_workTagCloud(2)
        elif self.rbtn_public.isChecked():
            self.canvas.draw_workTagCloud(-1)