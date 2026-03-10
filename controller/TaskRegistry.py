"""
TaskRegistry - 统一任务管理层（仅展示、不操控）

供执行器注册任务、更新进度、完成/失败；展示层订阅信号并调用 get_task/list_tasks 更新 UI。
不依赖任何 UI 组件；建议在主线程调用 register/update_progress/complete/error。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, Signal


@dataclass
class TaskProgress:
    """进度信息：current/total（0 表示未知）、message"""
    current: int = 0
    total: int = 0
    message: str = ""


@dataclass
class Task:
    """任务视图数据，用于 Registry 内部存储与 get/list 返回"""
    task_id: str
    title: str
    executor_type: str
    status: str  # pending | running | success | error
    progress: TaskProgress
    start_time: datetime
    end_time: Optional[datetime] = None
    end_message: str = ""


class TaskRegistry(QObject):
    """
    统一任务管理层单例。
    负责任务注册、进度更新、完成/失败、查询；发出信号供展示层订阅。
    不实现取消、重试；建议主线程调用。
    """

    task_added = Signal(str)  # task_id
    task_progress_updated = Signal(str)  # task_id
    task_finished = Signal(str, bool, str)  # task_id, success, message

    _instance: Optional[TaskRegistry] = None

    def __new__(cls) -> TaskRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized") and self._initialized:
            return
        super().__init__()
        self._initialized = True
        self._tasks: dict[str, Task] = {}

    @classmethod
    def instance(cls) -> TaskRegistry:
        """获取单例，无参数，不依赖 UI。"""
        if cls._instance is None:
            cls._instance = TaskRegistry()
        return cls._instance

    def register(
        self,
        task_id: Optional[str] = None,
        title: str = "",
        executor_type: str = "generic",
    ) -> str:
        """
        注册新任务。若未传 task_id 则生成唯一 id。
        创建 Task（status=running），写入 _tasks，发出 task_added，返回 task_id。
        """
        if task_id is None or task_id == "":
            task_id = f"generic_{uuid.uuid4().hex[:8]}"
        if task_id in self._tasks:
            return task_id

        now = datetime.now()
        task = Task(
            task_id=task_id,
            title=title,
            executor_type=executor_type,
            status="running",
            progress=TaskProgress(0, 0, "正在处理..."),
            start_time=now,
            end_time=None,
            end_message="",
        )
        self._tasks[task_id] = task
        self.task_added.emit(task_id)
        return task_id

    def update_progress(
        self,
        task_id: str,
        current: int,
        total: int,
        message: str = "",
    ) -> None:
        """若存在该任务则更新 progress 和 status=running，发出 task_progress_updated。"""
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.status = "running"
        task.progress = TaskProgress(current=current, total=total, message=message)
        self.task_progress_updated.emit(task_id)

    def complete(self, task_id: str, message: str = "完成") -> None:
        """若存在则设 status=success、end_time、end_message，发出 task_finished。"""
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.status = "success"
        task.end_time = datetime.now()
        task.end_message = message
        self.task_finished.emit(task_id, True, message)

    def error(self, task_id: str, message: str = "失败") -> None:
        """若存在则设 status=error、end_time、end_message，发出 task_finished。"""
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.status = "error"
        task.end_time = datetime.now()
        task.end_message = message
        self.task_finished.emit(task_id, False, message)

    def get_task(self, task_id: str) -> Optional[Task]:
        """返回内部 Task，供 UI 生成列表项文案。"""
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        """返回当前所有任务，按 start_time 倒序（新任务在前）。"""
        tasks = list(self._tasks.values())
        tasks.sort(key=lambda t: t.start_time, reverse=True)
        return tasks

    def unread_count(self) -> int:
        """status 为 running 或 error 的数量，便于状态栏角标。"""
        return sum(
            1 for t in self._tasks.values()
            if t.status in ("running", "error")
        )
