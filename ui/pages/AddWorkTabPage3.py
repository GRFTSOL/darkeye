from PySide6.QtWidgets import QPushButton, QHBoxLayout, QLabel,QVBoxLayout,QLineEdit,QTextEdit,QSizePolicy,QPlainTextEdit,QScrollArea, QWidget,QSplitter
from PySide6.QtCore import Qt,QObject,Signal,Property,SignalInstance,Slot,QThreadPool
from PySide6.QtGui import QIntValidator

from ui.widgets.CrawlerToolBox import CrawlerToolBox
import logging,json,asyncio
from pathlib import Path
from enum import Enum
from datetime import datetime

from config import settings,WORKCOVER_PATH,TEMP_PATH
from ui.widgets import ActressSelector,CompleterLineEdit,ActorSelector,CoverDropWidget,TagSelector4
from core.database.query import getUniqueDirector,get_work_tags,get_workinfo_by_workid,get_actressid_by_workid,get_actorid_by_workid,get_unique_short_story,exist_actor,get_workid_by_serialnumber,exist_actress
from core.database.insert import InsertNewWorkByHand,InsertNewActor,InsertNewActress
from core.database.update import update_work_byhand
from utils.utils import mse,load_ini_ids,covert_fanza,translate_text
from ui.basic import IconPushButton
from ui.base import LazyWidget
from controller.MessageService import MessageBoxService,IMessageService

from core.crawler.Worker import Worker
from core.crawler.download import download_image
from ui.navigation.router import Router
from ui.widgets.text.WikiTextEdit import WikiTextEdit
from controller.GlobalSignalBus import global_signals

class ButtonState(Enum):
    NORMAL = 1
    WARNING = 2
    DISABLED = 3

class Model():
    '''纯放数据的model'''
    def __init__(self):
        self._serial_number:str= ""
        self._director:str = ""
        self._release_date:str = ""
        self._vlength:int=0
        self._story:str = ""
        self._cn_title:str = ""
        self._cn_story:str = ""
        self._jp_title:str = ""
        self._jp_story:str = ""

        self._cover:str= ""
        self._actress:list[int] = []
        self._actor:list[int] = []
        self._tag:list[int] = []

    def to_dict(self):
        return {
            "serial_number": self._serial_number,
            "director": self._director,
            "release_date": self._release_date,
            "story": self._story,
            "cn_title": self._cn_title,
            "cn_story": self._cn_story,
            "jp_title": self._jp_title,
            "jp_story": self._jp_story,
            "actress_ids": self._actress,
            "actor_ids": self._actor,
            "tag_ids": self._tag,
            "image_url": self._cover #这个的地址应该是一个相对地址
        }

