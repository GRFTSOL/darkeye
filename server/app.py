from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import base64
import json, sqlite3, asyncio, logging, uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .bridge import bridge

from config import DATABASE, TEMP_PATH

# 配置日志
logger = logging.getLogger("server")

app = FastAPI(title="DarkEye Internal Server")

# SSE 客户端列表
sse_clients: List[asyncio.Queue] = []

# GET /api/v1/work/{serial} 同步等待：request_id -> Future（插件 POST work-merge-result 完成）
WORK_MERGE_TIMEOUT_SEC = 120.0
_work_merge_lock = asyncio.Lock()
_work_merge_futures: Dict[str, asyncio.Future] = {}

# GET /api/v1/actress/{name}同步等待（插件 POST actress-fetch-result）
_actress_fetch_lock = asyncio.Lock()
_actress_fetch_futures: Dict[str, asyncio.Future] = {}
_actress_fetch_names: Dict[str, str] = {}

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
    批量检查番号是否存在于本地数据库,这个是给浏览器插件用的
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
    接收插件在女优详情页采集的完整字段，经 bridge 回填编辑界面。这个是给浏览器插件用的
    body: { "context": { "actress_id"? , "persist"? }, "data": { 日文名, ... }?,
          "url"?, "error"? } — 仅 error + context 时表示自动更新失败（如多条搜索结果）
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

    # 组装消息
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
    context: Optional[Dict[str, Any]] = None


