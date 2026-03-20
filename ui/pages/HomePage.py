from PySide6.QtWidgets import QWidget, QSizePolicy, QVBoxLayout

from PySide6.QtCore import Slot
import sqlite3
import logging

from config import DATABASE
from controller.GlobalSignalBus import global_signals
from core.database.db_utils import attach_private_db, detach_private_db
from core.dvd.DvdShelfView import DvdShelfView


class HomePage(QWidget):
    def __init__(self):
        super().__init__()
        # 这个暂时没有用，因为这个 Page 就是直接一个自定义控件，
        # 见 widgets/CoverBrowser.py
        self.shelf_view = DvdShelfView(self)
        self.shelf_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        mainlayout = QVBoxLayout(self)
        mainlayout.setContentsMargins(0, 0, 0, 0)
        mainlayout.addWidget(self.shelf_view)

        # 首页：加载收藏作品的 work_id 列表
        work_ids = self._load_favorite_work_ids()
        if work_ids:
            self.shelf_view.set_work_ids(work_ids)
        else:
            logging.info("HomePage: 收藏列表为空，DVD 书架不加载任何作品。")

        # 监听全局作品数据变更信号，自动刷新首页收藏书架
        global_signals.work_data_changed.connect(self._refresh_favorites)
        global_signals.like_work_changed.connect(self._refresh_favorites)

    def _load_favorite_work_ids(self) -> list[int]:
        """从公库 + 私库加载按片商前缀排序后的收藏作品 work_id 列表。"""
        sql = """
        SELECT
            work.work_id
        FROM work
        LEFT JOIN prefix_maker_relation p
            ON p.prefix = SUBSTR(work.serial_number, 1, INSTR(work.serial_number, '-') - 1)
        JOIN priv.favorite_work fav
            ON fav.work_id = work.work_id
        WHERE work.is_deleted = 0
        ORDER BY p.maker_id IS NULL, p.maker_id, work.serial_number
        """
        try:
            with sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True) as conn:
                cursor = conn.cursor()
                attach_private_db(cursor)
                cursor.execute(sql)
                rows = cursor.fetchall()
                detach_private_db(cursor)
        except Exception as e:
            logging.error(f"HomePage: 加载收藏作品失败: {e}")
            return []

        return [int(row[0]) for row in rows if row and row[0] is not None]

    @Slot()
    def _refresh_favorites(self) -> None:
        """作品数据变更后，重新加载收藏作品并刷新书架视图。"""
        work_ids = self._load_favorite_work_ids()
        if work_ids:
            self.shelf_view.set_work_ids(work_ids)
        else:
            logging.info("HomePage: 收藏列表为空，清空 DVD 书架显示。")
            self.shelf_view.set_work_ids([])