class ViewModel(QObject):
    '''实现数据与视图的双向绑定，这里是数据，使用Property'''
    serial_number_changed = Signal(str)
    director_changed = Signal(str)
    release_date_changed=Signal(str)
    story_changed=Signal(str)
    vlength_changed=Signal(int)

    cn_title_changed = Signal(str)
    cn_story_changed = Signal(str)
    jp_title_changed = Signal(str)
    jp_story_changed = Signal(str)

    cover_changed=Signal(str)
    actress_changed=Signal('QList<int>')#这里不能使用list(int)要么直接list
    actor_changed=Signal('QList<int>')
    tag_changed=Signal('QList<int>')
    btn_state_changed=Signal(str,ButtonState)

    modify_state_changed = Signal(str, bool) #发出修改什么控件的信号
    workload=Signal(str)#发送给view使用


    def __init__(self, model=None,message_service:IMessageService=None):
        super().__init__()
        self.model:Model = model
        self.msg=message_service
        self._changed_flags = {#检测内容修改的字典,通过这个控制UI的改变
        'story': False,
        'release_date': False,
        'director': False,
        'cn_title': False,
        'cn_story': False,
        'jp_title': False,
        'jp_story': False,
        'actress_ids': False,
        'actor_ids': False,
        'tag_ids': False,
        'image_url': False
        }
        self._btn_state={
            'add_work':ButtonState.DISABLED,
            'load':ButtonState.DISABLED,
            'temp_save':ButtonState.DISABLED,
            'temp_load':ButtonState.NORMAL
        }

    # -------------------- getter / setter --------------------
    def get_serial_number(self)->str: return self.model._serial_number
    def set_serial_number(self, value:str):
        if not value:
            value=""
        if self.model._serial_number != value.strip().upper():#这里全部转成纯大写
            self.model._serial_number = value.strip().upper()
            self.serial_number_changed.emit(value)

            #这里写番号转换的函数
            #print("Model updated:", self.model._serial_number)

    def get_director(self)->str: return self.model._director
    def set_director(self, value:str):
        if not value:
            value=""
        if self.model._director != value.strip():
            self.model._director = value.strip()
            self.director_changed.emit(value)

    def get_release_date(self)->str: return self.model._release_date
    def set_release_date(self, value:str):
        if not value:
            value=""
        if self.model._release_date != value.strip():
            self.model._release_date = value.strip()
            self.release_date_changed.emit(value)
            #print("Model updated:", self.model._release_date)
    
    def get_vlength(self)->int: return self.model._vlength
    def set_vlength(self, value:int):
        if self.model._vlength != value:
            self.model._vlength = value
            self.vlength_changed.emit(value)
            #print("Model updated:", self.model._vlength)



    def get_story(self)->str: return self.model._story
    def set_story(self, value:str):
        if not value:
            value=""
        if self.model._story != value.strip():
            self.model._story = value.strip()
            self.story_changed.emit(value)
            #print("Model Story updated:", self.model._story)

    def get_cn_title(self)->str: return self.model._cn_title
    def set_cn_title(self, value:str):
        if not value:
            value=""
        if self.model._cn_title != value.strip():
            self.model._cn_title = value.strip()
            self.cn_title_changed.emit(value)
            #print("cn_title updated:", self.model._cn_title)

    def get_cn_story(self)->str: return self.model._cn_story
    def set_cn_story(self, value:str):
        if not value:
            value=""
        if self.model._cn_story != value.strip():
            self.model._cn_story = value.strip()
            self.cn_story_changed.emit(value)
            #print("cn_story updated:", self.model._cn_story)

    def get_jp_title(self)->str: return self.model._jp_title
    def set_jp_title(self, value:str):
        if not value:
            value=""
        if self.model._jp_title != value.strip():
            self.model._jp_title = value.strip()
            self.jp_title_changed.emit(value)
            #print("jp_title updated:", self.model._jp_title)

    def get_jp_story(self)->str: return self.model._jp_story
    def set_jp_story(self, value:str):
        if not value:
            value=""
        if self.model._jp_story != value.strip():
            self.model._jp_story = value.strip()
            self.jp_story_changed.emit(value)
            #print("jp_story updated:", self.model._jp_story)

    def get_cover(self)->str: return self.model._cover
    def set_cover(self, value:str):
        if not value:
            value=""
        if self.model._cover != value:
            logging.debug(f"cover原地址为{self.model._cover}")
            self.model._cover = value
            self.cover_changed.emit(value)
            logging.debug(f"cover地址改变为{value}")

    def get_actress(self)->list[int]: return self.model._actress
    def set_actress(self, value:list[int]):
        if self.model._actress != value:#考虑要不要集合操作，不过问题不大，存的时候会有集合操作
            self.model._actress = value
            self.actress_changed.emit(value)
            #print("Model updated:", self.model._actress)

    def get_actor(self)->list[int]: return self.model._actor
    def set_actor(self, value:list[int]):
        if self.model._actor != value:
            self.model._actor = value
            self.actor_changed.emit(value)
            #print("Model updated:", self.model._actor)

    def get_tag(self)->list[int]: return self.model._tag
    def set_tag(self, value:list[int]):
        '''设置tag的id列表'''
        if self.model._tag != value:
            self.model._tag = value
            self.tag_changed.emit(value)
            #print("Model updated _tag:", self.model._tag)

    def set_btn_state(self, key: str, value:bool):
        if key not in self._btn_state:
            raise KeyError(f"Unknown state key: {key}")
        if self._btn_state[key] != value:
            self._btn_state[key] = value
            self.btn_state_changed.emit(key, value)
            #logging.debug("更改按钮状态")

    def _noop_get(self):
        return None
    
    def set_state(self, key: str, value:bool):
        if key not in self._changed_flags:
            raise KeyError(f"Unknown state key: {key}")
        if self._changed_flags[key] != value:
            self._changed_flags[key] = value
            self.modify_state_changed.emit(key, value)

    # -------------------- Property --------------------
    modify_state=Property(str,_noop_get,set_state,notify=modify_state_changed)

    btn_state=Property(str,_noop_get,set_btn_state,notify=btn_state_changed)

    serial_number = Property(str, get_serial_number, set_serial_number, notify=serial_number_changed)
    director = Property(str, get_director, set_director, notify=director_changed)
    release_date = Property(str, get_release_date, set_release_date, notify=release_date_changed)
    story = Property(str, get_story, set_story, notify=story_changed)
    vlength = Property(int, get_vlength, set_vlength, notify=vlength_changed)

    cn_title = Property(str, get_cn_title, set_cn_title, notify=cn_title_changed)
    cn_story = Property(str, get_cn_story, set_cn_story, notify=cn_story_changed)
    jp_title = Property(str, get_jp_title, set_jp_title, notify=jp_title_changed)
    jp_story = Property(str, get_jp_story, set_jp_story, notify=jp_story_changed)

    cover = Property(str, get_cover, set_cover, notify=cover_changed)
    actress = Property(list, get_actress, set_actress, notify=actress_changed)
    actor = Property(list, get_actor, set_actor, notify=actor_changed)
    tag = Property(list, get_tag, set_tag, notify=tag_changed)


