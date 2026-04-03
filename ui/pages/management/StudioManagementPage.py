from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDataWidgetMapper,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)
import logging

from config import BASE_DIR, DATABASE, ICONS_PATH
from controller.message_service import MessageBoxService
from core.database.connection import get_connection
from core.database.db_queue import submit_db_raw
from core.database.query import get_maker_name
from ui.basic import ModelSearch
from ui.base.SqliteEditableTableModel import SqliteEditableTableModel
from ui.base.SqliteQueryTableModel import SqliteQueryTableModel
from ui.base.MakerComboDelegate import MakerComboDelegate
from darkeye_ui import LazyWidget
from darkeye_ui.components.label import Label
from darkeye_ui.components.token_table_view import TokenTableView
from darkeye_ui.components.button import Button
from darkeye_ui.components.input import LineEdit
from darkeye_ui.components.combo_box import ComboBox
from ui.widgets.selectors.maker_selector import MakerSelector
from darkeye_ui.design.icon import get_builtin_icon


class MakerRedirectDialog(QDialog):
    """片商重定向弹窗：左侧为被重定向，右侧为保留片商。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("重定向片商")
        self.setModal(True)
        self.resize(760, 140)

        makers = submit_db_raw(get_maker_name).result()
        self.from_selector = MakerSelector(makers, self)
        self.to_selector = MakerSelector(makers, self)

        self.btn_confirm = Button("确定")
        self.btn_cancel = Button("取消")

        selector_layout = QHBoxLayout()

        from_layout = QVBoxLayout()
        from_layout.addWidget(Label("被重定向片商"))
        from_layout.addWidget(self.from_selector)

        to_layout = QVBoxLayout()
        to_layout.addWidget(Label("保留片商"))
        to_layout.addWidget(self.to_selector)

        selector_layout.addLayout(from_layout, 1)
        selector_layout.addLayout(to_layout, 1)

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
        return self.from_selector.get_maker(), self.to_selector.get_maker()


class StudioManagementPage(LazyWidget):
    # StudioManagementPage
    def __init__(self):
        super().__init__()

    def _lazy_load(self):
        logging.info("----------制作商管理页面----------")
        self.init_ui()

        self.signal_connect()

        self.config()

        self.current_active_view = self.view1  # 默认选择

    def config(self):
        """配置 model 与 view"""
        # 表格用 delegate（parent=view1）；mapper 用独立 delegate（parent=None），
        # 避免 "editor does not belong to this view" 警告
        self.maker_delegate = MakerComboDelegate(
            self.view1, DATABASE, maker_col_index=2
        )
        self.mapper_maker_delegate = MakerComboDelegate(
            None, DATABASE, maker_col_index=2
        )

        # model1: prefix_maker_relation
        self.model1 = SqliteEditableTableModel(
            "prefix_maker_relation",
            DATABASE,
            self,
            relation_config={2: ("maker", "maker_id", "cn_name")},
            header_overrides={0: "ID", 1: "番号前缀", 2: "制作商"},
        )
        if not self.model1.refresh():
            QMessageBox.critical(
                self,
                "错误",
                f"加载表 prefix_maker_relation 失败: {self.model1.lastError().text()}",
            )
            return

        self.view1.setModel(self.model1)
        self.view1.setSelectionMode(QAbstractItemView.SingleSelection)
        self.view1.setSelectionBehavior(QTableView.SelectRows)
        self.view1.setColumnHidden(0, True)
        self.view1.setColumnWidth(1, 180)
        self.view1.setColumnWidth(2, 180)
        self.view1.setItemDelegate(self.maker_delegate)

        # studio ComboBox 数据源
        self.maker_combo_model = SqliteQueryTableModel(
            "SELECT maker_id, cn_name FROM maker", DATABASE
        )
        self.maker_combo_model.refresh()
        self.studio.setModel(self.maker_combo_model)
        self.studio.setModelColumn(1)  # 显示 cn_name

        self.mapper1 = QDataWidgetMapper(self)
        self.mapper1.setModel(self.model1)
        self.mapper1.setItemDelegate(self.mapper_maker_delegate)
        self.mapper1.addMapping(self.serial_number, 1)  # prefix
        self.mapper1.addMapping(self.studio, 2)  # maker_id

        selection_model1 = self.view1.selectionModel()
        selection_model1.currentRowChanged.connect(self.mapper1.setCurrentModelIndex)

        # model2: maker
        self.model2 = SqliteEditableTableModel(
            "maker",
            DATABASE,
            self,
            header_overrides={0: "ID", 1: "中文名", 2: "日文名", 3: "别名"},
        )
        if not self.model2.refresh():
            QMessageBox.critical(
                self, "错误", f"加载表 maker 失败: {self.model2.lastError().text()}"
            )
            return

        self.view2.setModel(self.model2)
        self.view2.setSelectionMode(QAbstractItemView.SingleSelection)
        self.view2.setSelectionBehavior(QTableView.SelectRows)
        self.view2.setColumnHidden(0, True)
        self.view2.setColumnWidth(1, 180)
        self.view2.setColumnWidth(2, 180)

        self.mapper2 = QDataWidgetMapper(self)
        self.mapper2.setModel(self.model2)
        self.mapper2.addMapping(self.cn_name, 1)  # cn_name
        self.mapper2.addMapping(self.jp_name, 2)  # jp_name
        self.mapper2.addMapping(self.alias, 3)  # aliases

        selection_model2 = self.view2.selectionModel()
        selection_model2.currentRowChanged.connect(self.mapper2.setCurrentModelIndex)

        self.searchWidget.set_model_view(self.model1, self.view1)

        self.view1.installEventFilter(self)
        self.view2.installEventFilter(self)

    def init_ui(self):
        self.msg = MessageBoxService(self)

        self.view1 = TokenTableView()
        self.view2 = TokenTableView()

        self.status_label = Label("")
        # 表格区域 - 使用分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.view1)
        splitter.addWidget(self.view2)
        splitter.setMinimumHeight(400)

        # 按钮
        self.btn_add = Button("新增行")
        self.btn_delete = Button("删除行")
        self.btn_save = Button("保存修改")
        self.btn_revert = Button("撤销修改")
        self.btn_refresh = Button("读数据库数据")
        self.btn_redirect_maker = Button("重定向片商")

        self.btn_export_maker_prefix = Button()
        self.btn_export_maker_prefix.setText("导出片商前缀到json文件")
        self.btn_export_maker_prefix.setToolTip("导出片商前缀到json文件")
        self.btn_export_maker_prefix.setIcon(get_builtin_icon(name="database"))

        self.btn_import_maker_prefix = Button()
        self.btn_import_maker_prefix.setText("从json文件导入片商前缀")
        self.btn_import_maker_prefix.setToolTip("从json文件导入片商前缀")
        self.btn_import_maker_prefix.setIcon(get_builtin_icon(name="database"))

        # 布局
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.btn_add)
        button_layout.addWidget(self.btn_delete)
        button_layout.addWidget(self.btn_save)
        button_layout.addWidget(self.btn_revert)
        button_layout.addWidget(self.btn_refresh)
        button_layout.addWidget(self.btn_export_maker_prefix)
        button_layout.addWidget(self.btn_import_maker_prefix)
        button_layout.addStretch(1)
        button_layout.addWidget(self.btn_redirect_maker)
        button_layout.addWidget(self.status_label)

        self.serial_number = LineEdit()
        self.studio = ComboBox()

        formlayout1 = QFormLayout()
        formlayout1.addRow(Label("番号前缀"), self.serial_number)
        formlayout1.addRow(Label("制作商"), self.studio)

        self.cn_name = LineEdit()
        self.jp_name = LineEdit()
        self.alias = LineEdit()
        formlayout2 = QFormLayout()
        formlayout2.addRow(Label("中文名"), self.cn_name)
        formlayout2.addRow(Label("日文名"), self.jp_name)
        formlayout2.addRow(Label("别名"), self.alias)

        self.searchWidget = ModelSearch()
        hlayout = QHBoxLayout()
        hlayout.addLayout(formlayout1)
        hlayout.addLayout(formlayout2)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter, 1)  # stretch=1 让 splitter 占据剩余空间
        layout.addWidget(self.searchWidget)
        layout.addLayout(button_layout)
        layout.addLayout(hlayout)

    def signal_connect(self):
        # 信号连接
        self.btn_add.clicked.connect(self.add_row)
        self.btn_delete.clicked.connect(self.delete_row)
        self.btn_save.clicked.connect(self.save_changes)
        self.btn_revert.clicked.connect(self.revert_changes)
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.btn_redirect_maker.clicked.connect(self.open_redirect_dialog)
        self.btn_export_maker_prefix.clicked.connect(self.export_maker_prefix)
        self.btn_import_maker_prefix.clicked.connect(self.import_maker_prefix)

    @Slot()
    def export_maker_prefix(self):
        from core.database.migrations import export_maker_prefix_json

        default_dir = BASE_DIR / "resources" / "config"
        default_dir.mkdir(parents=True, exist_ok=True)

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "选择导出 JSON 文件",
            str(default_dir / "maker_prefix.json"),
            "JSON 文件 (*.json)",
        )
        if not file_path:
            return

        try:
            export_maker_prefix_json(Path(file_path))
            self.msg.show_info("导出成功", f"已导出片商前缀到：\n{file_path}")
        except Exception as e:
            logging.exception("导出片商前缀失败")
            self.msg.show_critical("导出失败", f"导出片商前缀时发生错误：\n{e}")

    @Slot()
    def import_maker_prefix(self):
        from core.database.migrations import import_maker_prefix_json

        default_dir = BASE_DIR / "resources" / "config"
        default_dir.mkdir(parents=True, exist_ok=True)

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择片商前缀 JSON 文件",
            str(default_dir),
            "JSON 文件 (*.json)",
        )
        if not file_path:
            return

        if not self.msg.ask_yes_no(
            "确认导入",
            "将使用该 JSON 覆盖当前的片商和前缀数据，操作不可撤销，是否继续？",
        ):
            return

        try:
            import_maker_prefix_json(Path(file_path))
            self.msg.show_info("导入成功", "片商前缀数据已从 JSON 导入。")
            self.refresh_data()
            from controller.global_signal_bus import global_signals

            global_signals.makerDataChanged.emit()
            global_signals.workDataChanged.emit()
        except Exception as e:
            logging.exception("导入片商前缀失败")
            self.msg.show_critical("导入失败", f"导入片商前缀时发生错误：\n{e}")

    def eventFilter(self, obj, event):
        """事件过滤器，用于跟踪焦点变化"""
        if event.type() == event.Type.FocusIn:
            if obj in [self.view1, self.view2]:
                self.set_active_view(obj)
        return super().eventFilter(obj, event)

    def set_active_view(self, view: QTableView):
        """设置当前活动视图"""
        self.current_active_view = view
        view_name = "前缀表格" if view == self.view1 else "制作商表"
        self.status_label.setText(f"当前焦点: {view_name}")

        # 可选：高亮当前活动视图
        self.view1.setStyleSheet("")
        self.view2.setStyleSheet("")
        # view.setStyleSheet("border: 2px solid blue;")
        view.setStyleSheet(
            """
        QTableView{
            border: 2px solid orange;
        }
        """
        )
        model, view = self.get_current_model_and_view()
        self.searchWidget.set_model_view(model, view)

    def get_current_model_and_view(self):
        """获取当前活动的模型和视图"""
        if self.current_active_view == self.view1:
            return self.model1, self.view1
        elif self.current_active_view == self.view2:
            return self.model2, self.view2
        return None, None

    @Slot()
    def add_row(self):
        """新增一行"""
        model, view = self.get_current_model_and_view()
        if view == self.view1:
            default = ["番号前缀", 1]
        else:
            default = []
        if model and view:
            row = model.rowCount()
            model.insertRow(row)
            # 可选：初始化部分字段
            for i, value in enumerate(default):
                model.setData(model.index(row, i + 1), value)
            view.selectRow(row)
            # 滚动到最后一行
            view.scrollToBottom()  # 滚动到底

    @Slot()
    def delete_row(self):
        """删除选中的行"""
        model, view = self.get_current_model_and_view()
        if model and view:
            selected = view.selectionModel().selectedRows()
            if not selected:
                QMessageBox.warning(self, "提示", "请先选择要删除的行")
                return
            for index in selected:
                model.removeRow(index.row())

    @Slot()
    def save_changes(self):
        """保存修改到数据库"""
        model, view = self.get_current_model_and_view()
        if model and view:
            if not model.submitAll():
                QMessageBox.critical(
                    self, "错误", f"保存失败: {model.lastError().text()}"
                )
            else:
                QMessageBox.information(self, "提示", "保存成功")
                from controller.global_signal_bus import global_signals

                global_signals.makerDataChanged.emit()
                global_signals.workDataChanged.emit()

    @Slot()
    def revert_changes(self):
        """撤销未保存的修改"""
        model, view = self.get_current_model_and_view()
        if model and view:
            model.revertAll()
            QMessageBox.information(self, "提示", "已撤销修改")

    @Slot()
    def refresh_data(self):
        """刷新数据"""
        if not self.model1.refresh():
            QMessageBox.critical(
                self,
                "刷新错误",
                f"刷新 prefix_maker_relation 失败: {self.model1.lastError().text()}",
            )
            return
        if not self.model2.refresh():
            QMessageBox.critical(
                self, "刷新错误", f"刷新 maker 失败: {self.model2.lastError().text()}"
            )
            return

        self.maker_combo_model.refresh()
        self.studio.setModel(self.maker_combo_model)
        self.studio.setModelColumn(1)
        self.maker_delegate.refresh_maker_model()
        self.mapper_maker_delegate.refresh_maker_model()

        self.mapper1.toFirst()
        self.mapper2.toFirst()

        logging.info("数据已刷新，关联下拉框已更新")

    @Slot()
    def open_redirect_dialog(self):
        dialog = MakerRedirectDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        source_maker_id, target_maker_id = dialog.get_selection()
        if source_maker_id is None or target_maker_id is None:
            QMessageBox.warning(self, "提示", "请先在左右两侧都选择片商")
            return
        if source_maker_id == target_maker_id:
            QMessageBox.warning(self, "提示", "被重定向片商和保留片商不能相同")
            return

        if not self._redirect_maker(source_maker_id, target_maker_id):
            QMessageBox.critical(self, "错误", "片商重定向失败，请查看日志")
            return

        self.refresh_data()
        QMessageBox.information(self, "提示", "片商重定向成功")
        from controller.global_signal_bus import global_signals

        global_signals.makerDataChanged.emit()
        global_signals.workDataChanged.emit()

    def _redirect_maker(self, source_maker_id: int, target_maker_id: int) -> bool:
        """将 source 片商重定向到 target，并把 source 名字合并到 target.aliases。"""
        conn = get_connection(DATABASE, False)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT cn_name, jp_name, aliases FROM maker WHERE maker_id=?",
                (source_maker_id,),
            )
            source_row = cursor.fetchone()
            cursor.execute(
                "SELECT cn_name, jp_name, aliases FROM maker WHERE maker_id=?",
                (target_maker_id,),
            )
            target_row = cursor.fetchone()

            if not source_row or not target_row:
                logging.warning(
                    "重定向失败：片商不存在 source=%s target=%s",
                    source_maker_id,
                    target_maker_id,
                )
                conn.rollback()
                return False

            source_cn_name, source_jp_name, _ = source_row
            _, _, target_aliases = target_row

            source_name = str(source_cn_name or source_jp_name or "").strip()
            alias_items = [
                a.strip()
                for a in str(target_aliases or "").split(",")
                if a and a.strip()
            ]
            if source_name:
                alias_items.append(source_name)

            # 去重（忽略大小写），保留原始写法和顺序
            seen: set[str] = set()
            dedup_aliases: list[str] = []
            for alias in alias_items:
                key = alias.lower()
                if key in seen:
                    continue
                seen.add(key)
                dedup_aliases.append(alias)

            cursor.execute(
                "UPDATE maker SET aliases=? WHERE maker_id=?",
                (",".join(dedup_aliases), target_maker_id),
            )
            cursor.execute(
                "UPDATE work SET maker_id=? WHERE maker_id=?",
                (target_maker_id, source_maker_id),
            )
            cursor.execute(
                "UPDATE prefix_maker_relation SET maker_id=? WHERE maker_id=?",
                (target_maker_id, source_maker_id),
            )
            cursor.execute("DELETE FROM maker WHERE maker_id=?", (source_maker_id,))

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            logging.warning("片商重定向失败: %s", e)
            return False
        finally:
            cursor.close()
            conn.close()
