from __future__ import annotations

from enum import Enum
from typing import Dict, Set


class CrawlWorkflowState(str, Enum):
    """作品爬取在内存中的工作流阶段。"""

    QUEUED = "queued"
    CRAWLING = "crawling"
    MERGING = "merging"
    PERSISTING = "persisting"


class CrawlerTask:
    def __init__(
        self,
        serial_number,
        sources=("javlib", "javdb", "fanza", "javtxt", "avdanyuwiki"),
        withGUI=False,
        selected_fields: set[str] | None = None,
    ):
        self.serial: str = serial_number
        self.pending_sources: set[str] = set(sources)
        self.results: Dict[str, dict] = {}
        self.withGUI = withGUI
        self.selected_fields: set[str] | None = set(selected_fields) if selected_fields else None
        self.workflow_state: CrawlWorkflowState = CrawlWorkflowState.CRAWLING
        self.cancel_requested: bool = False