#----------------------------------------------------------
#                    提交修改函数
#----------------------------------------------------------
    def submit(self):
        '''手动添加作品记录
        data={
            "serial_number": 
            "director": 
            "release_date": 
            "story": 
            "cn_title": 
            "cn_story": 
            "jp_title": 
            "jp_story": 
            "actress_ids": 
            "actor_ids": 
            "tag_ids": 
            "image_url": 
        }
        '''
        #获得基本数据
        logging.debug("添加记录")
        data=self.model.to_dict()#从viewmodel里取

        image_url=self.get_serial_number().lower().replace('-', '') + 'pl.jpg'#默认的替换规则
        if self.get_cover() is None or self.get_cover()=="":
            data["image_url"]=None
        else:
            logging.debug(f"model内image_url{data["image_url"]}")
            from core.database.insert import rename_save_image
            rename_save_image(data["image_url"],image_url,"cover")
            data["image_url"]=image_url

        if self.work_id is not None:#work已在库中
            self._update_work_and_handle_result(self.work_id,**data)
            self.set_btn_state('add_work',ButtonState.DISABLED)
        else:#work未在库中,插入新的作品
            self._insert_work_and_handle_result(**data)
            
        self._load_from_db()#保存后重新加载一遍

    def _update_work_and_handle_result(self, work_id,**data):
        '''更新作品并弹窗'''
        serial_number=data["serial_number"]
        del data["serial_number"]#这个字段多余，不要了
        if update_work_byhand(work_id, **data):
            self.msg.show_info("更新作品信息成功",f"番号: {serial_number}")
            logging.info("更新作品成功，番号：%s",serial_number)
            from controller.GlobalSignalBus import global_signals
            global_signals.work_data_changed.emit()
            return True
        else:
            self.msg.show_warning("更新作品信息失败",f"未知原因")
            logging.warning("更新%s作品信息失败",serial_number)
            return False

    def _insert_work_and_handle_result(self,**data):
        '''插入作品并弹窗'''
        serial_number=data["serial_number"]
        if InsertNewWorkByHand(**data):
            self.msg.show_info("添加作品成功",f"番号: {serial_number}")
            from controller.GlobalSignalBus import global_signals
            global_signals.work_data_changed.emit()#发送给那些需要重新加载的东西
            logging.info("添加作品成功，番号：%s",serial_number)
            return True
        else:
            self.msg.show_warning("添加作品失败","未知原因")
            logging.warning("添加%s作品信息失败",serial_number)
            return False

#----------------------------------------------------------
#                    加载数据
#----------------------------------------------------------
    def on_work_selected(self):
        """当选择番号时，核心控制
        
        包括更新各种控件的状态，空时全部清空
        """
        #加载进来后要保存原始值
        
        self._cheakable = False#关闭检测

        #检测空的不能添加
        if self.get_serial_number().strip()=="":
            self._clear_all_info()
            self.set_btn_state('add_work',ButtonState.DISABLED)
            self.set_btn_state('temp_save',ButtonState.DISABLED)#关闭临时保存
            self.set_btn_state('load',ButtonState.DISABLED)#闭锁加载按钮
            logging.debug("番号为空")
            return
        
        #非空，但是番号不在库中
        work_id = get_workid_by_serialnumber(self.get_serial_number().strip())
        if work_id is None:
            self.set_btn_state('load',ButtonState.DISABLED)#闭锁加载按钮
            self.set_btn_state('temp_save',ButtonState.NORMAL)#打开临时加载按钮
            self.work_id=None
            #这里应该是清空所有的信息面板
            self._clear_all_info()
            self.set_btn_state('add_work',ButtonState.NORMAL)
            self.set_change_widget_default()
            return
        
        logging.debug("番号在库中")
        #番号在库中
        self.work_id=work_id
        self.set_btn_state('load',ButtonState.WARNING)#打开加载按钮
        self.set_btn_state('temp_save',ButtonState.DISABLED)#闭锁临时加载
        self.set_btn_state('add_work',ButtonState.DISABLED)
        self.set_change_widget_default()

    def _load_from_db(self):
        '''从数据库内加单个作品的数据'''
        logging.debug("加载作品数据----------------------------------------------------------------")
        self.work_id= get_workid_by_serialnumber(self.get_serial_number().strip())
        if self.work_id==None:
            return
        inf=get_workinfo_by_workid(self.work_id)

        #这里加载图，应用ego filter
        self.workload.emit(f"w{self.work_id}")


        def replace_nan_with_empty(d: dict):
            for k, v in d.items():
                if v is None:
                    d[k] = ""
            return d
        replace_nan_with_empty(inf)

        self._cheakable = False #关闭检测

        self.set_release_date(inf['release_date'])
        self.set_director(inf['director'])
        self.set_story(inf['story'])
        self.set_cn_title(inf['cn_title'])#Nano与空值的处理
        self.set_cn_story(inf['cn_story'])
        self.set_jp_title(inf['jp_title'])
        self.set_jp_story(inf['jp_story'])

        actress_ids:list=get_actressid_by_workid(self.work_id)
        self.set_actress(actress_ids)
        logging.debug("加载的女优id为：%s",actress_ids)

        actor_ids:list=get_actorid_by_workid(self.work_id)
        self.set_actor(actor_ids)
        logging.debug("加载的男优id为：%s",actor_ids)

        tag_ids = get_work_tags(self.work_id)
        self.set_tag(tag_ids)
        #logging.debug(f"加载的image_url为:{inf['image_url']}")
        if inf['image_url'] is None or inf['image_url']=="":
            self.set_cover("")
            #logging.debug("封面为空")
        else:
            self.set_cover(str(Path(WORKCOVER_PATH/inf['image_url'])))
        logging.info("加载番号:%s 作品信息",self.get_serial_number())

        #保存原始的内容为修改模式做比较

        inf['actress_ids']=actress_ids
        inf['actor_ids']=actor_ids
        inf['tag_ids']=tag_ids
        self.original_work=inf
        #logging.debug(f"加载的原始内容\n{self.original_work}")

        #重新信号连接，进入修改模式,关键点就是保存原始内容，重置修改旗子，按钮状态默认不能按

        self._cheakable = True
        #logging.debug("开始修改检测")

        self.set_btn_state('add_work',ButtonState.DISABLED)
        #样式还原
        self.set_change_widget_default()

    def _clear_all_info(self):
        '''清空所有的面板里的内容除了input_serial_number'''
        self.set_release_date("")
        self.set_director("")
        self.set_story("")
        self.set_cn_title("")
        self.set_cn_story("")
        self.set_jp_title("")
        self.set_jp_story("")
        self.set_cover("")
        self.set_actress([])
        self.set_actor([])
        self.set_tag([])


