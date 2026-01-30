
from PySide6.QtWidgets import QPushButton, QHBoxLayout, QWidget, QLabel,QVBoxLayout,QLineEdit,QComboBox
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt,Signal,Slot,QTimer
import sqlite3,logging
from typing import Callable

from config import DATABASE
from core.database.query import get_actressname,get_cup_type
from core.database.db_utils import attach_private_db,detach_private_db
from ui.widgets import ActressCard,CompleterLineEdit
from ui.basic import LazyScrollArea,IconPushButton,RotateButton,ShakeButton
from ui.base import LazyWidget
from utils.utils import timeit


class FlashComboBox(QComboBox):
    '''带刷新的comboBox,输入一个函数'''
    def __init__(self,func):
        super().__init__()
    def __init__(self, loader_func: Callable[[], list] = None, parent=None):
        """
        初始化
        :param loader_func: 返回项目列表的函数
        :param parent: 父组件
        """
        super().__init__(parent)
        self.items = []  # 存储当前项目列表
        self.loader_func = loader_func  # 存储加载函数
        self.load_items()  # 初始加载项目

    def set_loader_func(self, loader_func: Callable[[], list]):
        """设置新的加载函数"""
        self.loader_func = loader_func
        self.reload_items()
    
    def load_items(self):
        """从数据源加载项目"""
        if self.loader_func is not None:
            self.items = self.loader_func()  # 使用传入的函数加载
            self.setup()
    
    def setup(self):
        """设置/重新设置"""
        self.clear()
        self.addItems(self.items)
    
    def reload_items(self):
        """重新加载项目并刷新自动完成"""
        self.load_items()

    

    



