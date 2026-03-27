from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QLineEdit,
    QComboBox,
)

import sqlite3
import logging

from config import DATABASE
from core.database.db_utils import attach_private_db, detach_private_db
from core.database.query import (
    get_actressname,
    get_unique_director,
    get_actorname,
    get_serial_number,
    get_maker_name,
    get_label_name,
    get_series_name,
    get_workid_by_serialnumber,
)
from ui.basic import HorizontalScrollArea
from ui.widgets import CompleterLineEdit
from core.dvd.DvdShelfView import DvdShelfView
from ui.widgets.selectors.TagSelector5 import TagSelector5
from darkeye_ui.components.label import Label
from darkeye_ui.components.rotate_button import RotateButton
from darkeye_ui.components.shake_button import ShakeButton
from darkeye_ui.components.input import LineEdit
from darkeye_ui.components.combo_box import ComboBox
from ui.widgets.selectors.maker_selector import MakerSelector
from ui.widgets.selectors.label_selector import LabelSelector
from ui.widgets.selectors.series_selector import SeriesSelector

class ShelfPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.keyword = None
        self.tag_ids = None
        self.actress = None
        self.director = None
        self.actor = None
        self.title = None
        self.serial_number = None
        self.maker_id = None
        self.label_id = None
        self.series_id = None
        self._green_mode = False
        self.order = "添加逆序"
        self.scope = "公共库范围"

        self._init_ui()
        self._signal_connect()

        self.filter_timer = QTimer(self)
        self.filter_timer.setSingleShot(True)
        self.filter_timer.timeout.connect(self.apply_filter_real)

        self.apply_filter_real()

    def _init_ui(self) -> None:
        scroll = HorizontalScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedHeight(32)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        filterwidget = QWidget()
        filterlayout = QHBoxLayout(filterwidget)
        filterlayout.setContentsMargins(0, 0, 0, 0)
        filterwidget.setFixedHeight(32)
        filterwidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        scroll.setWidget(filterwidget)
        scroll.setStyleSheet(
            """
    QScrollArea {
        border: none;
        background: transparent;
    }
    QScrollBar {
        background: transparent;
    }
"""
        )

        self.story_input = LineEdit()
        self.title_input = LineEdit()
        self.serial_number_input = CompleterLineEdit(get_serial_number)
        self.actress_input = CompleterLineEdit(get_actressname)
        self.director_input = CompleterLineEdit(get_unique_director)
        self.actor_input = CompleterLineEdit(get_actorname)
        self.maker_selector = MakerSelector(get_maker_name())
        self.label_selector = LabelSelector(get_label_name())
        self.series_selector = SeriesSelector(get_series_name())

        self.story_input.setFixedWidth(100)
        self.title_input.setFixedWidth(100)
        self.serial_number_input.setFixedWidth(150)
        self.actress_input.setFixedWidth(120)
        self.director_input.setFixedWidth(150)
        self.actor_input.setFixedWidth(120)
        self.maker_selector.setFixedWidth(160)
        self.label_selector.setFixedWidth(160)
        self.series_selector.setFixedWidth(160)

        filterlayout.addWidget(Label("番号："))
        filterlayout.addWidget(self.serial_number_input)
        filterlayout.addWidget(Label("女优"))
        filterlayout.addWidget(self.actress_input)
        filterlayout.addWidget(Label("标题包含："))
        filterlayout.addWidget(self.title_input)
        filterlayout.addWidget(Label("简单笔记包含："))
        filterlayout.addWidget(self.story_input)
        filterlayout.addWidget(Label("导演"))
        filterlayout.addWidget(self.director_input)
        filterlayout.addWidget(Label("男优"))
        filterlayout.addWidget(self.actor_input)
        filterlayout.addWidget(Label("片商"))
        filterlayout.addWidget(self.maker_selector)
        filterlayout.addWidget(Label("厂牌"))
        filterlayout.addWidget(self.label_selector)
        filterlayout.addWidget(Label("系列"))
        filterlayout.addWidget(self.series_selector)

        for i in range(filterlayout.count()):
            item = filterlayout.itemAt(i)
            w = item.widget()
            if w is not None:
                filterlayout.setAlignment(w, Qt.AlignmentFlag.AlignVCenter)

        self.info = Label()
        self.info.setFixedWidth(100)

        self.btn_reload = RotateButton(icon_name="refresh_cw",icon_size=24,out_size=24)
        self.btn_eraser = ShakeButton(icon_name="eraser",icon_size=24,out_size=24)

        self.order_combo = ComboBox()
        self.order_combo.addItems(
            [
                "添加逆序",
                "添加顺序",
                "番号顺序",
                "番号逆序",
                "制作商顺序",
                "制作商逆序",
                "更新时间顺序",
                "更新时间逆序",
                "发布时间逆序",
                "发布时间顺序",
                "拍摄年龄顺序",
                "拍摄年龄逆序",
            ]
        )
        self.order_combo.setCurrentText(self.order)

        self.scope_combo = ComboBox()
        self.scope_combo.addItems(["公共库范围", "收藏库范围", "收藏未观看", "已撸过"])
        self.scope_combo.setCurrentText(self.scope)

        self.filter_widget = QWidget()
        self.filter_widget.setFixedHeight(32)
        self.filter_layout = QHBoxLayout(self.filter_widget)
        self.filter_layout.setContentsMargins(10, 0, 10, 0)

        self.filter_layout.addWidget(scroll)
        self.filter_layout.addWidget(self.btn_reload)
        self.filter_layout.addWidget(self.btn_eraser)
        self.filter_layout.addWidget(self.info)
        self.filter_layout.addWidget(self.scope_combo)
        self.filter_layout.addWidget(self.order_combo)

        self.shelf_view = DvdShelfView(self)
        self.shelf_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.tagselector = TagSelector5()
        self.tagselector.left_view.setFixedWidth(84)
        self.tagselector.left_widget.setFixedWidth(108)

        self.hlayout = QHBoxLayout()
        self.hlayout.addWidget(self.tagselector, 0)
        self.hlayout.addWidget(self.shelf_view, 1)

        mainlayout = QVBoxLayout(self)
        mainlayout.setContentsMargins(0, 0, 0, 0)
        mainlayout.addWidget(self.filter_widget)
        mainlayout.addLayout(self.hlayout)

    def _signal_connect(self) -> None:
        self.btn_reload.clicked.connect(self.refresh)
        self.title_input.textChanged.connect(self.apply_filter)
        self.story_input.textChanged.connect(self.apply_filter)
        self.serial_number_input.textChanged.connect(self.apply_filter)
        self.actress_input.textChanged.connect(self.apply_filter)
        self.actor_input.textChanged.connect(self.apply_filter)
        self.director_input.textChanged.connect(self.apply_filter)
        self.maker_selector.currentTextChanged.connect(self.apply_filter)
        self.label_selector.currentTextChanged.connect(self.apply_filter)
        self.series_selector.currentTextChanged.connect(self.apply_filter)
        self.order_combo.currentTextChanged.connect(self.apply_filter)
        self.scope_combo.currentTextChanged.connect(self.apply_filter)
        self.tagselector.selection_changed.connect(self.apply_filter)

        from controller.GlobalSignalBus import global_signals

        global_signals.green_mode_changed.connect(self.update_green_mode)
        global_signals.work_data_changed.connect(self.reload_input)
        global_signals.actress_data_changed.connect(self.actress_input.reload_items)
        global_signals.actor_data_changed.connect(self.actor_input.reload_items)

        self.btn_eraser.clicked.connect(self._clear_all_search)

    def _clear_filters_for_jump(self) -> None:
        """Clear current shelf filters synchronously before programmatic jump."""
        self.filter_timer.stop()
        self.actor_input.setText("")
        self.actress_input.setText("")
        self.director_input.setText("")
        self.title_input.setText("")
        self.story_input.setText("")
        self.serial_number_input.setText("")
        self.maker_selector.set_maker(None)
        self.label_selector.set_label(None)
        self.series_selector.set_series_id(None)
        self.tagselector.load_with_ids([])
        self.scope_combo.setCurrentIndex(0)
        self.order_combo.setCurrentIndex(0)
        self.filter_timer.stop()
        self.apply_filter_real()

    def load_with_params(
        self,
        work_id=None,
        serial_number=None,
        director=None,
        maker_id=None,
        label_id=None,
        series_id=None,
        **kwargs,
    ):
        target_work_id = work_id
        if target_work_id is None and serial_number:
            try:
                target_work_id = get_workid_by_serialnumber(str(serial_number).strip())
            except Exception:
                logging.exception("ShelfPage: failed to resolve work_id from serial_number")
                return

        if target_work_id is not None:
            try:
                target_work_id = int(target_work_id)
            except (TypeError, ValueError):
                return

            self._clear_filters_for_jump()

            if self.shelf_view.loadworkid(target_work_id):
                return

            # Delay one event-loop tick so a freshly lazy-loaded page can finish applying its initial data.
            QTimer.singleShot(0, lambda wid=target_work_id: self.shelf_view.loadworkid(wid))
            return

        def _positive_id(v) -> int | None:
            if v is None:
                return None
            try:
                i = int(v)
                return i if i > 0 else None
            except (TypeError, ValueError):
                return None

        d = str(director).strip() if director is not None else ""
        mid = _positive_id(maker_id)
        lid = _positive_id(label_id)
        sid = _positive_id(series_id)
        if not d and mid is None and lid is None and sid is None:
            return

        self._clear_filters_for_jump()
        if d:
            self.director_input.setText(d)
        if mid is not None:
            self.maker_selector.set_maker(mid)
        if lid is not None:
            self.label_selector.set_label(lid)
        if sid is not None:
            self.series_selector.set_series_id(sid)
        self.apply_filter_real()

    @Slot()
    def _clear_all_search(self) -> None:
        self.actor_input.setText("")
        self.actress_input.setText("")
        self.director_input.setText("")
        self.title_input.setText("")
        self.story_input.setText("")
        self.serial_number_input.setText("")
        self.maker_selector.set_maker(None)
        self.label_selector.set_label(None)
        self.series_selector.set_series_id(None)
        self.tagselector.load_with_ids([])
        self.apply_filter()

    @Slot()
    def reload_input(self) -> None:
        self.serial_number_input.reload_items()
        self.director_input.reload_items()
        self.maker_selector.reload_makers()
        self.label_selector.reload_labels()
        self.series_selector.reload_series()

    @Slot(bool)
    def update_green_mode(self, green_mode: bool) -> None:
        self._green_mode = green_mode
        logging.debug(f"workpage的绿色模式{green_mode}")

    @Slot()
    def apply_filter(self) -> None:
        self.filter_timer.start(50)

    @Slot()
    def apply_filter_real(self) -> None:
        self.keyword = self.story_input.text().strip()
        self.actress = self.actress_input.text().strip()
        self.director = self.director_input.text().strip()
        self.actor = self.actor_input.text().strip()
        self.title = self.title_input.text().strip()
        self.serial_number = self.serial_number_input.text().strip()
        self.maker_id = self.maker_selector.get_maker()
        self.label_id = self.label_selector.get_label()
        self.series_id = self.series_selector.get_series_id()
        self.tag_ids = self.tagselector.get_selected_ids()
        self.scope = self.scope_combo.currentText()
        self.order = self.order_combo.currentText()

        count = self._reload_work_ids()
        self.update_info(count)

    def update_info(self, count: int) -> None:
        if count == 0:
            self.info.setText("没有查询到数据")
        else:
            self.info.setText("过滤总数:" + str(count))

    def _reload_work_ids(self) -> int:
        work_ids = self._query_work_ids()
        self.shelf_view.set_work_ids(work_ids)
        return len(work_ids)

    def _query_work_ids(self) -> list[int]:
        params: list = []
        query = """
SELECT 
    work.work_id
FROM work
        """
        cte_parts = []

        if self.actress:
            withsql = """
filtered_actresses AS (
SELECT 
    DISTINCT actress_id
FROM 
    actress_name
WHERE cn LIKE ? OR jp LIKE ?
)
"""
            cte_parts.append(withsql)
            params.extend([f"%{self.actress}%", f"%{self.actress}%"])

        if self.actor:
            withsql = """
filtered_actors AS (
SELECT 
    DISTINCT actor_id
FROM 
    actor_name
WHERE cn LIKE ? OR jp LIKE ?
)
"""
            cte_parts.append(withsql)
            params.extend([f"%{self.actor}%", f"%{self.actor}%"])

        cte_sql = ""
        if cte_parts:
            cte_sql = "WITH " + ",\n".join(cte_parts) + "\n"

        query = cte_sql + query

        if self.scope == "收藏库范围" or self.scope == "收藏未观看":
            query += "JOIN priv.favorite_work fav ON fav.work_id=work.work_id\n"

        if self.scope == "已撸过":
            query += "JOIN priv.masturbation  ON priv.masturbation.work_id=work.work_id\n"

        if self.order == "拍摄年龄顺序" or self.order == "拍摄年龄逆序":
            query += "JOIN v_work_avg_age_info v ON work.work_id = v.work_id\n"

        if self.actress:
            query += """
JOIN work_actress_relation ON work_actress_relation.work_id=work.work_id
JOIN actress ON actress.actress_id=work_actress_relation.actress_id
JOIN filtered_actresses f ON actress.actress_id = f.actress_id
"""
        if self.actor:
            query += """
JOIN work_actor_relation ON work_actor_relation.work_id=work.work_id
JOIN filtered_actors fa ON fa.actor_id = work_actor_relation.actor_id
"""

        if self.tag_ids:
            placeholders = ",".join("?" for _ in self.tag_ids)
            query += f"LEFT JOIN work_tag_relation wtr2 ON work.work_id =wtr2.work_id AND wtr2.tag_id IN ({placeholders})\n"
            params.extend(self.tag_ids)

        query += "WHERE is_deleted=0\n"

        if self.keyword:
            query += "AND work.notes LIKE ?\n"
            params.append(f"%{self.keyword}%")

        if self.order == "拍摄年龄顺序" or self.order == "拍摄年龄逆序":
            query += "AND v.avg_age IS NOT NULL\n"

        if self.order == "发布时间顺序" or self.order == "发布时间逆序":
            query += "AND work.release_date IS NOT NULL AND work.release_date!=''\n"

        if self.director:
            query += "AND work.director LIKE ?\n"
            params.append(f"%{self.director}%")

        if self.serial_number:
            query += "AND work.serial_number LIKE ?\n"
            params.append(f"%{self.serial_number}%")

        if self.maker_id is not None:
            query += "AND work.maker_id = ?\n"
            params.append(self.maker_id)

        if self.title:
            query += "AND work.cn_title LIKE ?\n"
            params.append(f"%{self.title}%")

        if self.label_id:
            query += "AND work.label_id = ?\n"
            params.append(self.label_id)

        if self.series_id:
            query += "AND work.series_id = ?\n"
            params.append(self.series_id)

        if self.scope == "收藏未观看":
            query += "AND work.work_id NOT IN (SELECT work_id FROM priv.masturbation WHERE work_id IS NOT NULL)\n"

        if self.tag_ids:
            num_tags = len(self.tag_ids)
            query += """
GROUP BY work.work_id
HAVING COUNT(DISTINCT wtr2.tag_id) = ?
            """
            params.append(num_tags)

        match self.order:
            case "发布时间顺序":
                order = "ORDER BY work.release_date\n"
            case "发布时间逆序":
                order = "ORDER BY work.release_date DESC\n"
            case "拍摄年龄顺序":
                order = "ORDER BY (SELECT avg_age FROM v_work_avg_age_info WHERE work_id=work.work_id)\n"
            case "拍摄年龄逆序":
                order = "ORDER BY (SELECT avg_age FROM v_work_avg_age_info WHERE work_id=work.work_id) DESC\n"
            case "添加逆序":
                order = "ORDER BY work.create_time DESC\n"
            case "添加顺序":
                order = "ORDER BY work.create_time\n"
            case "番号顺序":
                order = "ORDER BY work.serial_number\n"
            case "番号逆序":
                order = "ORDER BY work.serial_number DESC\n"
            case "制作商顺序":
                order = "ORDER BY work.maker_id IS NULL, work.maker_id, work.serial_number\n"
            case "制作商逆序":
                order = "ORDER BY work.maker_id IS NULL DESC, work.maker_id DESC, work.serial_number DESC\n"
            case "更新时间逆序":
                order = "ORDER BY work.update_time DESC\n"
            case "更新时间顺序":
                order = "ORDER BY work.update_time\n"
            case _:
                order = "ORDER BY work.create_time DESC\n"

        query += order

        with sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True) as conn:
            cursor = conn.cursor()
            if (
                self.scope == "收藏库范围"
                or self.scope == "收藏未观看"
                or self.scope == "已撸过"
            ):
                attach_private_db(cursor)
            cursor.execute(query, params)
            results = cursor.fetchall()
            if (
                self.scope == "收藏库范围"
                or self.scope == "收藏未观看"
                or self.scope == "已撸过"
            ):
                detach_private_db(cursor)

        return [row[0] for row in results]

    @Slot()
    def refresh(self) -> None:
        self.apply_filter_real()