#----------------------------------------------------------
#                    检测有无修改并指示
#----------------------------------------------------------

    def setup_change_detection(self):
        """为每个控件设置变更检测"""
        self._cheakable = False #True时开启检测变更
        logging.debug("关闭修改检测")
        # 文本类控件
        self.story_changed.connect(lambda: self.check_change('story', self.get_story()))
        self.release_date_changed.connect(lambda: self.check_change('release_date', self.get_release_date()))
        self.director_changed.connect(lambda: self.check_change('director', self.get_director()))
        
        # 多行文本控件
        self.cn_title_changed.connect(lambda: self.check_change('cn_title', self.get_cn_title()))
        self.cn_story_changed.connect(lambda: self.check_change('cn_story', self.get_cn_story()))
        self.jp_title_changed.connect(lambda: self.check_change('jp_title', self.get_jp_title()))
        self.jp_story_changed.connect(lambda: self.check_change('jp_story', self.get_jp_story()))
        
        # 选择器类控件
        self.actress_changed.connect(lambda: self.check_change('actress_ids', self.get_actress()))
        self.actor_changed.connect(lambda: self.check_change('actor_ids', self.get_actor()))
        self.tag_changed.connect(lambda: self.check_change('tag_ids', self.get_tag()))
        
        # 图片控件
        self.cover_changed.connect(self.check_image_change)

    @Slot()
    def check_change(self, field, new_value):
        '''
        通用字段变更检测方法，用于比较原始值与新值是否发生变化，并更新变更状态标志
        
        Args:
            field (str): 要检测的字段名（对应self.original_work中的键）
            new_value (Any): 待比较的新值
            
        Returns:
            None: 结果会直接更新到self.changed_flags字典中
            
        处理逻辑：
        1. None值特殊处理：直接比较是否相等
        2. 列表类型处理：转换为集合比较元素差异（忽略顺序）
        3. 其他类型：直接值比较
        最终结果会记录在changed_flags字典中并触发按钮状态更新
        '''
        if not self._cheakable:
            return
        original_value = self.original_work[field]
        #logging.debug(f"比较字段{field}")
        # 特殊处理None值比较
        if original_value is None or new_value is None:
            self.set_state(field,(original_value != new_value))
        elif isinstance(original_value, list) and isinstance(new_value, list):#如果是两个列表就是两个集合元素的比较
            self.set_state(field, (set(original_value) != set(new_value)))
        else:
            self.set_state(field,(original_value != new_value))
            #print(original_value)
            #print(new_value)
        #logging.info("检测到内容变更，变更字典为%s",self._changed_flags)
        self.update_button_state()

    @Slot()
    def check_image_change(self):
        """特殊处理图片变更检测"""
        if not self._cheakable:
            return
        if self.original_work['image_url'] is None or self.original_work['image_url']=='':#空的变有的当然直接变更
            self.set_state('image_url',True)
        else:
            flag=mse(str(Path(WORKCOVER_PATH/self.original_work['image_url'])),self.get_cover()) != 0
            self.set_state('image_url',flag)
        logging.debug("检测到内容变更，变更字典为%s",self._changed_flags)
        self.update_button_state()

    def update_button_state(self):
        if any(self._changed_flags.values()):
            self.set_btn_state('add_work',ButtonState.WARNING)
        else:
            self.set_btn_state('add_work',ButtonState.DISABLED)

    def set_change_widget_default(self):
        '''各种控件状态设置为原始状态'''
        for key in self._changed_flags:
            self.set_state(key,False)


    @Slot()
    def jump_detail_page(self):
        '''跳转到显示页面'''
        work_id = get_workid_by_serialnumber(self.get_serial_number().strip())
        if work_id:
            Router.instance().push("work", work_id=work_id)

    def appendTags(self,tag_list:list[int]):
        '''添加tag,不重复'''
        new_tag_list=list(set(self.tag)|set(tag_list))
        self.set_tag(new_tag_list)

