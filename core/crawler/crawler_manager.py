import logging
import random
import threading
from collections import deque
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests
from PySide6.QtCore import QObject, QThreadPool, QTimer, Qt, Signal, Slot

from controller.global_signal_bus import global_signals
from core.crawler.crawler_task import CrawlerTask, CrawlWorkflowState
from core.crawler.sequential_download import SequentialDownloader
from core.crawler.work_persistence import schedule_data_update
from core.schema.model import CrawledWorkData

# 与 server.app WORK_MERGE_TIMEOUT_SEC + 余量一致（manual_tests 使用 130s）
_WORK_API_BASE = "http://127.0.0.1:56789"
_WORK_API_TIMEOUT_SEC = 130.0


def crawled_work_from_extension_payload(data: dict[str, Any]) -> CrawledWorkData:
    """将插件 ``GET /api/v1/work`` 返回的 ``data`` 映射为 ``CrawledWorkData``（无翻译）。

    多源桌面合并逻辑见 ``tests/support/merge_crawl_legacy.py``（仅单测回归）。
    """
    if not isinstance(data, dict):
        raise TypeError("extension payload must be a dict")
    sn = str(data.get("serial_number") or "").strip()
    try:
        rt = int(data.get("runtime")) if data.get("runtime") not in (None, "") else 0
    except (ValueError, TypeError):
        rt = 0
    tag = data.get("tag_list")
    if not isinstance(tag, list):
        tag = []
    al = data.get("actress_list")
    if not isinstance(al, list):
        al = []
    acl = data.get("actor_list")
    if not isinstance(acl, list):
        acl = []
    cov = data.get("cover_url_list")
    if not isinstance(cov, list):
        cov = []
    fan = data.get("fanart_url_list")
    if not isinstance(fan, list):
        fan = []
    return CrawledWorkData(
        serial_number=sn,
        director=str(data.get("director") or ""),
        release_date=str(data.get("release_date") or ""),
        runtime=rt,
        cn_title=str(data.get("cn_title") or ""),
        jp_title=str(data.get("jp_title") or ""),
        cn_story=str(data.get("cn_story") or ""),
        jp_story=str(data.get("jp_story") or ""),
        tag_list=[str(x) for x in tag if x is not None],
        actress_list=[str(x) for x in al if x is not None],
        actor_list=[str(x) for x in acl if x is not None],
        cover_url_list=[str(x).strip() for x in cov if x],
        maker=str(data.get("maker") or ""),
        series=str(data.get("series") or ""),
        label=str(data.get("label") or ""),
        fanart_url_list=[
            str(x).strip() for x in fan if isinstance(x, str) and str(x).strip()
        ],
    )


class _WorkApiSignals(QObject):
    """后台线程完成 GET /api/v1/work 后向主线程投递结果。"""

    finished = Signal(
        str, object, object
    )  # serial, payload dict | None, err str | None


