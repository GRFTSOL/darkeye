from PySide6.QtCore import QObject, Signal


# 这个一行要运行在主线程
class ServerBridge(QObject):
    """
    用于连接 FastAPI 线程和 PyQt 主线程的桥梁。
    单例模式，确保全局只有一个实例。
    """

    # 定义信号，传递字典类型的数据
    capture_received = Signal(dict)
    actressid_received = Signal(int)
    minnano_actress_capture_received = Signal(dict)
    captureone_received = Signal(str)
    javlib_finished = Signal(dict)
    fanza_finished = Signal(dict)
    javdb_finished = Signal(dict)

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