#----------------------------------------------------------
#                        翻译函数
#----------------------------------------------------------

    @Slot()
    def _trans_title(self):
        '''调用google第三方翻译，不稳定，将日文翻译成中文写到框内'''
        worker=Worker(lambda:asyncio.run(translate_text(self.get_jp_title())))
        worker.signals.finished.connect(self._on_trans_title)
        QThreadPool.globalInstance().start(worker)

    @Slot()
    def _trans_story(self):
        '''调用google第三方翻译，不稳定，将日文翻译成中文写到框内'''
        worker=Worker(lambda:asyncio.run(translate_text(self.get_jp_story())))#传一个函数名进去
        worker.signals.finished.connect(self._on_trans_story)
        QThreadPool.globalInstance().start(worker)

    @Slot(str)
    def _on_trans_title(self,result:str):
        self.set_cn_title(result)

    @Slot(str)
    def _on_trans_story(self,result:str):
        self.set_cn_story(result)


class AddWorkTabPage3(LazyWidget):
    #添加作品的窗口
    '''现在有两个模式，修改模式，与添加模式，具体的区分是在于番号是否在库内，修改模式就要进行内容修改检测
    '''
    def __init__(self):
        super().__init__()

    def _lazy_load(self):
        logging.info("----------加载打开添加/更改作品信息界面----------")
        
        self.original_work={}#加载后原始的数据，用于检测内容修改
        self.msg=MessageBoxService(self)#弹窗服务
        self.model=Model()
        self.viewmodel = ViewModel(self.model,self.msg)
        self.init_ui()
        
        self.beaute()
        self.signal_connect()
        self.viewmodel.setup_change_detection()
        self.bind_model()

        #设置按钮初始的状态
        

        self.update_commit_btn("add_work",ButtonState.DISABLED)
        self.update_commit_btn("load",ButtonState.DISABLED)


    def init_ui(self) -> None:
        #第一列控件
        self.crawler_toolbox=CrawlerToolBox()
        self.coverdroplabel=CoverDropWidget()#加载拖动图片控件
        self.coverdroplabel.setMaximumWidth(200)
        self.coverdroplabel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        #第一列布局
        leftleftlayout=QVBoxLayout()
        leftleftlayout.setContentsMargins(0,0,0,0)
        leftleftlayout.addWidget(self.crawler_toolbox)
        leftleftlayout.addWidget(self.coverdroplabel,alignment=Qt.AlignHCenter)

        # 第二列控件

        self.label_serial_umber = QLabel("番       号：")
        from core.database.query import get_serial_number
        self.input_serial_number=CompleterLineEdit(get_serial_number)

        self.btn_load_form_db=QPushButton("加载")
        self.btn_jump_detail=IconPushButton("eye.svg")


        self.label_time=QLabel("发布日期：")
        self.input_time=QLineEdit()
        self.input_time.setPlaceholderText("YYYY-MM-DD")

        self.label_director=QLabel("导       演：")
        self.input_director=CompleterLineEdit(getUniqueDirector)
        
        self.label_vlength=QLabel("影片长度：")
        self.input_vlength=QLineEdit()
        self.input_vlength.setValidator(QIntValidator())
        
        self.btn_add_work = QPushButton()

        self.label_cn_title=QLabel("中文标题")
        self.cn_title=QPlainTextEdit()
        self.label_jp_title=QLabel("日文标题")
        self.jp_title=QPlainTextEdit()
        self.label_cn_story=QLabel("中文剧情")
        self.cn_story=QPlainTextEdit()
        self.label_jp_story=QLabel("日文剧情")
        self.jp_story=QPlainTextEdit()

        self.btn_trans_title=IconPushButton(iconpath="languages.svg",iconsize=16,outsize=16)
        self.btn_trans_title.setToolTip("翻译日文标题成中文并写在上方 中文标题框 内")
        self.btn_trans_story=IconPushButton(iconpath="languages.svg",iconsize=16,outsize=16)
        self.btn_trans_story.setToolTip("翻译日文剧情成中文并写在上方 中文剧情框 内")
        
    
        jp_title_label_layout=QHBoxLayout()
        jp_story_label_layout=QHBoxLayout()
        jp_title_label_layout.addWidget(self.label_jp_title)
        jp_title_label_layout.addWidget(self.btn_trans_title)
        jp_story_label_layout.addWidget(self.label_jp_story)
        jp_story_label_layout.addWidget(self.btn_trans_story)     


        #第二列布局
        left_layout=QVBoxLayout()#左侧总体垂直布局

        left_small_layout1 = QHBoxLayout()
        left_small_layout1.addWidget(self.label_serial_umber)
        left_small_layout1.addWidget(self.input_serial_number)
        left_small_layout1.addWidget(self.btn_load_form_db)
        left_small_layout1.addWidget(self.btn_jump_detail)

        left_small_layout2 = QHBoxLayout()
        left_small_layout2.addWidget(self.label_time)
        left_small_layout2.addWidget(self.input_time)

        left_small_layout3 = QHBoxLayout()
        left_small_layout3.addWidget(self.label_director)
        left_small_layout3.addWidget(self.input_director)

        left_small_layout4 = QHBoxLayout()
        left_small_layout4.addWidget(self.label_vlength)
        left_small_layout4.addWidget(self.input_vlength)


        left_layout.addLayout(left_small_layout1)
        left_layout.addLayout(left_small_layout2)
        left_layout.addLayout(left_small_layout3)
        left_layout.addLayout(left_small_layout4)

        left_layout.addWidget(self.label_cn_title)
        left_layout.addWidget(self.cn_title)
        left_layout.addWidget(self.label_cn_story)
        left_layout.addWidget(self.cn_story)
        left_layout.addLayout(jp_title_label_layout)
        left_layout.addWidget(self.jp_title)
        left_layout.addLayout(jp_story_label_layout)
        left_layout.addWidget(self.jp_story)
        left_layout.addWidget(self.btn_add_work)
        
        #第三列控件
        self.actressselector=ActressSelector()#女优选择器
        self.actorselector=ActorSelector()#男优选择器
        #第三列布局
        selector_layout=QVBoxLayout()
        selector_layout.addWidget(self.actressselector)
        selector_layout.addWidget(self.actorselector)

        #第四列控件
        self.tag_selector=TagSelector4()#tag选择器
        self.tag_selector.left_widget.setFixedWidth(140)
        self.tag_selector.tag_receive_widget.setFixedWidth(116)
        self.tag_selector.btn_expand.click()

        scroll_area=QScrollArea()
        container=QWidget()#这个是实际里面装东西的
        container.setObjectName("container")
        container.setStyleSheet("#container { background-color: white; }")
        scroll_area.setWidget(container)
        scroll_area.setWidgetResizable(True)
        layout=QVBoxLayout(container)

        #总体布局，四列组装
        toparea=QWidget()
        toparea.setMinimumHeight(600)
        hlayout = QHBoxLayout()
        toparea.setLayout(hlayout)
        hlayout.addLayout(leftleftlayout)
        hlayout.addLayout(left_layout)
        hlayout.addLayout(selector_layout)
        hlayout.addWidget(self.tag_selector)

        bottomarea=QSplitter(Qt.Horizontal)
        from ui.statistics.force_view_multi_processing import ForceViewControlWidget



        self.forceview=ForceViewControlWidget()
        self.view_session = self.forceview.view.session
        
        self.viewmodel.workload.connect(self.on_set_directview)

        self.forceview.setFixedHeight(600)
        self.forceview.setMinimumWidth(400)
        self.input_story=WikiTextEdit()
        self.input_story.setFixedHeight(600)
        self.input_story.setMinimumWidth(400)
        bottomarea.addWidget(self.forceview)
        bottomarea.addWidget(self.input_story)
        bottomarea.setStretchFactor(0, 0) # 索引1（右侧）拉伸
        bottomarea.setStretchFactor(1, 0) # 索引1（右侧）拉伸
        layout.addWidget(toparea)
        layout.addWidget(bottomarea)

        main_layout=QHBoxLayout(self)
        main_layout.addWidget(scroll_area)


    def bind_model(self) -> None:
        '''双向绑定'''
        self._updating_flags = {}#单独弄一个标记是否在更新，避免绑定循环问题
        # --------- 模型 -> UI ----------
        self.viewmodel.cover_changed.connect(self.coverdroplabel.set_image)#这些绑定实际上都是有点问题的，设置后会循环绑定的问题。

        self.viewmodel.actress_changed.connect(self.actressselector.load_with_ids)
        self.viewmodel.actor_changed.connect(self.actorselector.load_with_ids)
        self.viewmodel.tag_changed.connect(self.tag_selector.load_with_ids)

        #这个是单向的model -> UI 没有问题
        self.viewmodel.btn_state_changed.connect(self.update_commit_btn)
        self.viewmodel.modify_state_changed.connect(self.modify_state_change)
        # --------- UI -> 模型 ----------

        # 对于选择器，可以在选择变化时更新模型,这些信号都是自定义的
        self.actressselector.selection_changed.connect(
            lambda: self.viewmodel.set_actress(self.actressselector.get_selected_ids())
        )
        self.actorselector.selection_changed.connect(
            lambda: self.viewmodel.set_actor(self.actorselector.get_selected_ids())
        )
        self.tag_selector.selection_changed.connect(
            lambda: self.viewmodel.set_tag(self.tag_selector.get_selected_ids())
        )
        self.coverdroplabel.cover_changed.connect( # coverdroplabel 可以在图片改变后发信号更新模型
            lambda: self.viewmodel.set_cover(self.coverdroplabel.get_image())
        )

        bindings_map2:dict[str,QLineEdit] = {
            "serial_number": self.input_serial_number,
            "director": self.input_director,
            "release_date": self.input_time
        }
        for prop_name,widget in bindings_map2.items():
            self._updating_flags[prop_name] = False
            widget.textChanged.connect(lambda text,p=prop_name:self.lineedit_ui_to_model(p,text))
            vm_signal:SignalInstance=getattr(self.viewmodel,f"{prop_name}_changed")
            vm_signal.connect(lambda text, w=widget,p=prop_name:self.lineedit_model_to_ui(w,p,text))

        #这样可以完整的处理好同一个类型的绑定问题，避免其回环，UI->model单向，model->UI单向，各自独立
        bindings_map:dict[str,QTextEdit] = {
            "cn_title": self.cn_title,
            "cn_story": self.cn_story,
            "jp_title": self.jp_title,
            "jp_story": self.jp_story,
            "story": self.input_story
        }
        for prop_name,widget in bindings_map.items():
            self._updating_flags[prop_name] = False
            widget.textChanged.connect(lambda p=prop_name,w=widget:self.textedit_ui_to_model(w,p))#匿名函数作为槽函数
            vm_signal:SignalInstance=getattr(self.viewmodel,f"{prop_name}_changed")
            vm_signal.connect(lambda text, w=widget,p=prop_name:self.textedit_model_to_ui(w,p,text))#匿名函数作为槽函数

    #处理绑定循环的问题
    def textedit_ui_to_model(self,widget:QPlainTextEdit,prop_name:str):
        if self._updating_flags.get(prop_name, False):
            return
        self._updating_flags[prop_name] = True
        setter_method=getattr(self.viewmodel,f"set_{prop_name}")
        setter_method(widget.toPlainText())
        self._updating_flags[prop_name] = False

    def textedit_model_to_ui(self, widget: QPlainTextEdit,prop_name:str ,text: str):
        if self._updating_flags.get(prop_name, False):
            return
        self._updating_flags[prop_name] = True
        widget.clear()
        widget.setPlainText(text)
        self._updating_flags[prop_name] = False

    def lineedit_ui_to_model(self,prop_name:str,text:str):
        if self._updating_flags.get(prop_name, False):
            return
        self._updating_flags[prop_name] = True
        setter_method=getattr(self.viewmodel,f"set_{prop_name}")
        setter_method(text)
        self._updating_flags[prop_name] = False

    def lineedit_model_to_ui(self,widget:QTextEdit,prop_name:str,text):
        if self._updating_flags.get(prop_name, False):
            return
        self._updating_flags[prop_name] = True
        widget.setText(text)
        self._updating_flags[prop_name] = False


