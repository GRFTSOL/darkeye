from PySide6.QtCore import QObject, Signal


# 这个一行要运行在主线程
class ServerBridge(QObject):
    """
    用于连接 FastAPI 线程和 PyQt 主线程的桥梁。
    单例模式，确保全局只有一个实例。
    """

    # 定义信号，传递字典类型的数据
    captureReceived = Signal(dict)
    actressIdReceived = Signal(int)
    minnanoActressCaptureReceived = Signal(dict)
    captureOneReceived = Signal(str)
    javlibFinished = Signal(dict)
    fanzaFinished = Signal(dict)
    javdbFinished = Signal(dict)
    javtxtFinished = Signal(dict)
    crawlerBacklogWarning = Signal(int, str)
    # 浏览器插件拉取 DMM 封面完成：request_id, 临时文件绝对路径或 None, 错误说明（成功为空串）
    coverBrowserFetchResult = Signal(str, object, str)

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ServerBridge, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # 确保只初始化一次
        if not hasattr(self, "_initialized"):
            super().__init__()
            self._initialized = True


# 全局单例（必须在主线程首次 import 本模块时创建）
bridge = ServerBridge()


def get_bridge() -> ServerBridge:
    """返回全局单例。导入并调用此函数可避免被 linter 判为未使用而删除导入。"""
    return bridge
