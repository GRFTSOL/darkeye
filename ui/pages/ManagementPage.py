from PySide6.QtWidgets import (
    QHBoxLayout,
    QWidget,
    QVBoxLayout,
    QToolButton,
    QSizePolicy,
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, Slot, QThreadPool

from config import ICONS_PATH
from ui.pages.management.TagManagement import TagManagement
from ui.pages.management.SearchTable import SearchTable
from ui.pages.management.AddWorkTabPage3 import AddWorkTabPage3
from ui.pages.management.StudioManagementPage import StudioManagementPage
from ui.pages.management.LabelManagementPage import LabelManagementPage
from ui.pages.management.SeriesManagementPage import SeriesManagementPage
from ui.pages.management.ManagementTable import ManagementTable
from ui.pages.management.RecycleBinPage import RecycleBinPage
from ui.pages.management.UpdateManyTabPage import UpdateManyTabPage
from ui.pages.management.WorkSoftDeletePage import WorkSoftDeletePage

import logging

from controller.message_service import MessageBoxService

from darkeye_ui.components.token_tab_widget import TokenTabWidget
from darkeye_ui.design.icon import get_builtin_icon

class ManagementPage(QWidget):
    """管理面板，里面嵌套了其他很多的功能"""

    def __init__(self):
        super().__init__()
        # self.setStyleSheet("border: 2px solid red;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        mainlayout = QVBoxLayout(self)
        mainlayout.setContentsMargins(0, 0, 0, 0)
        # mainlayout.addSpacing(72)

        self.msg = MessageBoxService(self)
        # 工具栏区域
        # toolbar = self.create_toolbar()
        # mainlayout.addWidget(toolbar)

        # 主内容区域
        # tabwidget
        self.tab_widget = TokenTabWidget()
        # self.tab_widget.setMovable(True)
        self.worktab = AddWorkTabPage3()
        self.searchtable = SearchTable()
        self.tag_manage = TagManagement()
        self.rubbish = RecycleBinPage()
        self.updatemany = UpdateManyTabPage()
        self.studio_management = StudioManagementPage()
        self.label_management = LabelManagementPage()
        self.series_management = SeriesManagementPage()
        self.g_management = ManagementTable()
        self.work_soft_delete = WorkSoftDeletePage()

        mainlayout.addWidget(self.tab_widget)
        self.tab_widget.addTab(self.worktab, "添加/修改作品")
        self.tab_widget.addTab(self.tag_manage, "作品标签管理")
        self.tab_widget.addTab(self.studio_management, "番号/片商管理")
        self.tab_widget.addTab(self.label_management, "厂牌管理")
        self.tab_widget.addTab(self.series_management, "系列管理")
        self.tab_widget.addTab(self.updatemany, "批量操作")
        self.tab_widget.addTab(self.searchtable, "汇总查询表")
        self.tab_widget.addTab(self.g_management, "综合管理")
        self.tab_widget.addTab(self.work_soft_delete, "作品软删除")
        self.tab_widget.addTab(self.rubbish, "回收站")

    def load_with_params(self, serial_number=None, work_id=None, **kwargs):
        """
        根据路由参数加载管理页（如切换到添加/修改作品 tab 并预填番号）
        业务状态由页面自身管理，Router 只传参。
        """
        if serial_number is None and work_id is not None:
            from core.database.query import get_workinfo_by_workid

            try:
                info = get_workinfo_by_workid(work_id)
                if info:
                    serial_number = info.get("serial_number")
            except Exception:
                logging.exception(
                    "ManagementPage.load_with_params: 根据 work_id 查询作品失败"
                )
        if serial_number is None:
            return
        self.tab_widget.setCurrentWidget(self.worktab)
        if hasattr(self.worktab, "viewmodel"):
            self.worktab.viewmodel.set_serial_number(serial_number)
            self.worktab.viewmodel._load_from_db()
