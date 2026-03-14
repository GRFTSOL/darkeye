
from typing import Dict
import logging
from PySide6.QtCore import QThreadPool
from server.bridge import bridge

#这个逻辑全在js里爬，

def jump_to_javdb(serial_number):
    '''启动浏览器插件爬虫进行爬取 (同步阻塞模式)，将原本的异步回调改成同步阻塞'''
    import threading
    from core.crawler.jump import send_crawler_request
    from server.bridge import bridge
    
    # 1. 准备同步原语
    event = threading.Event()
    result_container = {"data": {}}
    web = "javdb"

    # 2. 定义临时回调函数
    def temp_callback(data):
        #logging.info(f"收到的javlib数据为{data}")
        if data.get("id") == serial_number:
            result_container["data"] = data
            event.set() # 解锁阻塞

    # 3. 连接信号
    # 注意：这里需要确保 signal 是唯一的或者能正确断开
    # 如果 bridge 是单例，connect 会累积，所以要在 finally 里 disconnect
    bridge.javdb_finished.connect(temp_callback)

    try:
        # 4. 发送请求
        send_crawler_request(web, serial_number)
        
        # 5. 阻塞等待 (超时 60 秒)
        is_set = event.wait(timeout=20)
        
        if not is_set:
            logging.info(f"Error: Javdb crawl timeout for {serial_number}")
            return {}
        #logging.info(f"这个函数返回的javdb的数据为{result_container["data"]}")
        return result_container["data"]

    finally:
        # 6. 清理：必须断开连接，否则下次请求会触发旧的回调
        try:
            bridge.javdb_finished.disconnect(temp_callback)
        except Exception:
            pass # 防止未连接时断开报错