class ActressPage(LazyWidget):
    def __init__(self):
        super().__init__()
        
    def _lazy_load(self):
        logging.info("----------加载女优界面----------")
        self.last_scroll_value = 0  # 上一次滚动位置
        self.actress_name=None

        self.order="添加逆序"#排序默认值
        self.scope="公共库范围"
        self.cup=None

        #self.spacer_widget = QWidget()
        #self.spacer_widget.setFixedHeight(70)

        self.filter_widget = QWidget()
        self.filter_widget.setFixedHeight(26)
        self.filter_layout = QHBoxLayout(self.filter_widget)  # 直接传入 widget
        self.filter_layout.setContentsMargins(10,0,10,0)

        self.actressname_input = CompleterLineEdit(get_actressname)

        self.cup_combo=FlashComboBox(lambda: [""] + get_cup_type())

        

        self.info=QLabel()#用来显示信息
        self.info.setFixedWidth(100)
        
        #self.filter_btn =IconPushButton("search.svg")
        self.btn_eraser=ShakeButton("eraser.svg")
        self.btn_reload=RotateButton("refresh-cw.svg")
        #排序选择器
        self.order_combo = QComboBox()
        self.order_combo.addItems(["年龄顺序", "年龄逆序","出道顺序","出道逆序","添加顺序","添加逆序","身高顺序","身高逆序","罩杯顺序","罩杯逆序","腰臀比顺序","腰臀比逆序"])
        self.order_combo.setCurrentText(self.order)
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["公共库范围","收藏库范围"])
        self.scope_combo.setCurrentText(self.scope)

        self.filter_layout.addWidget(QLabel("女优"))
        self.filter_layout.addWidget(self.actressname_input)
        self.filter_layout.addWidget(QLabel("罩杯"))
        self.filter_layout.addWidget(self.cup_combo)
        #self.filter_layout.addWidget(self.filter_btn)
        self.filter_layout.addWidget(self.btn_reload)
        self.filter_layout.addWidget(self.btn_eraser)
        self.filter_layout.addWidget(self.info)
        self.filter_layout.addWidget(self.scope_combo)
        self.filter_layout.addWidget(self.order_combo)

        #加载女优的区域
        self.lazy_area = LazyScrollArea(column_width=150)

        #总体布局
        mainlayout = QVBoxLayout(self)
        mainlayout.setContentsMargins(0, 0, 0, 0)
        #mainlayout.addWidget(self.spacer_widget)
        mainlayout.addWidget(self.filter_widget)
        mainlayout.addWidget(self.lazy_area)
        
        self.singal_connect()

        self.lazy_area.set_loader(self.load_page)#这个最费时
        self.info.setText("过滤总数:"+str(self.load_data(0,0,True)[0][0]))

        self.filter_timer = QTimer(self)#防抖动
        self.filter_timer.setSingleShot(True)
        self.filter_timer.timeout.connect(self.apply_filter_real)

    def singal_connect(self):
        self.btn_reload.clicked.connect(self.refresh)
        #self.filter_btn.clicked.connect(self.apply_filter)
        self.order_combo.activated.connect(self.apply_filter)
        self.scope_combo.activated.connect(self.apply_filter)
        #self.actressname_input.returnPressed.connect(self.apply_filter)
        self.cup_combo.activated.connect(self.apply_filter)
        self.actressname_input.textChanged.connect(self.apply_filter)
        #self.lazy_area.verticalScrollBar().valueChanged.connect(self.handle_scroll)

        from controller.GlobalSignalBus import global_signals
        global_signals.actress_data_changed.connect(self.actressname_input.reload_items)
        global_signals.actress_data_changed.connect(self.cup_combo.reload_items)
        self.btn_eraser.clicked.connect(self._clear_all_search)

    @Slot()
    def _clear_all_search(self):
        self.actressname_input.setText("")
        self.cup_combo.setCurrentIndex(0)
        self.apply_filter()

    @Slot()
    def apply_filter(self):
        """防抖：用户操作后延迟执行真正的查询"""
        self.filter_timer.start(50)  # 停 50ms 才真正执行

    @Slot()
    def apply_filter_real(self):
        self.actress_name = self.actressname_input.text().strip()
        self.order=self.order_combo.currentText()
        self.scope=self.scope_combo.currentText()
        self.cup=self.cup_combo.currentText() 
        self.lazy_area.reset()
        self.update_info()


    def update_info(self):
        '''更新查询到几条数据'''
        if self.load_data(0,0,True) is None:
            self.info.setText("没有查询到数据")
        else:
            self.info.setText("过滤总数:"+str(self.load_data(0,0,True)[0][0]))


    def load_data(self, page_index: int, page_size: int,count:bool=False)->tuple:
        '''返回查询的数据'''
        offset = page_index * page_size
        # 动态拼接 SQL,要怎么筛逻辑都在这里改
        params=[]
        #基础查询
        if count:#查询总数
            query=f"""
SELECT 
    count(*) AS count
FROM actress
        """
        else:
            query=f"""
SELECT 
    (SELECT cn FROM actress_name WHERE actress_id = actress.actress_id AND(name_type=1))AS name,
    image_urlA,
    actress.actress_id
FROM actress
        """

        # 拼withsql
        if self.actress_name:
            withsql=f'''
WITH filtered_actresses AS (--先筛选名字中的actress_id,单独的
SELECT 
    DISTINCT actress_id
FROM 
    actress_name
WHERE cn LIKE ? OR jp LIKE ? OR en LIKE ? OR kana LIKE ?
)
            '''
            query=withsql+query
            params.extend([f"%{self.actress_name}%", f"%{self.actress_name}%", f"%{self.actress_name}%", f"%{self.actress_name}%"])

        # 拼join
        if self.scope=="收藏库范围":
            join="JOIN priv.favorite_actress fav ON fav.actress_id=actress.actress_id\n"
            query+=join

        if self.actress_name:
            join="JOIN filtered_actresses f ON actress.actress_id = f.actress_id \n"
            query+=join
            
        # 拼where
        where="WHERE 1=1\n"#占位
        match self.order:
            case "年龄顺序":
                where="WHERE actress.birthday !=''AND actress.birthday is NOT NULL\n"
            case "年龄逆序":
                where="WHERE actress.birthday !=''AND actress.birthday is NOT NULL\n"
            case "出道顺序":
                where="WHERE actress.debut_date !=''AND actress.debut_date is NOT NULL\n"
            case "出道逆序":
                where="WHERE actress.debut_date !=''AND actress.debut_date is NOT NULL\n"
            case "腰臀比顺序":
                where="WHERE actress.waist IS NOT NULL AND actress.hip IS NOT NULL AND actress.hip !=0\n"
            case "腰臀比逆序":
                where="WHERE actress.waist IS NOT NULL AND actress.hip IS NOT NULL AND actress.hip !=0\n"

        query+=where#比拼

        if self.cup:
            where=f"AND actress.cup=?\n"
            params.extend(self.cup)
            query+=where

        # 拼order
        match self.order:
            case "年龄顺序":
                order="ORDER BY actress.birthday DESC\n"
            case "年龄逆序":
                order="ORDER BY actress.birthday\n"
            case "添加顺序":
                order="ORDER BY actress.create_time \n"
            case "添加逆序":
                order="ORDER BY actress.create_time DESC\n"
            case "身高顺序":
                order="ORDER BY actress.height \n"
            case "身高逆序":
                order="ORDER BY actress.height DESC\n"
            case "罩杯顺序":
                order="ORDER BY actress.cup \n"
            case "罩杯逆序":
                order="ORDER BY actress.cup DESC\n"
            case "出道顺序":
                order="ORDER BY actress.debut_date \n"
            case "出道逆序":
                order="ORDER BY actress.debut_date DESC\n"
            case "腰臀比顺序":
                order="ORDER BY ROUND(actress.waist * 1.0 / NULLIF(actress.hip, 0), 2) \n"
            case "腰臀比逆序":
                order="ORDER BY ROUND(actress.waist * 1.0 / NULLIF(actress.hip, 0), 2) DESC\n"

        if not count:
            query +=f"{order} LIMIT ? OFFSET ?"#最后拼这个
            params.extend([page_size, offset])

        #logging.debug(f"ActressPage Execute SQL\n{query}")
        with sqlite3.connect(f"file:{DATABASE}?mode=ro",uri=True) as conn:
            cursor = conn.cursor()
            if self.scope=="收藏库范围": attach_private_db(cursor)
            cursor.execute(query,params) #这里面不能orderby random 会重复
            results=cursor.fetchall()
            if self.scope=="收藏库范围": detach_private_db(cursor)
        return results

    def load_page(self, page_index: int, page_size: int) -> list[ActressCard]:
        """返回一个页面的 ActressCard 列表"""
        result:list[ActressCard] = []
        data=self.load_data(page_index,page_size)
        if not data:
            return None
        for name, image_urlA,actress_id in data:
            card = ActressCard(name,image_urlA,actress_id)

            
            result.append(card)
        return result
    
    def refresh(self):
        '''刷新'''
        self.lazy_area.reset()
        self.update_info()

    @Slot(int)
    def handle_scroll(self, value):
        direction = value - self.last_scroll_value

        if direction > 5:
            # 向下滚动，隐藏顶部
            if self.filter_widget.isVisible():
                self.filter_widget.hide()
                #self.spacer_widget.hide()

        elif direction < -5:
            # 向上滚动，显示顶部
            if not self.filter_widget.isVisible():
                self.filter_widget.show()
                #self.spacer_widget.show()

        self.last_scroll_value = value


