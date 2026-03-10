
from PySide6.QtCore import QObject, Signal

class GlobalSignalBus(QObject):
    """全局信号总线,生存周期长周期"""
    work_data_changed = Signal()  # 作品数据变更信号
    actress_data_changed = Signal()  # 女优数据变更信号,主要是刷新女优选择器
    actor_data_changed = Signal()  # 男优数据变更信号，主要是刷新男优选择器
    tag_data_changed=Signal()#标签数据变更信号，主要是刷新标签选择器

    masterbation_changed=Signal() # 撸管记录变更信号
    lovemaking_changed=Signal() #做爱记录变更信号
    sexarousal_changed=Signal() #晨勃记录变更信号
    green_mode_changed=Signal(bool) #绿色模式切换信号，参数是当前状态
    like_work_changed=Signal()#喜欢作品的信号修改
    like_actress_changed=Signal()#喜欢的女优更改信号

    status_msg_changed = Signal(str)  # 通知状态栏文字变更信号
    download_success=Signal(str)#图片下载成功信号，参数是文件路径
    gui_update=Signal(dict)#通知GUI更新信号




global_signals = GlobalSignalBus()