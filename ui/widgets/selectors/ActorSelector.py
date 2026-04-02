from PySide6.QtWidgets import QHBoxLayout, QWidget, QVBoxLayout, QLineEdit
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt, QItemSelection, Signal, Slot
import sqlite3
import logging
import time
from config import DATABASE
from core.database.db_queue import submit_db_raw
from controller.message_service import MessageBoxService

from darkeye_ui.components.label import Label
from darkeye_ui.components.input import LineEdit
from darkeye_ui.components.icon_push_button import IconPushButton
from darkeye_ui.components.token_list_view import TokenListView


class ActorSelector(QWidget):
    """男演员选择器"""

    selectionChanged = Signal()  # 下方被选择的列表改变了

    def __init__(self):
        super().__init__()

        # 主要逻辑是实例化后的Item移来移去
        # 数据初始化
        self.choose_actor_all_items = self.load_actor_from_db()
        self.choose_actor_items = list(self.choose_actor_all_items)
        self.receive_actor_items = []
        self.msg = MessageBoxService(self)

        # 模型初始化
        self.receive_actor_model = QStandardItemModel()
        self.choose_actor_model = QStandardItemModel()

        self.update_model(self.choose_actor_model, self.choose_actor_items)
        self.update_model(self.receive_actor_model, self.receive_actor_items)

        # 右侧搜索框和视图和按钮

        self.search_box = LineEdit()
        self.search_box.setPlaceholderText("搜索中文名或日文名")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self.filter_choose_actor_items)

        self.choose_actor_view = TokenListView()
        self.choose_actor_view.setModel(self.choose_actor_model)

        self.label_actor = Label("参演男优")
        self.label_actor.setAlignment(Qt.AlignCenter)

        self.receive_actor_view = TokenListView()
        self.receive_actor_view.setModel(self.receive_actor_model)

        # 连接选中信号
        self.receive_actor_view.selectionModel().selectionChanged.connect(
            lambda selected, _: self.clear_other_selection(
                self.choose_actor_view, selected
            )
        )
        self.choose_actor_view.selectionModel().selectionChanged.connect(
            lambda selected, _: self.clear_other_selection(
                self.receive_actor_view, selected
            )
        )

        # 按钮
        self.btn_to_left = IconPushButton(icon_name="arrow_down")
        self.btn_to_left.setToolTip("选择参演男优")
        self.btn_to_right = IconPushButton(icon_name="arrow_up")
        self.btn_to_right.setToolTip("移除参演男优")
        self.btn_add_actor = IconPushButton(icon_name="circle_plus")
        self.btn_add_actor.setToolTip("添加男优并选择")

        self.btn_to_left.clicked.connect(self.move_to_left)
        self.btn_to_right.clicked.connect(self.move_to_right)
        self.btn_add_actor.clicked.connect(self.add_actor_dialog)

        # 男优中间按钮布局
        btn_actor_layout = QHBoxLayout()
        btn_actor_layout.addWidget(self.btn_to_left)
        btn_actor_layout.addWidget(self.label_actor)
        btn_actor_layout.addWidget(self.btn_to_right)

        # 男优搜索布局
        btn_actor_search_layout = QHBoxLayout()
        btn_actor_search_layout.addWidget(self.search_box)
        btn_actor_search_layout.addWidget(self.btn_add_actor)

        # 男优选择列布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addLayout(btn_actor_search_layout)
        main_layout.addWidget(self.choose_actor_view)
        main_layout.addLayout(btn_actor_layout)
        main_layout.addWidget(self.receive_actor_view)

        from controller.global_signal_bus import global_signals

        global_signals.actorDataChanged.connect(self.refresh_right_list)

    def load_actor_from_db(self, exclude_ids=None):
        exclude_ids = exclude_ids or []
        """从数据库读数据并加载到viewmodel内,在打开页面的过程中只运行一次
        #数据库有没有被正确的读取是一个问题，数据库的版本与软件的版本要对上
        """
        query = """
SELECT
    a.actor_id,
    actor_name.cn AS cn_name,
    actor_name.jp AS jp_name
FROM actor a
JOIN actor_name ON actor_name.actor_id=a.actor_id
"""
        try:
            t0 = time.perf_counter()
            rows = submit_db_raw(lambda: self._fetch_actor_rows_from_db(query)).result()
            items = []
            rows = rows[::-1]
            for actor_id, cn_name, jp_name in rows:
                if actor_id in exclude_ids:
                    continue
                label = f"{cn_name}（{jp_name}）"
                item = QStandardItem(label)

                # 设置附加数据（绑定 ID）
                item.setData(actor_id)
                # 设置只读不可编辑
                item.setEditable(False)
                items.append(item)

            elapsed_ms = (time.perf_counter() - t0) * 1000
            logging.info(
                "ActorSelector 加载男优数据库完成，耗时 %.2f ms，共 %d 条",
                elapsed_ms,
                len(items),
            )
            return items
        except Exception as e:
            self.msg.show_critical("数据库错误", f"无法读取数据：\n{e}")
            logging.warning("读取男优数据库失败%s", e)
            return []

    def _fetch_actor_rows_from_db(self, query: str) -> list[tuple]:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    @Slot()
    def move_to_left(self):
        """移动到选择侧"""
        index = self.choose_actor_view.selectionModel().selectedIndexes()
        if not index:
            return
        item = self.choose_actor_model.itemFromIndex(index[0])

        # 移动逻辑
        self.choose_actor_items.remove(item)
        self.choose_actor_all_items.remove(item)
        item_copy = item.clone()
        self.receive_actor_items.append(item_copy)

        self.update_model(self.receive_actor_model, self.receive_actor_items)
        self.filter_choose_actor_items(self.search_box.text())

        self.selectionChanged.emit()  # 发射信号

    @Slot()
    def move_to_right(self):
        """移动到待选侧"""
        index = (
            self.receive_actor_view.selectionModel().selectedIndexes()
        )  # 找到选择的index
        if not index:
            return
        item = self.receive_actor_model.itemFromIndex(index[0])

        self.receive_actor_items.remove(item)
        item_copy = item.clone()
        self.choose_actor_all_items.insert(0, item_copy)

        self.update_model(self.receive_actor_model, self.receive_actor_items)
        self.filter_choose_actor_items(self.search_box.text())

        self.selectionChanged.emit()  # 发射信号

    def refresh_right_list(self):
        """这个是新添加男优后才刷新已选择侧列表"""
        # 刷新待选列表
        # 获取左侧所有已选ID
        left_ids = [
            self.receive_actor_model.item(i).data()
            for i in range(self.receive_actor_model.rowCount())
        ]
        # 从数据库重新加载，排除已在左边的
        self.choose_actor_all_items = self.load_actor_from_db(exclude_ids=left_ids)
        self.update_model(self.choose_actor_model, self.choose_actor_all_items)
        # 根据搜索框文本筛选
        self.filter_choose_actor_items(self.search_box.text())
        self.selectionChanged.emit()

    def update_model(self, model: QStandardItemModel, items: list):
        model.clear()
        for item in items:
            model.appendRow(item)

    def filter_choose_actor_items(self, keyword):
        keyword = keyword.strip()
        if not keyword:
            self.choose_actor_items = list(self.choose_actor_all_items)
        else:
            self.choose_actor_items = [
                item for item in self.choose_actor_all_items if keyword in item.text()
            ]
        self.update_model(self.choose_actor_model, self.choose_actor_items)

    @Slot()
    def add_actor_dialog(self):
        from ui.dialogs.AddActorDialog import AddActorDialog

        dialog = AddActorDialog()
        dialog.success.connect(self.handle_actor_result)
        dialog.exec()  # 模态显示对话框，阻塞主窗口直到关闭

    @Slot()
    def handle_actor_result(self):
        # 接受添加男优成功的信号后进行操作
        self.refresh_right_list()
        old_text = self.search_box.text()
        self.search_box.clear()
        # 选中右侧最上面
        if self.choose_actor_model.rowCount() > 0:
            index = self.choose_actor_model.index(0, 0)  # 第 0 行，第 0 列
            self.choose_actor_view.setCurrentIndex(index)
            self.choose_actor_view.scrollTo(index)  # 可选：自动滚动到该项
        self.move_to_left()
        self.search_box.setText(old_text)  # 保持输入框的文字

    def clear_other_selection(self, other_list, selected: QItemSelection):
        """当选中状态变化时，清除另一个列表的选中"""
        if selected.count() > 0:  # 如果有选中项
            other_list.selectionModel().clearSelection()

    def find_item_by_id(self, target_id: int) -> QStandardItem | None:
        """通过ID在choose_actor_items中查找item"""
        for item in self.choose_actor_items:
            if item.data() == target_id:  # 假设ID存储在默认角色
                return item

        logging.warning("根据id: %s  找不到待选区对应的item", target_id)
        return None

    def move_all_to_left(self):
        """把接收器的部分全部移回去，回到初始状态"""
        self.search_box.setText(None)
        for item in self.receive_actor_items.copy():
            # logging.info(item.text())
            self.receive_actor_items.remove(item)  # 危险操作注意
            item_copy = item.clone()
            self.choose_actor_all_items.insert(0, item_copy)

        self.update_model(self.receive_actor_model, self.receive_actor_items)
        self.filter_choose_actor_items(self.search_box.text())

    def get_selection_actor_name(self) -> str:
        """获得当前选择的男优的姓名"""
        index = self.choose_actor_view.selectionModel().selectedIndexes()
        if not index:
            return
        item = self.choose_actor_model.itemFromIndex(index[0])
        return item.text()

    # ---------------------------------------------------
    #                 暴露在外面的接口
    # ---------------------------------------------------

    def get_selected_ids(self) -> list:
        """返回被选中的id"""
        ids = []

        for row in range(self.receive_actor_model.rowCount()):
            item = self.receive_actor_model.item(row)
            actor_id = item.data()
            ids.append(actor_id)
        return ids

    @Slot("QList<int>")
    def load_with_ids(self, ids: list[int]):
        """通过ids列表加载到下面的选择器里
        不能重新加载，整个系统只是加载一次，然后就是不断的移动
        """
        self.search_box.setText(None)
        self.move_all_to_left()

        # 爬虫在 DB 线程插入新男优后会 emit actorDataChanged（queued 到主线程），
        # 而 guiUpdate 在 submit_db_raw().result() 返回后主线程立即 set_actor，
        # 常见顺序是 load_with_ids 先于 refresh_right_list 执行，待选池仍是旧数据，
        # find_item_by_id 得到 None，进而 remove 报错。此处与 DB 同步待选列表。
        self.choose_actor_all_items = self.load_actor_from_db()
        self.filter_choose_actor_items(self.search_box.text())

        # 去重并保持顺序，避免同一 ID 第二次找不到条目
        ids = list(dict.fromkeys(ids))

        for id in ids:
            item = self.find_item_by_id(id)
            if item is None:
                logging.warning(
                    "load_with_ids: 男优 ID %s 不在待选列表（库无记录或 actor / actor_name "
                    "缺少可用的中日文名）",
                    id,
                )
                continue
            if item not in self.choose_actor_items:
                logging.warning(
                    "load_with_ids: 男优 ID %s 的条目与当前待选列表不同步，已跳过",
                    id,
                )
                continue
            self.choose_actor_items.remove(item)
            self.choose_actor_all_items.remove(item)
            item_copy = item.clone()
            self.receive_actor_items.append(item_copy)

        self.update_model(self.receive_actor_model, self.receive_actor_items)
        self.filter_choose_actor_items(self.search_box.text())
        self.selectionChanged.emit()
