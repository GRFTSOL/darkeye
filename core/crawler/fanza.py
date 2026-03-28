# 这里用浏览器爬fanza
from pathlib import Path
import sys
from typing import Dict

root_dir = Path(__file__).resolve().parents[2]  # 上两级
sys.path.insert(0, str(root_dir))


from core.crawler.Worker import Worker
from PySide6.QtCore import QThreadPool
from server.bridge import bridge


def jump_to_fanza(serial_number):
    """启动浏览器插件爬虫进行爬取"""
    from core.crawler.Worker import Worker

    web = "fanza"
    from core.crawler.jump import send_crawler_request

    worker = Worker(lambda: send_crawler_request(web, serial_number))
    QThreadPool.globalInstance().start(worker)


def on_fanza_finished(data: Dict):
    """处理爬虫的结果"""
    print(data)


bridge.fanzaFinished.connect(on_fanza_finished)
