from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import json, sqlite3, asyncio, logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .bridge import bridge

from config import DATABASE

# 配置日志
logger = logging.getLogger("server")

app = FastAPI(title="DarkEye Internal Server")

# SSE 客户端列表
sse_clients: List[asyncio.Queue] = []

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，方便开发插件
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CheckExistenceRequest(BaseModel):
    items: List[str]


class CaptureData(BaseModel):
    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    # 允许接收任意额外字段
    extra: Optional[Dict[str, Any]] = None


class NavigateCommand(BaseModel):
    url: str
    target: str = "new_tab"  # new_tab 或 current_tab
    context: Optional[Dict[str, Any]] = (
        None  # 例如 { "actress_id": 1, "source": "minnano_manual" }
    )


@app.get("/api/v1/health")
async def health_check():
    """
    健康检查接口
    """
    return {"status": "ok", "service": "DarkEye Server"}


@app.post("/api/v1/check_existence")
async def check_existence(request: CheckExistenceRequest):
    """
    批量检查番号是否存在于本地数据库
    """
    try:
        items = request.items
        if not items:
            return {"results": {}}

        # 预处理：转大写，去除空白
        cleaned_items = [item.strip().upper() for item in items]

        # 构造结果字典，初始全为 False
        results = {item: False for item in items}

        if not cleaned_items:
            return {"results": results}

        placeholders = ",".join(["?"] * len(cleaned_items))
        # 使用 UPPER 进行忽略大小写的匹配
        query = f"SELECT serial_number FROM work WHERE UPPER(serial_number) IN ({placeholders})"

        # 使用只读模式连接数据库，避免锁冲突
        try:
            with sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True) as conn:
                cursor = conn.cursor()
                cursor.execute(query, cleaned_items)
                rows = cursor.fetchall()

                existing_serials = set(row[0].upper() for row in rows)

                # 更新结果
                for item in items:
                    if item.strip().upper() in existing_serials:
                        results[item] = True
        except sqlite3.OperationalError as e:
            logger.error(f"Database error: {e}")
            # 如果数据库连接失败，可能需要降级处理或返回错误，这里暂时返回空结果或抛出
            raise

        return {"results": results}

    except Exception as e:
        logger.error(f"Error checking existence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/minnano-actress-capture")
async def receive_minnano_actress_capture(body: Dict[str, Any]):
    """
    接收插件在女优详情页采集的完整字段，经 bridge 回填编辑界面。
    body: { "context": { "actress_id"? }, "data": { 日文名, ... }, "url"? }
    """
    try:
        logger.info("Received minnano actress capture from extension")
        bridge.minnanoActressCaptureReceived.emit(body)
        return {"status": "success", "message": "Data received"}
    except Exception as e:
        logger.error(f"Error processing minnano actress capture: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/actressid")
async def receive_actressid(data: Dict[str, Any]):
    """
    接收来自插件的抓取 actressid 数据
    """
    try:
        logger.info(f"Received capture data from: {data.get('url', 'unknown')}")
        # 发射信号，将数据传递给主线程
        raw_id = data.get("id", -1)
        try:
            id = int(raw_id)
        except (ValueError, TypeError):
            logger.warning(f"Invalid ID format: {raw_id}")
            id = -1

        logger.info(f"actressid:{id}")
        bridge.actressIdReceived.emit(id)
        return {"status": "success", "message": "Data received"}
    except Exception as e:
        logger.error(f"Error processing capture data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/capture")
async def receive_capture(data: Dict[str, Any]):
    """
    接收来自插件的抓取数据，只有普通的页面抓取数据，不包含ID抓取，这个是
    """
    try:
        logger.info(f"Received capture data from: {data.get('url', 'unknown')}")
        # 发射信号，将数据传递给主线程
        bridge.captureReceived.emit(data)
        return {"status": "success", "message": "Data received"}
    except Exception as e:
        logger.error(f"Error processing capture data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/capture/one")