#----------------------------------------------------------
#                       信号连接
#----------------------------------------------------------
    def signal_connect(self):
        '''按钮信号连接'''
        self.viewmodel.serial_number_changed.connect(self.viewmodel.on_work_selected)#核心
        self.input_serial_number.returnPressed.connect(self.viewmodel._load_from_db)#按enter后查询


        self.btn_load_form_db.clicked.connect(self.viewmodel._load_from_db)
        self.btn_jump_detail.clicked.connect(self.viewmodel.jump_detail_page)

        self.btn_trans_title.clicked.connect(self.viewmodel._trans_title)
        self.btn_trans_story.clicked.connect(self.viewmodel._trans_story)

        from core.crawler.jump import jump_javlibrary,jump_javdb,jump_javtxt,jump_missav,jump_avmoo,jump_fanza,jump_mgs,jump_avdanyuwiki,jump_netflav,jump_jinjier,jump_kana,jump_gana,jump_123av,jump_jable,jump_supjav
        self.crawler_toolbox.btn_get_javlibrary.clicked.connect(lambda:jump_javlibrary(self.input_serial_number.text()))
        self.crawler_toolbox.btn_get_javdb.clicked.connect(lambda:jump_javdb(self.input_serial_number.text()))
        self.crawler_toolbox.btn_get_javtxt.clicked.connect(lambda:jump_javtxt(self.input_serial_number.text()))
        self.crawler_toolbox.btn_get_missav.clicked.connect(lambda:jump_missav(self.input_serial_number.text()))
        self.crawler_toolbox.btn_get_avmoo.clicked.connect(lambda:jump_avmoo(self.input_serial_number.text()))
        self.crawler_toolbox.btn_get_avdanyuwiki.clicked.connect(lambda:jump_avdanyuwiki(covert_fanza(self.input_serial_number.text())))
        self.crawler_toolbox.btn_get_123av.clicked.connect(lambda:jump_123av(self.input_serial_number.text()))
        self.crawler_toolbox.btn_get_jable.clicked.connect(lambda:jump_jable(self.input_serial_number.text()))
        self.crawler_toolbox.btn_get_supjav.clicked.connect(lambda:jump_supjav(self.input_serial_number.text()))
        self.crawler_toolbox.btn_get_fanza.clicked.connect(jump_fanza)
        self.crawler_toolbox.btn_get_mgs.clicked.connect(jump_mgs)
        self.crawler_toolbox.btn_get_netflav.clicked.connect(jump_netflav)
        self.crawler_toolbox.btn_get_jinjier.clicked.connect(jump_jinjier)
        self.crawler_toolbox.btn_get_kana.clicked.connect(jump_kana)
        self.crawler_toolbox.btn_get_gana.clicked.connect(jump_gana)

        self.btn_add_work.clicked.connect(self.viewmodel.submit)
        self.crawler_toolbox.btn_get_crawler.clicked.connect(self.crawler2)

        global_signals.gui_update.connect(self.update_gui)
        global_signals.download_success.connect(self.update_cover)


