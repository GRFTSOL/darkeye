from PySide6.QtCore import QObject, Signal


class GlobalSignalBus(QObject):
    """全局信号总线,生存周期长周期"""

    # 数据变更相关
    workDataChanged = Signal()  # 作品数据变更信号
    actressDataChanged = Signal()  # 女优数据变更信号,主要是刷新女优选择器
    actorDataChanged = Signal()  # 男优数据变更信号，主要是刷新男优选择器
    tagDataChanged = Signal()  # 标签数据变更信号，主要是刷新标签选择器
    makerDataChanged = Signal()  # 片商数据变更信号，主要是刷新片商选择器
    labelDataChanged = Signal()  # 厂牌数据变更信号，主要是刷新厂牌选择器
    seriesDataChanged = Signal()  # 系列数据变更信号，主要是刷新系列选择器

    # 记录相关
    masterbationChanged = Signal()  # 撸管记录变更信号
    lovemakingChanged = Signal()  # 做爱记录变更信号
    sexarousalChanged = Signal()  # 晨勃记录变更信号

    # 偏好与模式相关
    greenModeChanged = Signal(bool)  # 绿色模式切换信号，参数是当前状态
    likeWorkChanged = Signal()  # 喜欢作品的信号修改
    likeActressChanged = Signal()  # 喜欢的女优更改信号

    # 状态栏与简单通知
    statusMsgChanged = Signal(str)  # 通知状态栏文字变更信号

    # 下载结果与 GUI 更新
    downloadSuccess = Signal(str)  # 图片下载成功信号，参数是文件路径
    guiUpdate = Signal(dict)  # 通知GUI更新信号

    # 下载 Inbox / 任务进度相关信号
    # serial: 任务标识（例如作品番号），total: 预期总进度（如总张数或总步骤）
    downloadTaskStarted = Signal(str, int)
    # current: 当前进度值（如已完成数），msg: 人类可读的提示文本
    downloadTaskProgress = Signal(str, int, int, str)
    # success: 是否成功完成，msg: 收尾提示（错误原因或完成说明）
    downloadTaskFinished = Signal(str, bool, str)
    # 爬取入库后按库内状态刷新 15 维完整度；object 为 dict[str, bool]（key 同 WORK_COMPLETENESS_KEYS）
    workCrawlCompleteness = Signal(str, object)


global_signals = GlobalSignalBus()
