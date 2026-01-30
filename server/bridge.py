from PySide6.QtCore import QObject, Signal

class ServerBridge(QObject):
    """
    用于连接 FastAPI 线程和 PyQt 主线程的桥梁。
    单例模式，确保全局只有一个实例。
    """
    # 定义信号，传递字典类型的数据
    capture_received = Signal(dict)
    actressid_received = Signal(int)
    captureone_received = Signal(str)
    javlib_finished = Signal(dict)
    fanza_finished=Signal(dict)
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ServerBridge, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # 确保只初始化一次
        if not hasattr(self, '_initialized'):
            super().__init__()
            self._initialized = True

# 全局单例
bridge = ServerBridge()
