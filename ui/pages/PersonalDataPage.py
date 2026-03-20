#个人隐私的面板

from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import QHBoxLayout, QWidget,QVBoxLayout
from PySide6.QtGui import QPainter, QPainterPath, QBrush, QColor, QPen
from PySide6.QtCore import Qt,Slot, QThreadPool, QRunnable, Signal, QObject
from core.database.query import get_record_count_in_days,get_top_actress_by_masturbation_count
import logging
from ui.widgets import ActressCard
from ui.widgets.StatsOverviewCards import StatsOverviewCards
from ui.basic.Effect import ShadowEffectMixin
from darkeye_ui import LazyWidget
from ui.statistics import SwitchHeapMap
from controller.GlobalSignalBus import global_signals
from darkeye_ui.components.transparent_widget import TransparentWidget
from darkeye_ui.components.label import Label
from darkeye_ui.design.tokens import ThemeTokens, LIGHT_TOKENS

if TYPE_CHECKING:
    from darkeye_ui.design.theme_manager import ThemeManager

class DatabaseQueryWorker(QRunnable):
    """数据库查询工作线程"""
    def __init__(self, query_func, *args, **kwargs):
        super().__init__()
        self.query_func = query_func
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.query_func(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            logging.error(f"数据库查询失败: {e}")
            self.signals.finished.emit(None)


class WorkerSignals(QObject):
    """工作线程信号"""
    finished = Signal(object)

class PersonalDataPage(LazyWidget):
    def __init__(self):
        super().__init__()


    def _lazy_load(self):
        logging.info("----------个人数据界面----------")
        mainlayout = QVBoxLayout(self)
        mainlayout.setContentsMargins(0, 10, 0, 0)

        # 顶部统计卡片（数据库概览）
        mainlayout.addWidget(StatsOverviewCards())

        self.hlayout=QHBoxLayout()
        
        most_like_actress30=MostLikeActress(30)
        most_like_actress180=MostLikeActress(180)
        most_like_actress365=MostLikeActress(365)

        work_sale_cycle=WorkSaleCycle()
        self.hlayout.addWidget(most_like_actress30)
        self.hlayout.addWidget(most_like_actress180)
        self.hlayout.addWidget(most_like_actress365)

        self.hlayout.addWidget(work_sale_cycle)

        mainlayout.addLayout(self.hlayout)

        calendar_heatmap=SwitchHeapMap()
        mainlayout.addWidget(calendar_heatmap,alignment=Qt.AlignCenter)

        
        #全局信号总线触发
        global_signals.masterbation_changed.connect(work_sale_cycle.update_day)
        global_signals.like_work_changed.connect(work_sale_cycle.update_day)
        global_signals.masterbation_changed.connect(most_like_actress30.update_actress)
        global_signals.masterbation_changed.connect(most_like_actress180.update_actress)
        global_signals.masterbation_changed.connect(most_like_actress365.update_actress)
        from datetime import datetime
        def refresh_heatmap():
            calendar_heatmap.update(datetime.now().year, force_refresh=True)
        global_signals.masterbation_changed.connect(refresh_heatmap)
        global_signals.lovemaking_changed.connect(refresh_heatmap)
        global_signals.sexarousal_changed.connect(refresh_heatmap)


class OctagonCard(QWidget, ShadowEffectMixin):
    """通用八边形卡片外框，子类只负责填充内容。背景与描边由设计令牌驱动，随主题切换。"""

    def __init__(
        self,
        object_name: str,
        margins: tuple[int, int, int, int] = (0, 0, 0, 0),
        theme_manager: Optional["ThemeManager"] = None,
    ) -> None:
        super().__init__()
        self.setFixedSize(170, 250)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName(object_name)
        self.set_shadow()
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

        if theme_manager is None:
            try:
                from app_context import get_theme_manager
                theme_manager = get_theme_manager()
            except Exception:
                pass
        self._theme_manager = theme_manager
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._on_theme_changed)

        # 提供给子类使用的主布局
        self.mainlayout = QVBoxLayout(self)
        self.mainlayout.setContentsMargins(*margins)

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _on_theme_changed(self) -> None:
        self.update()

    def paintEvent(self, event):  # type: ignore[override]
        """绘制八边形背景，替代圆角矩形。背景与描边由设计令牌驱动。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # 留一点边距，避免贴边，同时给阴影留空间
        r = self.rect().adjusted(0, 0, -0, -0)
        w, h = r.width(), r.height()
        x, y = r.x(), r.y()
        chamfer = 20

        path = QPainterPath()
        path.moveTo(x + chamfer, y)
        path.lineTo(x + w - chamfer, y)
        path.lineTo(x + w, y + chamfer)
        path.lineTo(x + w, y + h - chamfer)
        path.lineTo(x + w - chamfer, y + h)
        path.lineTo(x + chamfer, y + h)
        path.lineTo(x, y + h - chamfer)
        path.lineTo(x, y + chamfer)
        path.closeSubpath()

        # 背景与描边由设计令牌驱动，随主题切换
        t = self._tokens()
        painter.setPen(QPen(QColor(t.color_border), 1))
        painter.setBrush(QBrush(QColor(t.color_bg)))
        painter.drawPath(path)
        painter.end()


class WorkSaleCycle(OctagonCard):
    '''去化周期显示'''
    def __init__(self):
        super().__init__("WorkSaleCycle", margins=(0, 0, 0, 0))
        self.thread_pool = QThreadPool.globalInstance()

        mainlayout = self.mainlayout
        label1=Label(f"收藏作品中未观看去化周期")
        label1.setAlignment(Qt.AlignCenter)

        self.label2=Label("加载中...")
        self.label2.setAlignment(Qt.AlignCenter)
        self.label2.setStyleSheet("font-size: 30pt; color: #999999;")

        mainlayout.addWidget(label1)
        mainlayout.addWidget(self.label2)

        # 异步加载初始数据
        self._load_data_async()

    def _load_data_async(self):
        """异步加载去化周期数据"""
        worker = DatabaseQueryWorker(self._calculate_sales_cycle)
        worker.signals.finished.connect(self._on_data_loaded)
        self.thread_pool.start(worker)

    def _calculate_sales_cycle(self):
        """#按过去3个月平均的撸管频率去计算去化周期并显示,当去化周期大于14天时就进入选择模式"""
        from core.database.query import get_unmasturbated_work_count
        un_mas_num=get_unmasturbated_work_count()
        count=get_record_count_in_days(90,0)
        if not count==0:
            Sales_cycleun=int(un_mas_num/count*90)
        else:
            Sales_cycleun=114514
        return Sales_cycleun

    def _on_data_loaded(self, day):
        """数据加载完成回调"""
        self.label2.setText(str(day)+"天")
        if day>30:
            self.label2.setStyleSheet("font-size: 30pt; color: #FF0000;")  # 纯红
        else:
            self.label2.setStyleSheet("font-size: 30pt; color: #000000;")  # 纯黑

    def work_not_watch(self):
        '''#按过去3个月平均的撸管频率去计算去化周期并显示,当去化周期大于14天时就进入选择模式'''
        return self._calculate_sales_cycle()

    @Slot()
    def update_day(self):
        logging.debug("更新去化周期")
        # 先显示加载状态
        self.label2.setText("加载中...")
        self.label2.setStyleSheet("font-size: 30pt; color: #999999;")
        # 异步加载新数据
        self._load_data_async()