#----------------------------------------------------------
#          爬虫函数，QCheckBox触发，未MVVM,与UI耦合
#----------------------------------------------------------
    def crawler2(self):
        '''用浏览器插件手动跳转javlibrary'''
        from core.crawler.CrawlerManager import crawler_manager2
        crawler_manager2.start_crawl(self.viewmodel.serial_number,True)

    def update_gui(self,data):
        '''更新gui'''
        if self.crawler_toolbox.cb_release_date.isChecked():
            self.viewmodel.set_release_date(data["release_date"])
        if self.crawler_toolbox.cb_director.isChecked():
            self.viewmodel.set_director(data["director"])
        if self.crawler_toolbox.cb_actress.isChecked():
            self.viewmodel.set_actress(data["actress_list"])
        if self.crawler_toolbox.cb_actor.isChecked():
            self.viewmodel.set_actor(data["actor_list"])
        if self.crawler_toolbox.cb_cn_title.isChecked():
            self.viewmodel.set_cn_title(data["cn_title"])
        if self.crawler_toolbox.cb_cn_story.isChecked():
            self.viewmodel.set_cn_story(data["cn_story"])
        if self.crawler_toolbox.cb_jp_title.isChecked():
            self.viewmodel.set_jp_title(data["jp_title"])
        if self.crawler_toolbox.cb_jp_story.isChecked():
            self.viewmodel.set_jp_story(data["jp_story"])
        if self.crawler_toolbox.cb_tag.isChecked():
            cur_tag_id=self.viewmodel.get_tag()
            self.viewmodel.set_tag(list(set(cur_tag_id)|set(data["tag_id_list"])))

    def update_cover(self,file_path:str):
        '''更新封面'''
        logging.info(f"更新封面:{file_path}")
        if self.crawler_toolbox.cb_cover.isChecked():
            self.viewmodel.set_cover(file_path)
        

    def on_set_directview(self,id:str):
        from core.graph.graph_filter import EgoFilter
        self.forceview.view.session.set_filter(EgoFilter(center_id=id, radius=2))
        self.forceview.view.session.reload()
        self.forceview.view.nodelayer.center_node_id=id

