
from PySide6.QtCore import QObject, Signal


class GlobalSignalBus(QObject):
    """全局信号总线,生存周期长周期"""

    # 数据变更相关
    work_data_changed = Signal()  # 作品数据变更信号
    actress_data_changed = Signal()  # 女优数据变更信号,主要是刷新女优选择器
    actor_data_changed = Signal()  # 男优数据变更信号，主要是刷新男优选择器
    tag_data_changed = Signal()  # 标签数据变更信号，主要是刷新标签选择器

    # 记录相关
    masterbation_changed = Signal()  # 撸管记录变更信号
    lovemaking_changed = Signal()  # 做爱记录变更信号
    sexarousal_changed = Signal()  # 晨勃记录变更信号

    # 偏好与模式相关
    green_mode_changed = Signal(bool)  # 绿色模式切换信号，参数是当前状态
    like_work_changed = Signal()  # 喜欢作品的信号修改
    like_actress_changed = Signal()  # 喜欢的女优更改信号

    # 状态栏与简单通知
    status_msg_changed = Signal(str)  # 通知状态栏文字变更信号

    # 下载结果与 GUI 更新
    download_success = Signal(str)  # 图片下载成功信号，参数是文件路径
    gui_update = Signal(dict)  # 通知GUI更新信号

    # 下载 Inbox / 任务进度相关信号
    # serial: 任务标识（例如作品番号），total: 预期总进度（如总张数或总步骤）
    download_task_started = Signal(str, int)
    # current: 当前进度值（如已完成数），msg: 人类可读的提示文本
    download_task_progress = Signal(str, int, int, str)
    # success: 是否成功完成，msg: 收尾提示（错误原因或完成说明）
    download_task_finished = Signal(str, bool, str)


global_signals = GlobalSignalBus()