class MostLikeActress(OctagonCard):
    '''最喜欢的女优卡片'''
    def __init__(self,beforeday):
        super().__init__("mostLikeActress", margins=(10,0,10,10))
        self._bday=beforeday
        self.thread_pool = QThreadPool.globalInstance()
        self.current_worker = None

        label1=Label(f"过去{beforeday}天最喜欢的女优")

        # 先显示占位UI
        self.placeholder_widget = QWidget()
        placeholder_layout = QVBoxLayout(self.placeholder_widget)
        self.placeholder_label = Label("加载中...")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("font-size: 14px; color: #999999;")
        placeholder_layout.addWidget(self.placeholder_label)
        self.placeholder_widget.setLayout(placeholder_layout)

        # 存储最终的女优卡片容器
        self.actress_card_container = TransparentWidget()
        self.actress_card_container_layout = QVBoxLayout(self.actress_card_container)
        self.actress_card_container_layout.setContentsMargins(0, 0, 0, 0)
        self.actress_card_container.setLayout(self.actress_card_container_layout)

        # 初始显示占位符
        self.actress_card_container_layout.addWidget(self.placeholder_widget)
        self.actress_card = None

        #总装
        mainlayout=self.mainlayout
        mainlayout.addWidget(label1,alignment=Qt.AlignCenter)
        mainlayout.addWidget(self.actress_card_container)

        # 异步加载数据
        self._load_actress_async()

    def _load_actress_async(self):
        """异步加载女优数据"""
        worker = DatabaseQueryWorker(get_top_actress_by_masturbation_count, self._bday)
        worker.signals.finished.connect(self._on_actress_loaded)
        self.current_worker = worker
        self.thread_pool.start(worker)

    def _on_actress_loaded(self, actress):
        """女优数据加载完成回调"""
        if self.placeholder_widget:
            self.placeholder_widget.setParent(None)
            self.placeholder_widget = None

        if actress:
            self.actress_card = ActressCard(actress['actress_name'], actress['image_urlA'], actress['actress_id'])
        else:
            self.actress_card = ActressCard()

        self.actress_card_container_layout.addWidget(self.actress_card)


    @Slot()
    def update_actress(self):
        '''初始化或者更新'''
        # 清除旧的女优卡片
        if self.actress_card:
            self.actress_card.setParent(None)
            self.actress_card = None

        # 显示加载占位符
        self.placeholder_widget = QWidget()
        placeholder_layout = QVBoxLayout(self.placeholder_widget)
        self.placeholder_label = Label("加载中...")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("font-size: 14px; color: #999999;")
        placeholder_layout.addWidget(self.placeholder_label)
        self.placeholder_widget.setLayout(placeholder_layout)
        self.actress_card_container_layout.addWidget(self.placeholder_widget)

        # 重新异步加载
        self._load_actress_async()