#----------------------------------------------------------
#                         UI样式修改
#----------------------------------------------------------
    def beaute(self):
        '''控件美化'''
        self.btn_load_form_db.setStyleSheet("""
            QPushButton {
                background-color: orange;
                color: white;
            }
            QPushButton:disabled {
                background-color: gray;
                color: darkGray;
            }
        """)

    @Slot(str,ButtonState)
    def update_commit_btn(self,key:str,state:ButtonState):
        '''
        self._btn_state={
            'add_work':ButtonState.DISABLED,
            'load':ButtonState.WARNING,
            'temp_save':ButtonState.DISABLED,
            'temp_load':ButtonState.NORMAL
        }
        '''
        match key:
            case 'add_work':
                if state == ButtonState.NORMAL:
                    self.btn_add_work.setEnabled(True)
                    self.btn_add_work.setText("添加")
                    self.btn_add_work.setStyleSheet("""
                        QPushButton {
                            background-color: #4CAF50;
                            color: white;
                            border-radius: 5px;
                            padding: 6px;
                        }
                    """)
                elif state == ButtonState.WARNING:
                    self.btn_add_work.setEnabled(True)
                    self.btn_add_work.setText("修改")
                    self.btn_add_work.setStyleSheet("""           
                            QPushButton {
                            background-color: #FF9800;
                            color: white;
                            border-radius: 5px;
                            padding: 6px;}
                        """)
                elif state == ButtonState.DISABLED:
                    self.btn_add_work.setEnabled(False)
                    self.btn_add_work.setText("----")
                    self.btn_add_work.setStyleSheet("""
                        QPushButton {
                            background-color: #999999;
                            color: #CCCCCC;
                            border-radius: 5px;
                            padding: 6px;
                        }
                    """)
            case 'load':
                if state == ButtonState.WARNING:
                    self.btn_load_form_db.setDisabled(False)
                elif state == ButtonState.DISABLED:
                    self.btn_load_form_db.setDisabled(True)
    
    @Slot(str, bool)
    def modify_state_change(self,key:str,value:bool):
        highlight_line = "QLineEdit { border: 2px solid #FFA500; }"
        highlight_text = "QPlainTextEdit { border: 2px solid #FFA500; }"
        highlight_list = "QListView { border: 2px solid #FFA500; }"
        highlight_cover = "border: 2px dashed orange; font-size: 16px; padding: 0px;margin: 0px;"
        normal_cover = "border: 2px dashed grey; font-size: 16px; padding: 0px;margin: 0px;"
        highlight_text2="QTextEdit { border: 2px solid #FFA500; }"

        mapping = [
            ("story", self.input_story, highlight_text2, ""),
            ("director", self.input_director, highlight_line, ""),
            ("release_date", self.input_time, highlight_line, ""),
            ("cn_title", self.cn_title, highlight_text, ""),
            ("jp_title", self.jp_title, highlight_text, ""),
            ("cn_story", self.cn_story, highlight_text, ""),
            ("jp_story", self.jp_story, highlight_text, ""),
            ("actress_ids", self.actressselector.receive_actress_view, highlight_list, ""),
            ("actor_ids", self.actorselector.receive_actor_view, highlight_list, ""),
            ("image_url", self.coverdroplabel, highlight_cover, normal_cover),
        ]

        for field, widget, style_on, style_off in mapping:
            if key==field:
                if value:
                    widget.setStyleSheet(style_on)
                else:
                    widget.setStyleSheet(style_off)
        # 控制方法有两种，一种是直接控制，还有种是控件写出一个接口
        if key=="tag_ids":
            if value:
                self.tag_selector.set_state(False)
            else:
                self.tag_selector.set_state(True)

