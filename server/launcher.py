
import logging

logger = logging.getLogger("server")


class ServerLauncher:
    def __init__(self, host="127.0.0.1", port=56789):
        self.host = host
        self.port = port
        self.server_thread = None

    def _run(self):
        try:
            # 在后台线程内导入，避免主线程加载 FastAPI/uvicorn（约省 3s）
            from .app import app
            import uvicorn
            logger.info(f"Starting API server at http://{self.host}:{self.port}")
            # log_config=None 防止 uvicorn 覆盖我们的 logging 配置
            uvicorn.run(app, host=self.host, port=self.port, log_config=None)
        except Exception as e:
            logger.error(f"Failed to start API server: {e}")


    def start(self):
        """
        在后台线程启动服务器
        """
        import threading
        if self.server_thread is None or not self.server_thread.is_alive():
            self.server_thread = threading.Thread(target=self._run, daemon=True)
            self.server_thread.start()
            logger.info("API Server thread started")

# 全局启动器实例
server_launcher = ServerLauncher()
