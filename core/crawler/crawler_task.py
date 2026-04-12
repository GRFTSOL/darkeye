from __future__ import annotations

from enum import Enum


class CrawlWorkflowState(str, Enum):
    """作品爬取在内存中的工作流阶段。"""

    QUEUED = "queued"
    CRAWLING = "crawling"
    PERSISTING = "persisting"


class CrawlerTask:
    def __init__(
        self,
        serial_number: str,
        withGUI: bool = False,
        selected_fields: set[str] | None = None,
    ):
        self.serial: str = serial_number
        self.withGUI = withGUI
        self.selected_fields: set[str] | None = (
            set(selected_fields) if selected_fields else None
        )
        self.workflow_state: CrawlWorkflowState = CrawlWorkflowState.CRAWLING
        self.cancel_requested: bool = False
