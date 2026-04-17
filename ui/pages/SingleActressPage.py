# 个人女优详细的面板

import logging
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout

from config import DATABASE
from core.database.db_queue import submit_db_raw
from darkeye_ui import LazyWidget
from ui.widgets import SingleActressInfo
from ui.widgets.ActressWorkTimeline import ActressWorkTimeline


def load_timeline_rows(actress_id: int) -> list[tuple]:
    """按女优拉取全部关联作品（含 release_date），供时间轴使用。"""
    query = """
SELECT
    work.serial_number,
    cn_title,
    image_url,
    wtr.tag_id,
    work.work_id,
    CASE
        WHEN (SELECT cn_name FROM maker WHERE maker_id = p.maker_id) IS NULL
        THEN 0
        ELSE 1
    END AS standard,
    work.release_date
FROM work
JOIN work_actress_relation war ON war.work_id = work.work_id
LEFT JOIN work_tag_relation wtr
    ON work.work_id = wtr.work_id AND wtr.tag_id IN (1, 2, 3)
LEFT JOIN prefix_maker_relation p
    ON p.prefix = SUBSTR(work.serial_number, 1, INSTR(work.serial_number, '-') - 1)
WHERE war.actress_id = ?
ORDER BY work.release_date DESC"""

    def _run_read() -> list[tuple]:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (actress_id,))
            return cursor.fetchall()

    return submit_db_raw(_run_read).result()


class SingleActressPage(LazyWidget):
    def __init__(self):
        super().__init__()

    def _lazy_load(self):
        logging.info("----------加载单独女优界面----------")
        self._actress_id = None
        self.actress = True
        self.order = "按发布时间顺序"
        self.scope = "全库"

        self.single_actress_info = SingleActressInfo()
        self.single_actress_info.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred
        )

        self.works_timeline = ActressWorkTimeline()
        self.works_timeline.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        mainlayout = QVBoxLayout(self)
        mainlayout.setContentsMargins(0, 0, 0, 0)
        info_row = QHBoxLayout()
        info_row.setContentsMargins(0, 0, 0, 0)
        info_row.setSpacing(0)
        info_row.addStretch(1)
        info_row.addWidget(
            self.single_actress_info,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        info_row.addStretch(1)
        mainlayout.addLayout(info_row)
        mainlayout.addWidget(self.works_timeline, 1)

    def update(self, actress_id):
        self.single_actress_info.update(actress_id)
        self._actress_id = actress_id
        rows = load_timeline_rows(actress_id)
        self.works_timeline.set_work_rows(rows)
