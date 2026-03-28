from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QMessageBox, QFileDialog
from PySide6.QtCore import Slot
import logging

from config import DATABASE
from ui.basic import ModelSearch
from ui.base.SqliteQueryTableModel import SqliteQueryTableModel
from darkeye_ui import LazyWidget
from darkeye_ui.components.token_table_view import TokenTableView
from darkeye_ui.components.button import Button
from darkeye_ui.components.input import LineEdit
from darkeye_ui.components.combo_box import ComboBox


class SearchTable(LazyWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

    def _lazy_load(self):
        logging.info("----------汇总查询页面----------")
        self.init_ui()

        self.signal_connect()

        self.config()

    def config(self):
        """配置 model 与 view"""
        self.query_sql = """
        WITH actress_age_at_release AS (--计算每个女优发布作品的年龄
  SELECT
    w.work_id,
    a.actress_id,
    w.serial_number,
    w.release_date,
    a.birthday,
    -- 使用 julianday 计算日期差（以天为单位），然后除以 365.25 得到年龄
    (julianday(w.release_date) - julianday(a.birthday)) / 365.25 AS age_at_release
  FROM work w
  JOIN work_actress_relation war ON w.work_id = war.work_id
  JOIN actress a ON war.actress_id = a.actress_id
  WHERE w.release_date IS NOT NULL AND a.birthday IS NOT NULL
),
average_age_per_work AS (--辅助计算年龄的表
  SELECT
    work_id,
    serial_number,
    ROUND(AVG(age_at_release), 1)-0.45 AS avg_age_at_release--假设拍摄后5个多月发布
  FROM actress_age_at_release
  GROUP BY work_id
),
actress_list AS(--计算女优出演的名单
SELECT
	w.work_id,
    GROUP_CONCAT(
        (SELECT cn FROM actress_name WHERE actress_id = a.actress_id AND(name_type=1)),
        ','
    ) AS actress_list,
	GROUP_CONCAT(war.job,',') AS job,
	GROUP_CONCAT(war.state,',') AS state
FROM
    work w
LEFT JOIN 
    work_actress_relation war ON w.work_id = war.work_id
LEFT JOIN 
    actress a ON war.actress_id = a.actress_id
GROUP BY w.work_id
),
actor_list AS(--男优名单
SELECT
	w.work_id,
    GROUP_CONCAT(
        (SELECT cn FROM actor_name WHERE actor_id=war1.actor_id),
        ','
    ) AS actor_list
FROM
    work w
LEFT JOIN 
    work_actor_relation war1 ON w.work_id = war1.work_id
LEFT JOIN 
    actor a ON war1.actor_id = a.actor_id
GROUP BY w.work_id
),
studio_list AS(--片商表
SELECT 
	w.work_id,
	(SELECT cn_name FROM maker WHERE maker_id =p.maker_id) AS studio_name
FROM 
    work w
INNER JOIN 
    prefix_maker_relation p ON p.prefix = SUBSTR(w.serial_number, 1, INSTR(w.serial_number, '-') - 1)
WHERE 
    w.serial_number LIKE '%-%'
)
SELECT --水平计算表，然后统一合并
	w.work_id,
    w.serial_number AS serial_number,
    w.director AS director,
	w.release_date AS release_date,
	(SELECT actress_list FROM actress_list WHERE work_id=w.work_id)AS actress,
	(SELECT avg_age_at_release FROM average_age_per_work WHERE work_id=w.work_id)AS avg_age,
	(SELECT state FROM actress_list WHERE work_id=w.work_id)AS state,
	(SELECT actor_list FROM actor_list WHERE work_id=w.work_id)AS actor,
	w.notes AS notes,
	w.cn_title,
	w.cn_story,
	w.jp_title,
	w.jp_story,
	(SELECT studio_name FROM studio_list WHERE work_id=w.work_id)AS studio
FROM 
    work w;
        """
        self.model = SqliteQueryTableModel(self.query_sql, DATABASE, self)

        if not self.model.refresh():
            QMessageBox.critical(self, "错误", "无法加载数据，请查看日志。")
            return

        self.view.setModel(self.model)
        self.view.setColumnHidden(0, True)  # 隐藏 ID 列（主键）

        self.searchWidget.set_model_view(self.model, self.view)

    def init_ui(self):
        self.view = TokenTableView()
        self.btn_refresh = Button("刷新数据")
        export_csv_button = Button("导出为 CSV")
        export_csv_button.clicked.connect(self.export_to_csv)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.btn_refresh)
        button_layout.addWidget(export_csv_button)

        self.serial_number = LineEdit()
        self.studio = ComboBox()

        self.searchWidget = ModelSearch()

        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        layout.addWidget(self.searchWidget)
        layout.addLayout(button_layout)

    def signal_connect(self):
        self.btn_refresh.clicked.connect(self.refresh_data)

    @Slot()
    def refresh_data(self):
        """刷新数据"""
        if not self.model.refresh():
            QMessageBox.critical(self, "刷新错误", "刷新数据失败，请查看日志。")
            return
        logging.info("数据已刷新")

    @Slot()
    def export_to_csv(self):
        """封装为：传入 SQL，用 sqlite 查询并写入 CSV。"""
        from utils.utils import export_sql_to_csv

        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存为 CSV 文件", "", "CSV Files (*.csv)"
        )
        if not file_path:
            return

        if not file_path.endswith(".csv"):
            file_path += ".csv"

        base_sql = getattr(self, "query_sql", "SELECT * FROM v_work_avg_age_info")
        ok = export_sql_to_csv(base_sql, file_path, DATABASE)

        if ok:
            QMessageBox.information(
                self,
                "导出成功",
                f"已根据 SQL 导出所有数据到：\n{file_path}\n用 Excel 打开时请使用 UTF-8 导入，否则会出现乱码。",
            )
        else:
            QMessageBox.critical(self, "导出失败", "导出过程中发生错误，请查看日志。")
