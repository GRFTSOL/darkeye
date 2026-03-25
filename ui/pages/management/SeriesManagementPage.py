from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDataWidgetMapper,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)
import logging

from config import DATABASE
from core.database.connection import get_connection
from core.database.query import get_series_name
from ui.basic import ModelSearch
from ui.base.SqliteEditableTableModel import SqliteEditableTableModel
from darkeye_ui import LazyWidget
from darkeye_ui.components.label import Label
from darkeye_ui.components.token_table_view import TokenTableView
from darkeye_ui.components.button import Button
from darkeye_ui.components.input import LineEdit
from ui.widgets.selectors.series_selector import SeriesSelector


class SeriesRedirectDialog(QDialog):
    """系列重定向弹窗：左侧为被重定向，右侧为保留系列。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("重定向系列")
        self.setModal(True)
        self.resize(760, 140)

        series_list = get_series_name()
        self.from_selector = SeriesSelector(series_list, self)
        self.to_selector = SeriesSelector(series_list, self)

        self.btn_confirm = Button("确定")
        self.btn_cancel = Button("取消")

        selector_layout = QHBoxLayout()
        from_widget = QWidget()
        from_layout = QVBoxLayout(from_widget)
        from_layout.setContentsMargins(0, 0, 0, 0)
        from_layout.addWidget(Label("被重定向系列"))
        from_layout.addWidget(self.from_selector)

        to_widget = QWidget()
        to_layout = QVBoxLayout(to_widget)
        to_layout.setContentsMargins(0, 0, 0, 0)
        to_layout.addWidget(Label("保留系列"))
        to_layout.addWidget(self.to_selector)

        selector_layout.addWidget(from_widget, 1)
        selector_layout.addWidget(to_widget, 1)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self.btn_confirm)
        button_layout.addWidget(self.btn_cancel)

        layout = QVBoxLayout(self)
        layout.addLayout(selector_layout)
        layout.addLayout(button_layout)

        self.btn_confirm.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def get_selection(self) -> tuple[int | None, int | None]:
        return self.from_selector.get_series_id(), self.to_selector.get_series_id()


class SeriesManagementPage(LazyWidget):
    """系列管理页面（仅管理 series 表）。"""

    def __init__(self):
        super().__init__()

    def _lazy_load(self):
        logging.info("----------系列管理页面----------")
        self.init_ui()
        self.signal_connect()
        self.config()

    def config(self):
        self.model = SqliteEditableTableModel(
            "series",
            DATABASE,
            self,
            header_overrides={
                0: "ID",
                1: "中文名",
                2: "日文名",
                3: "别名",
                4: "详情",
                5: "相关系列",
            },
        )
        if not self.model.refresh():
            QMessageBox.critical(self, "错误", f"加载表 series 失败: {self.model.lastError().text()}")
            return

        self.view.setModel(self.model)
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.view.setSelectionBehavior(QTableView.SelectRows)
        self.view.setColumnHidden(0, True)
        self.view.setColumnWidth(1, 180)
        self.view.setColumnWidth(2, 180)
        self.view.setColumnWidth(3, 220)

        self.mapper = QDataWidgetMapper(self)
        self.mapper.setModel(self.model)
        self.mapper.addMapping(self.cn_name, 1)
        self.mapper.addMapping(self.jp_name, 2)
        self.mapper.addMapping(self.alias, 3)
        selection_model = self.view.selectionModel()
        selection_model.currentRowChanged.connect(self.mapper.setCurrentModelIndex)

        self.searchWidget.set_model_view(self.model, self.view)

    def init_ui(self):
        self.view = TokenTableView()
        self.searchWidget = ModelSearch()

        self.btn_add = Button("新增行")
        self.btn_delete = Button("删除行")
        self.btn_save = Button("保存修改")
        self.btn_revert = Button("撤销修改")
        self.btn_refresh = Button("读数据库数据")
        self.btn_redirect_series = Button("重定向系列")

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.btn_add)
        button_layout.addWidget(self.btn_delete)
        button_layout.addWidget(self.btn_save)
        button_layout.addWidget(self.btn_revert)
        button_layout.addWidget(self.btn_refresh)
        button_layout.addStretch(1)
        button_layout.addWidget(self.btn_redirect_series)

        self.cn_name = LineEdit()
        self.jp_name = LineEdit()
        self.alias = LineEdit()

        form_layout = QFormLayout()
        form_layout.addRow(Label("中文名"), self.cn_name)
        form_layout.addRow(Label("日文名"), self.jp_name)
        form_layout.addRow(Label("别名"), self.alias)

        layout = QVBoxLayout(self)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.searchWidget)
        layout.addLayout(button_layout)
        layout.addLayout(form_layout)

    def signal_connect(self):
        self.btn_add.clicked.connect(self.add_row)
        self.btn_delete.clicked.connect(self.delete_row)
        self.btn_save.clicked.connect(self.save_changes)
        self.btn_revert.clicked.connect(self.revert_changes)
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.btn_redirect_series.clicked.connect(self.open_redirect_dialog)

    @Slot()
    def add_row(self):
        row = self.model.rowCount()
        self.model.insertRow(row)
        self.view.selectRow(row)
        self.view.scrollToBottom()

    @Slot()
    def delete_row(self):
        selected = self.view.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "提示", "请先选择要删除的行")
            return
        for index in selected:
            self.model.removeRow(index.row())

    @Slot()
    def save_changes(self):
        if not self.model.submitAll():
            QMessageBox.critical(self, "错误", f"保存失败: {self.model.lastError().text()}")
            return
        QMessageBox.information(self, "提示", "保存成功")
        from controller.GlobalSignalBus import global_signals

        global_signals.series_data_changed.emit()
        global_signals.work_data_changed.emit()

    @Slot()
    def revert_changes(self):
        self.model.revertAll()
        QMessageBox.information(self, "提示", "已撤销修改")

    @Slot()
    def refresh_data(self):
        if not self.model.refresh():
            QMessageBox.critical(self, "刷新错误", f"刷新 series 失败: {self.model.lastError().text()}")
            return
        self.mapper.toFirst()
        logging.info("series 数据已刷新")

    @Slot()
    def open_redirect_dialog(self):
        dialog = SeriesRedirectDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        source_series_id, target_series_id = dialog.get_selection()
        if source_series_id is None or target_series_id is None:
            QMessageBox.warning(self, "提示", "请先在左右两侧都选择系列")
            return
        if source_series_id == target_series_id:
            QMessageBox.warning(self, "提示", "被重定向系列和保留系列不能相同")
            return

        if not self._redirect_series(source_series_id, target_series_id):
            QMessageBox.critical(self, "错误", "系列重定向失败，请查看日志")
            return

        self.refresh_data()
        QMessageBox.information(self, "提示", "系列重定向成功")
        from controller.GlobalSignalBus import global_signals

        global_signals.series_data_changed.emit()
        global_signals.work_data_changed.emit()

    def _redirect_series(self, source_series_id: int, target_series_id: int) -> bool:
        """将 source 系列重定向到 target，并把 source 名字合并到 target.aliases。"""
        conn = get_connection(DATABASE, False)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT cn_name, jp_name, aliases FROM series WHERE series_id=?",
                (source_series_id,),
            )
            source_row = cursor.fetchone()
            cursor.execute(
                "SELECT cn_name, jp_name, aliases FROM series WHERE series_id=?",
                (target_series_id,),
            )
            target_row = cursor.fetchone()

            if not source_row or not target_row:
                logging.warning("重定向失败：系列不存在 source=%s target=%s", source_series_id, target_series_id)
                conn.rollback()
                return False

            source_cn_name, source_jp_name, _ = source_row
            _, _, target_aliases = target_row

            source_name = str(source_cn_name or source_jp_name or "").strip()
            alias_items = [a.strip() for a in str(target_aliases or "").split(",") if a and a.strip()]
            if source_name:
                alias_items.append(source_name)

            seen: set[str] = set()
            dedup_aliases: list[str] = []
            for alias in alias_items:
                key = alias.lower()
                if key in seen:
                    continue
                seen.add(key)
                dedup_aliases.append(alias)

            cursor.execute(
                "UPDATE series SET aliases=? WHERE series_id=?",
                (",".join(dedup_aliases), target_series_id),
            )
            cursor.execute(
                "UPDATE work SET series_id=? WHERE series_id=?",
                (target_series_id, source_series_id),
            )
            cursor.execute("DELETE FROM series WHERE series_id=?", (source_series_id,))

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            logging.warning("系列重定向失败: %s", e)
            return False
        finally:
            cursor.close()
            conn.close()