async def captureone(data: Dict[str, Any]):
    """
    接收来自插件的要抓取的单个番号，直接录入，不经过确认，信号传出去后直接爬
    现在的目前是连续两次后就崩溃
    """
    try:
        logger.info(f"Received capture data from: {data.get('url', 'unknown')}")
        # 发射信号，将数据传递给主线程
        bridge.captureOneReceived.emit(str(data["content"]))
        print(str(data["content"]))

        return {"status": "success", "message": "Data received"}
    except Exception as e:
        logger.error(f"Error processing capture data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/navigate")
async def send_navigate(command: NavigateCommand):
    """
    发送导航指令给所有连接的插件
    """
    logger.info(f"Broadcasting navigate command: {command}")
    dead_clients = []
    message = {
        "type": "navigate",
        "url": command.url,
        "target": command.target,
    }
    if command.context is not None:
        message["context"] = command.context
    event_data = f"data: {json.dumps(message)}\n\n"

    for client in sse_clients:
        try:
            await client.put(event_data)
        except Exception:
            dead_clients.append(client)

    for dead in dead_clients:
        if dead in sse_clients:
            sse_clients.remove(dead)

    return {"status": "success", "count": len(sse_clients)}


class CrawlerRequest(BaseModel):
    web: str
    serial_number: str


class CrawlerBacklogWarningBody(BaseModel):
    count: int
    browser: str = "firefox"
    threshold: int = 7


@app.post("/api/v1/crawler-backlog-warning")
async def crawler_backlog_warning(body: CrawlerBacklogWarningBody):
    """
    浏览器插件报告专用爬虫窗口标签过多，通知桌面弹窗。
    """
    if body.count < body.threshold:
        return {"status": "ignored", "reason": "below_threshold"}
    try:
        logger.info(
            "Crawler backlog warning: browser=%s count=%s threshold=%s",
            body.browser,
            body.count,
            body.threshold,
        )
        bridge.crawlerBacklogWarning.emit(body.count, body.browser)
        return {"status": "success", "message": "notified"}
    except Exception as e:
        logger.error("crawler_backlog_warning: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/startcrawler")
async def start_crawler(data: CrawlerRequest):
    """
    发送爬虫指令给插件，指定要爬取的网站和番号
    """
    logger.info(f"广播爬虫指令: {data.web} {data.serial_number}")
    dead_clients = []
    message = {"type": "crawler", "web": data.web, "serial_number": data.serial_number}
    event_data = f"data: {json.dumps(message)}\n\n"

    for client in sse_clients:
        try:
            await client.put(event_data)
        except Exception:
            dead_clients.append(client)

    for dead in dead_clients:
        if dead in sse_clients:
            sse_clients.remove(dead)

    return {"status": "success", "count": len(sse_clients)}


@app.post("/api/v1/crawler-result")
async def receive_crawler_result(data: Dict[str, Any]):
    """
    接收来自插件的抓取的爬虫数据并分流
    """
    try:
        logger.info(f"收到插件的抓取的爬虫数据")
        # 发射信号，将数据传递给主线程
        web = data.get("web", "")  # 根据爬取的网站分流
        if web == "javlib":
            # logging.info(f"收到的javlib数据为{data.get('data',{})}")
            bridge.javlibFinished.emit(data.get("data", {}))
        elif web == "javdb":
            bridge.javdbFinished.emit(data.get("data", {}))
        elif web == "fanza":
            pass
        else:
            print("非法消息")
        return {"status": "success", "message": "Data received"}
    except Exception as e:
        logger.error(f"Error processing capture data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/events")
async def sse_endpoint(request: Request):
    """
    SSE 端点，插件连接到这里接收指令
    """

    async def event_generator():
        client_queue = asyncio.Queue()
        sse_clients.append(client_queue)
        try:
            while True:
                if await request.is_disconnected():
                    break
                # 等待新消息
                data = await client_queue.get()
                yield data
        except asyncio.CancelledError:
            pass
        finally:
            if client_queue in sse_clients:
                sse_clients.remove(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