class CrawlerBacklogWarningBody(BaseModel):
    count: int
    browser: str = "firefox"
    threshold: int = 13


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
    logger.info(f"广播爬虫指令: {data.web} {data.serial_number} {data.context!r}")
    dead_clients = []
    message: Dict[str, Any] = {
        "type": "crawler",
        "web": data.web,
        "serial_number": data.serial_number,
    }
    if data.context is not None:
        message["context"] = data.context
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
        elif web == "javtxt":
            bridge.javtxtFinished.emit(data.get("data", {}))
        elif web == "javtxt-top-actresses":
            inner = data.get("data") or {}
            names = inner.get("names")
            if not isinstance(names, list):
                names = []
            bridge.javtxtTopActressesFinished.emit(
                {
                    "ok": bool(data.get("results")),
                    "names": names,
                    "error": inner.get("error"),
                }
            )
        elif web == "avdanyuwiki":
            bridge.avdanyuwikiFinished.emit(data.get("data", {}))
        elif web == "fanza":
            pass
        else:
            logger.warning("未识别的 crawler-result web: %s", web)
        return {"status": "success", "message": "Data received"}
    except Exception as e:
        logger.error(f"Error processing capture data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class WorkMergeResultBody(BaseModel):
    """Firefox 插件四站合并完成后回传，解除 GET /api/v1/work/{serial} 的挂起。"""

    request_id: str
    ok: bool
    merged: Optional[Dict[str, Any]] = None
    per_site: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    serial_number: Optional[str] = None


@app.get("/api/v1/work/{serial_number}")
async def get_work_merge(serial_number: str):
    """
    同步聚合四站（javlib / javdb / javtxt / avdanyuwiki）：经 SSE 通知插件并行爬取，
    等待插件 POST /api/v1/work-merge-result；不触发 bridge 爬虫信号。
    """
    sn = serial_number.strip()
    if not sn:
        raise HTTPException(status_code=400, detail="serial_number required")
    if len(sse_clients) == 0:
        logger.info("work_merge: reject serial=%s reason=no_sse_clients", sn)
        raise HTTPException(
            status_code=503,
            detail="no browser extension connected (SSE)",
        )

    request_id = str(uuid.uuid4())
    fut: asyncio.Future = asyncio.get_running_loop().create_future()
    async with _work_merge_lock:
        _work_merge_futures[request_id] = fut

    n_sse = len(sse_clients)
    logger.info(
        "work_merge: wait start serial=%s request_id=%s sse_listeners=%s timeout_s=%s",
        sn,
        request_id,
        n_sse,
        WORK_MERGE_TIMEOUT_SEC,
    )

    message = {
        "type": "work_merge_fetch",
        "request_id": request_id,
        "serial_number": sn,
    }
    event_data = f"data: {json.dumps(message)}\n\n"
    dead_clients: List[asyncio.Queue] = []
    for client in sse_clients:
        try:
            await client.put(event_data)
        except Exception:
            dead_clients.append(client)
    for dead in dead_clients:
        if dead in sse_clients:
            sse_clients.remove(dead)

    logger.info(
        "work_merge: sse_broadcast serial=%s request_id=%s pushed_to=%s dead_removed=%s",
        sn,
        request_id,
        n_sse,
        len(dead_clients),
    )

    try:
        payload = await asyncio.wait_for(fut, timeout=WORK_MERGE_TIMEOUT_SEC)
        ok = payload.get("ok") if isinstance(payload, dict) else None
        err = payload.get("error") if isinstance(payload, dict) else None
        logger.info(
            "work_merge: done serial=%s request_id=%s ok=%s error=%s",
            sn,
            request_id,
            ok,
            err,
        )
        try:
            logger.info(
                "work_merge: response payload serial=%s request_id=%s\n%s",
                sn,
                request_id,
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            )
        except Exception as e:
            logger.warning(
                "work_merge: could not serialize payload for log serial=%s: %s",
                sn,
                e,
            )
        return payload
    except asyncio.TimeoutError:
        logger.warning(
            "work_merge: timeout serial=%s request_id=%s after_s=%s",
            sn,
            request_id,
            WORK_MERGE_TIMEOUT_SEC,
        )
        raise HTTPException(
            status_code=504,
            detail="work merge timed out waiting for browser extension",
        )
    finally:
        async with _work_merge_lock:
            _work_merge_futures.pop(request_id, None)
        logger.debug("work_merge: future slot cleared request_id=%s", request_id)


@app.post("/api/v1/work-merge-result")
async def receive_work_merge_result(body: WorkMergeResultBody):
    """插件合并完成后调用；与 crawler-result 分流，不发射 bridge 爬虫信号。"""
    rid = (body.request_id or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="request_id required")

    async with _work_merge_lock:
        fut = _work_merge_futures.get(rid)
    if fut is None:
        return {"status": "ignored", "reason": "unknown_or_finished_request"}
    if fut.done():
        return {"status": "ignored", "reason": "already_completed"}

    sn = (body.serial_number or "").strip()
    out: Dict[str, Any] = {
        "ok": body.ok,
        "serial_number": sn,
        "data": body.merged,
        "per_site": body.per_site or {},
    }
    if body.error:
        out["error"] = body.error
    fut.set_result(out)
    return {"status": "success"}


class ActressFetchResultBody(BaseModel):
    """Firefox 插件 minnano 女优页采集完成后回传，解除 GET /api/v1/actress/{name} 的挂起。"""

    request_id: str
    ok: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    actress_jp_name: Optional[str] = None


@app.get("/api/v1/actress/{actress_jp_name}")
async def get_actress_minnano(
    actress_jp_name: str,
    minnano_url: Optional[str] = Query(
        None,
        description="缓存的 minnano 详情 id（数字片段），非空则直达 actress{id}.html",
    ),
):
    """
    同步拉取 minnano 女优信息：经 SSE 通知插件打开搜索/详情并采集，
    等待 POST /api/v1/actress-fetch-result；不触发 bridge、不写库。
    """
    jp = actress_jp_name.strip()
    mid = (minnano_url or "").strip()
    if not jp:
        raise HTTPException(status_code=400, detail="actress_jp_name required")
    if len(sse_clients) == 0:
        logger.info("actress_fetch: reject jp=%s reason=no_sse_clients", jp)
        raise HTTPException(
            status_code=503,
            detail="no browser extension connected (SSE)",
        )

    request_id = str(uuid.uuid4())
    fut: asyncio.Future = asyncio.get_running_loop().create_future()
    async with _actress_fetch_lock:
        _actress_fetch_futures[request_id] = fut
        _actress_fetch_names[request_id] = jp

    n_sse = len(sse_clients)
    logger.info(
        "actress_fetch: wait start jp=%s request_id=%s sse_listeners=%s timeout_s=%s",
        jp,
        request_id,
        n_sse,
        WORK_MERGE_TIMEOUT_SEC,
    )

    message: Dict[str, Any] = {
        "type": "minnano_actress_fetch",
        "request_id": request_id,
        "actress_jp_name": jp,
    }
    if mid:
        message["minnano_url"] = mid
    event_data = f"data: {json.dumps(message)}\n\n"
    dead_clients: List[asyncio.Queue] = []
    for client in sse_clients:
        try:
            await client.put(event_data)
        except Exception:
            dead_clients.append(client)
    for dead in dead_clients:
        if dead in sse_clients:
            sse_clients.remove(dead)

    logger.info(
        "actress_fetch: sse_broadcast jp=%s request_id=%s pushed_to=%s dead_removed=%s",
        jp,
        request_id,
        n_sse,
        len(dead_clients),
    )

    try:
        payload = await asyncio.wait_for(fut, timeout=WORK_MERGE_TIMEOUT_SEC)
        ok = payload.get("ok") if isinstance(payload, dict) else None
        err = payload.get("error") if isinstance(payload, dict) else None
        logger.info(
            "actress_fetch: done jp=%s request_id=%s ok=%s error=%s",
            jp,
            request_id,
            ok,
            err,
        )
        try:
            logger.info(
                "actress_fetch: response payload jp=%s request_id=%s\n%s",
                jp,
                request_id,
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            )
        except Exception as e:
            logger.warning(
                "actress_fetch: could not serialize payload for log jp=%s: %s",
                jp,
                e,
            )
        return payload
    except asyncio.TimeoutError:
        logger.warning(
            "actress_fetch: timeout jp=%s request_id=%s after_s=%s",
            jp,
            request_id,
            WORK_MERGE_TIMEOUT_SEC,
        )
        raise HTTPException(
            status_code=504,
            detail="actress fetch timed out waiting for browser extension",
        )
    finally:
        async with _actress_fetch_lock:
            _actress_fetch_futures.pop(request_id, None)
            _actress_fetch_names.pop(request_id, None)
        logger.debug("actress_fetch: future slot cleared request_id=%s", request_id)


@app.post("/api/v1/actress-fetch-result")
async def receive_actress_fetch_result(body: ActressFetchResultBody):
    """插件 minnano 采集完成后调用；不发射 bridge 信号。"""
    rid = (body.request_id or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="request_id required")

    async with _actress_fetch_lock:
        fut = _actress_fetch_futures.get(rid)
        name_fallback = _actress_fetch_names.get(rid, "")
    if fut is None:
        return {"status": "ignored", "reason": "unknown_or_finished_request"}
    if fut.done():
        return {"status": "ignored", "reason": "already_completed"}

    an = (body.actress_jp_name or "").strip() or name_fallback
    out: Dict[str, Any] = {
        "ok": body.ok,
        "actress_jp_name": an,
        "data": body.data,
    }
    if body.error:
        out["error"] = body.error
    fut.set_result(out)
    return {"status": "success"}


class CoverImageFetchRequest(BaseModel):
    url: str
    request_id: str
    allow_any_host: bool = False


class CoverImageFetchResult(BaseModel):
    request_id: str
    ok: bool
    error: Optional[str] = None
    content_base64: Optional[str] = None


def _allowed_dmm_cover_fetch_url(url: str) -> bool:
    try:
        p = urlparse(url.strip())
        if p.scheme not in ("http", "https"):
            return False
        h = (p.hostname or "").lower()
        return h == "dmm.co.jp" or h.endswith(".dmm.co.jp")
    except Exception:
        return False


def _allowed_any_http_cover_url(url: str) -> bool:
    """允许任意 http(s) 图片 URL（仅校验 scheme 与 netloc）。"""
    try:
        p = urlparse(url.strip())
        if p.scheme not in ("http", "https"):
            return False
        return bool(p.netloc)
    except Exception:
        return False


def _finish_cover_image_fetch(
    rid: str, temp_path: Optional[str], error: Optional[str] = None
) -> None:
    """插件回填完成后通知 Qt（与 ``coverBrowserFetchResult`` 订阅方一致）。"""
    err = (error or "").strip()
    bridge.coverBrowserFetchResult.emit(rid, temp_path, err)


@app.post("/api/v1/cover-image-fetch")
async def broadcast_cover_image_fetch(body: CoverImageFetchRequest):
    """通过 SSE 通知浏览器插件用 fetch 拉取 DMM 图片（走浏览器网络栈）。
    这个是给本地桌面软件使用的，通知浏览器插件去拉取图片
    """
    rid = (body.request_id or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="request_id required")
    if body.allow_any_host:
        if not _allowed_any_http_cover_url(body.url):
            raise HTTPException(status_code=400, detail="invalid url")
    elif not _allowed_dmm_cover_fetch_url(body.url):
        raise HTTPException(status_code=400, detail="url host not allowed")

    listener_count = len(sse_clients)
    if listener_count == 0:
        return {"status": "success", "listener_count": 0}

    dead_clients: List[asyncio.Queue] = []
    message = {
        "type": "fetch_cover_image",
        "url": body.url.strip(),
        "request_id": rid,
    }
    event_data = f"data: {json.dumps(message)}\n\n"
    for client in sse_clients:
        try:
            await client.put(event_data)
        except Exception:
            dead_clients.append(client)
    for dead in dead_clients:
        if dead in sse_clients:
            sse_clients.remove(dead)
    return {"status": "success", "listener_count": len(sse_clients)}


@app.post("/api/v1/cover-image-fetch-result")
async def receive_cover_image_fetch_result(body: CoverImageFetchResult):
    """接收插件回传的 base64 图片，写入临时目录并发信号给 Qt。
    这个是给浏览器插件用的，把下载的图片传到本地的临时目录
    """
    rid = (body.request_id or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="request_id required")

    if not body.ok:
        _finish_cover_image_fetch(rid, None, body.error or "失败")
        return {"status": "success"}

    b64 = (body.content_base64 or "").strip()
    if not b64:
        _finish_cover_image_fetch(rid, None, "无图片数据")
        return {"status": "success"}

    try:
        raw = base64.b64decode(b64, validate=True)
    except Exception as e:
        _finish_cover_image_fetch(rid, None, f"解码失败: {e}")
        return {"status": "success"}

    max_bytes = 30 * 1024 * 1024
    if len(raw) > max_bytes:
        _finish_cover_image_fetch(rid, None, "图片过大")
        return {"status": "success"}

    min_bytes = 5 * 1024
    if len(raw) < min_bytes:
        _finish_cover_image_fetch(rid, None, "图片过小（小于 5KB）")
        return {"status": "success"}

    TEMP_PATH.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(TEMP_PATH) / f"fanza_pl_browser_{ts}.jpg"
    try:
        out.write_bytes(raw)
    except OSError as e:
        _finish_cover_image_fetch(rid, None, f"写入失败: {e}")
        return {"status": "success"}

    _finish_cover_image_fetch(rid, str(out.resolve()), "")
    return {"status": "success"}


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