class CrawlerManager2(QObject):
    """番号爬虫调度：队列、本地 work API 拉取、封面下载与未完成状态持久化。"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        """单例：全进程共用一个 ``CrawlerManager2`` 实例。"""
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        """初始化队列、定时器、线程池及与 bridge / 全局信号的连接；从 ini 恢复未完成番号。"""
        super().__init__()
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self.tasks: Dict[str, CrawlerTask] = {}
            self._download_relays: Dict[int, QObject] = {}

            self._unfinished_serials: set[str] = set()
            self._persist_key_unfinished = "Inbox/UnfinishedSerials"

            self._crawl_terminated: bool = False
            self._work_fetch_busy: bool = False

            self._work_api_signals = _WorkApiSignals(self)
            self._work_api_signals.finished.connect(
                self._on_work_api_finished,
                Qt.ConnectionType.QueuedConnection,
            )

            self._download_pool = QThreadPool(self)
            self._download_pool.setObjectName("CoverDownloadPool")
            self._download_pool.setMaxThreadCount(4)

            self._persist_pool = QThreadPool(self)
            self._persist_pool.setObjectName("WorkPersistPool")
            self._persist_pool.setMaxThreadCount(2)

            self.request_queue = deque()
            self.schedule_timer = QTimer(self)
            self.schedule_timer.setSingleShot(True)
            self.schedule_timer.timeout.connect(self._on_schedule_tick)
            self.last_schedule_time = 0

            from server.bridge import bridge

            bridge.captureOneReceived.connect(
                lambda serial_number: self.start_crawl([serial_number]),
                Qt.ConnectionType.QueuedConnection,
            )

            global_signals.downloadTaskFinished.connect(
                self._on_download_task_finished,
                Qt.ConnectionType.QueuedConnection,
            )

            self._restore_unfinished_from_ini()

    def inbox_snapshot(self) -> tuple[set[str], set[str]]:
        """只读：待爬队列番号集合、元数据爬取中任务番号集合。"""
        return ({item[0] for item in self.request_queue}, set(self.tasks.keys()))

    def get_serial_workflow_state(self, serial: str) -> CrawlWorkflowState | None:
        """只读：某番号当前工作流阶段；不在队列且不在 tasks 则返回 None。"""
        serial = self._norm_serial(serial)
        if not serial:
            return None
        if any(item[0] == serial for item in self.request_queue):
            return CrawlWorkflowState.QUEUED
        task = self.tasks.get(serial)
        return task.workflow_state if task else None

    def request_cancel_running(self, serial: str) -> bool:
        """标记运行中任务在请求返回后跳过入库（不中断已发出的 HTTP）。"""
        serial = self._norm_serial(serial)
        task = self.tasks.get(serial)
        if not task or task.serial != serial:
            return False
        task.cancel_requested = True
        return True

    def start_crawl(
        self, serial_numbers, withGUI=False, selected_fields: set[str] | None = None
    ):
        """将番号加入 ``request_queue``，并视情况启动调度定时器。

        ``serial_numbers`` 可为单个 str 或可迭代；经 ``_norm_serial`` 规范化，空串丢弃。
        ``withGUI``、``selected_fields`` 原样写入队列元组，供后续拉取插件数据时使用；
        ``selected_fields`` 为 ``None`` 或省略表示全字段。

        若此前调用过 ``terminate_crawl``，会先 ``resume_crawl`` 再继续入队。
        仅与入队前已有的 ``request_queue`` 去重；同一次调用里 ``serial_numbers``
        若含重复番号仍可能重复入队（不含已在 ``tasks`` 中运行的番号）。
        每个新入队番号会加入 ``_unfinished_serials`` 并持久化到 ini（收件箱等可恢复）。
        方法末尾若队列非空且调度器空闲，按最小间隔触发 ``_schedule_next``。
        """
        # 终止状态下调度被关掉，先入队前需恢复，否则任务永远不会被弹出
        if getattr(self, "_crawl_terminated", False):
            logging.info("检测到爬虫调度器处于终止状态：自动恢复后继续 start_crawl")
            self.resume_crawl()
        if isinstance(serial_numbers, str):
            serial_numbers = [serial_numbers]

        # 只与「尚未开始爬」的排队项去重；正在 tasks 里的由其它路径处理
        existing_serials = {item[0] for item in self.request_queue}

        for serial_number in serial_numbers:
            serial_number = self._norm_serial(serial_number)
            if not serial_number:
                continue
            if serial_number in existing_serials:
                logging.info("任务 %s 已在队列中，跳过重复添加", serial_number)
                continue
            # (番号, 是否 GUI, 字段子集或 None)
            self.request_queue.append(
                (
                    serial_number,
                    withGUI,
                    set(selected_fields) if selected_fields else None,
                )
            )
            logging.info(
                "任务 %s 已入队，当前队列长度: %s",
                serial_number,
                len(self.request_queue),
            )

            self._unfinished_serials.add(serial_number)
            self._persist_unfinished_to_ini()

        if not self.schedule_timer.isActive() and self.request_queue:
            import time

            now = time.time() * 1000
            elapsed = now - self.last_schedule_time
            min_interval = 12000

            if elapsed < min_interval:
                delay = int(min_interval - elapsed)
                self._schedule_next(delay)
            else:
                self._schedule_next(0)

    def terminate_crawl(self, *, clear_queue: bool = True):
        """停止调度定时器并标记终止态；可选清空待爬队列并从未完成集合中移除被丢弃番号。

        已在执行的 HTTP / 持久化后台任务不会被强行中断。
        """
        self._crawl_terminated = True

        if self.schedule_timer.isActive():
            self.schedule_timer.stop()

        if clear_queue:
            dropped = len(self.request_queue)
            dropped_serials = {item[0] for item in self.request_queue}
            self.request_queue.clear()
            logging.info(
                "爬虫调度器已终止：已丢弃未开始任务 %s 个；正在运行的任务将继续执行",
                dropped,
            )
            if dropped_serials:
                self._unfinished_serials.difference_update(dropped_serials)
                self._persist_unfinished_to_ini()
        else:
            logging.info("爬虫调度器已终止：未清空队列（但也不会再调度）")

    def is_crawl_terminated(self) -> bool:
        """是否处于 ``terminate_crawl`` 后的终止态（不再调度新任务）。"""
        return bool(getattr(self, "_crawl_terminated", False))

    def resume_crawl(self):
        """清除终止标记；若队列非空则按最小间隔重新安排调度。"""
        self._crawl_terminated = False

        if self.request_queue and not self.schedule_timer.isActive():
            import time

            now = time.time() * 1000
            elapsed = now - self.last_schedule_time
            min_interval = 12000
            delay = int(min_interval - elapsed) if elapsed < min_interval else 0
            self._schedule_next(delay)

    def drop_pending(self, serial: str) -> bool:
        """从 ``request_queue`` 移除该番号的第一条待处理项，并同步未完成集合与 ini。

        若番号不在队列中返回 ``False``；不处理已在 ``tasks`` 中运行的任务。
        """
        serial = self._norm_serial(serial)
        if not serial:
            return False

        removed_from_queue = False
        new_q = deque()
        while self.request_queue:
            s, withGUI, selected_fields = self.request_queue.popleft()
            if s == serial and not removed_from_queue:
                removed_from_queue = True
                continue
            new_q.append((s, withGUI, selected_fields))
        self.request_queue = new_q

        if serial in self._unfinished_serials:
            self._unfinished_serials.discard(serial)
        self._persist_unfinished_to_ini()

        return removed_from_queue

    def _norm_serial(self, serial: str) -> str:
        """番号规范化：``None`` 与仅空白视为空串。"""
        if serial is None:
            return ""
        return str(serial).strip()

    def _load_unfinished_from_ini(self) -> list[str]:
        """从 ``settings`` 读取逗号分隔的未完成番号列表，去重且保序。"""
        from config import settings

        raw = settings.value(self._persist_key_unfinished, "", type=str)
        if not raw:
            return []
        parts = [p.strip() for p in str(raw).split(",") if p and str(p).strip()]
        seen: set[str] = set()
        out: list[str] = []
        for p in parts:
            if p in seen:
                continue
            seen.add(p)
            out.append(p)
        return out

    def _persist_unfinished_to_ini(self) -> None:
        """将 ``_unfinished_serials`` 排序后写回 ``settings``（逗号分隔）。"""
        from config import settings

        serials = sorted(self._unfinished_serials)
        settings.setValue(self._persist_key_unfinished, ",".join(serials))

    def _restore_unfinished_from_ini(self) -> None:
        """启动时把 ini 中的未完成番号填回队列，并置为终止态（需用户恢复调度）。"""
        serials = self._load_unfinished_from_ini()
        if not serials:
            return

        self._crawl_terminated = True

        existing = {item[0] for item in self.request_queue}
        restored = 0
        for s in serials:
            s = self._norm_serial(s)
            if not s or s in existing:
                continue
            self.request_queue.append((s, False, None))
            self._unfinished_serials.add(s)
            restored += 1

        if restored:
            logging.info(
                "已从 settings.ini 恢复未完成任务 %s 个到队列（默认暂停调度）",
                restored,
            )
            self._persist_unfinished_to_ini()

    @Slot(str, bool, str)
    def _on_download_task_finished(self, serial: str, success: bool, msg: str) -> None:
        """封面串行下载结束：从未完成集合移除该番号并删除对应 ``tasks`` 条目。

        ``success`` / ``msg`` 由下载链路传入，此处仅做收尾。
        """
        serial = self._norm_serial(serial)
        if not serial:
            return
        if serial in self._unfinished_serials:
            self._unfinished_serials.discard(serial)
            self._persist_unfinished_to_ini()
        if serial in self.tasks:
            del self.tasks[serial]

    def _schedule_next(self, delay=None):
        """启动单次 ``schedule_timer``；终止态不调度。``delay`` 为毫秒，省略时随机 12–18s。"""
        if getattr(self, "_crawl_terminated", False):
            logging.info("爬虫调度器已终止：跳过 _schedule_next")
            return
        if delay is None:
            delay = random.randint(12000, 18000)
        self.schedule_timer.start(delay)
        logging.info("调度器将在 %.1f 秒后执行下一个任务", delay / 1000)

    def _on_schedule_tick(self):
        """定时器到期：若队列非空且当前无 work API 在途，弹出队首并发起拉取。"""
        if getattr(self, "_crawl_terminated", False):
            logging.info("爬虫调度器已终止：停止后续调度")
            return
        if not self.request_queue:
            logging.info("队列为空，调度器停止")
            return
        if self._work_fetch_busy:
            self._schedule_next(1000)
            return

        import time

        self.last_schedule_time = time.time() * 1000

        serial, withGUI, selected_fields = self.request_queue.popleft()
        self._execute_work_api_fetch(serial, withGUI, selected_fields)

    def _work_api_url(self, serial: str) -> str:
        """本地服务 ``GET /api/v1/work/{serial}`` 的完整 URL（番号经 ``quote``）。"""
        return f"{_WORK_API_BASE}/api/v1/work/{quote(serial, safe='')}"

    def _execute_work_api_fetch(
        self,
        serial_number: str,
        withGUI: bool = False,
        selected_fields: set[str] | None = None,
    ) -> None:
        """在后台线程请求 work API，结果经 ``_WorkApiSignals.finished`` 回主线程。

        主线程侧置 ``_work_fetch_busy`` 并登记 ``CrawlerTask``；空番号直接走收尾。
        """
        serial_number = self._norm_serial(serial_number)
        if not serial_number:
            self._after_work_api_cycle()
            return

        self._work_fetch_busy = True
        task = CrawlerTask(serial_number, withGUI, selected_fields)
        self.tasks[serial_number] = task

        url = self._work_api_url(serial_number)
        sig = self._work_api_signals

        def run() -> None:
            """子线程：GET work API，成功则 ``finished.emit(serial, body, None)``，否则带错误串。"""
            try:
                r = requests.get(url, timeout=_WORK_API_TIMEOUT_SEC)
                if r.status_code != 200:
                    tail = (r.text or "")[:400]
                    sig.finished.emit(
                        serial_number,
                        None,
                        f"HTTP {r.status_code} {tail}",
                    )
                    return
                try:
                    body = r.json()
                except Exception as e:
                    sig.finished.emit(serial_number, None, f"invalid JSON: {e}")
                    return
                if not isinstance(body, dict):
                    sig.finished.emit(serial_number, None, "response is not an object")
                    return
                sig.finished.emit(serial_number, body, None)
            except Exception as e:
                sig.finished.emit(serial_number, None, str(e))

        threading.Thread(target=run, daemon=True).start()

    @Slot(str, object, object)
    def _on_work_api_finished(
        self, serial: str, payload: object, err: Optional[str]
    ) -> None:
        """处理 work API 响应：错误/取消则清理任务；成功则解析并 ``schedule_data_update``。"""
        self._work_fetch_busy = False
        serial = self._norm_serial(serial)
        if not serial:
            self._after_work_api_cycle()
            return

        task = self.tasks.get(serial)
        if task and task.cancel_requested:
            if serial in self.tasks:
                del self.tasks[serial]
            logging.info("任务 %s 已取消，跳过入库", serial)
            self._after_work_api_cycle()
            return

        if err:
            logging.error("work API 失败 serial=%s: %s", serial, err)
            if serial in self.tasks:
                del self.tasks[serial]
            self._after_work_api_cycle()
            return

        if not isinstance(payload, dict):
            logging.error("work API 无效 payload serial=%s", serial)
            if serial in self.tasks:
                del self.tasks[serial]
            self._after_work_api_cycle()
            return

        if not payload.get("ok"):
            logging.warning(
                "work API ok=false serial=%s error=%s",
                serial,
                payload.get("error"),
            )
            if serial in self.tasks:
                del self.tasks[serial]
            self._after_work_api_cycle()
            return

        data = payload.get("data")
        if not isinstance(data, dict) or not data:
            logging.warning("work API 缺少 data serial=%s", serial)
            if serial in self.tasks:
                del self.tasks[serial]
            self._after_work_api_cycle()
            return

        task = self.tasks.get(serial)
        if not task or task.cancel_requested:
            if serial in self.tasks:
                del self.tasks[serial]
            self._after_work_api_cycle()
            return

        try:
            merged = crawled_work_from_extension_payload(data)
        except Exception as e:
            logging.error("解析 extension data 失败 serial=%s: %s", serial, e)
            if serial in self.tasks:
                del self.tasks[serial]
            self._after_work_api_cycle()
            return

        task.workflow_state = CrawlWorkflowState.PERSISTING
        schedule_data_update(
            self,
            merged,
            withGUI=task.withGUI,
            selected_fields=task.selected_fields,
        )
        self._after_work_api_cycle()

    def _after_work_api_cycle(self) -> None:
        """单次拉取链路结束：未终止且队列仍有项则继续调度，否则打日志停止。"""
        if getattr(self, "_crawl_terminated", False):
            return
        if self.request_queue:
            self._schedule_next()
        else:
            logging.info("队列已空，停止后续调度")


_crawler_manager2: Optional["CrawlerManager2"] = None


def get_manager() -> "CrawlerManager2":
    """返回进程内单例 ``CrawlerManager2``；首次须在持有 QApplication 的主线程调用。"""
    global _crawler_manager2
    if _crawler_manager2 is None:
        from PySide6.QtCore import QCoreApplication, QThread

        app = QCoreApplication.instance()
        if app is not None and QThread.currentThread() != app.thread():
            raise RuntimeError(
                "CrawlerManager2 必须在主线程首次初始化（请在 MainWindow show 后调用 get_manager()）"
            )

        _crawler_manager2 = CrawlerManager2()
    return _crawler_manager2
