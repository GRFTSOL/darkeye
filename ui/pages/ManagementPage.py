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

import logging

from controller.MessageService import MessageBoxService

from darkeye_ui.components.token_tab_widget import TokenTabWidget


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

        mainlayout.addWidget(self.tab_widget)
        self.tab_widget.addTab(self.worktab, "添加/修改作品")
        self.tab_widget.addTab(self.tag_manage, "作品标签管理")
        self.tab_widget.addTab(self.studio_management, "番号/片商管理")
        self.tab_widget.addTab(self.label_management, "厂牌管理")
        self.tab_widget.addTab(self.series_management, "系列管理")
        self.tab_widget.addTab(self.updatemany, "批量操作")
        self.tab_widget.addTab(self.searchtable, "汇总查询表")
        self.tab_widget.addTab(self.g_management, "综合管理")
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

    # 工具栏
    def create_toolbar(self):
        # 工具栏
        toolbar = QWidget()
        toolbar.setFixedHeight(30)

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 0, 2, 0)
        layout.setSpacing(3)

        # 工具按钮
        btn_addWork = QToolButton()
        btn_addWork.setText("快速记录番号(W)")
        btn_addWork.setToolTip("快速记录番号")
        btn_addWork.setIcon(QIcon(str(ICONS_PATH / "film.png")))
        btn_addWork.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        btn_addAdress = QToolButton()
        btn_addAdress.setText("添加新女优")
        btn_addAdress.setToolTip(
            "手动添加女优，至少需要输入一个准确的中文名与日文名，要求日文名在MinnanoAV能找到"
        )
        btn_addAdress.setIcon(QIcon(str(ICONS_PATH / "venus.png")))
        btn_addAdress.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        btn_reNewAdress = QToolButton()
        btn_reNewAdress.setText("更新女优数据")
        btn_reNewAdress.setToolTip(
            "根据标记自动更新女优的数据，包括身高，三维，罩杯，出生年月，出道日期，照片"
        )
        btn_reNewAdress.setIcon(QIcon(str(ICONS_PATH / "refresh-cw.svg")))
        btn_reNewAdress.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        btn_addMasturbate = QToolButton()
        btn_addMasturbate.setText("添加自慰记录(M)")
        btn_addMasturbate.setToolTip("添加自慰记录，包括时间，满意度，以及感受")
        btn_addMasturbate.setIcon(QIcon(str(ICONS_PATH / "masturbate.png")))
        btn_addMasturbate.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        btn_addSex = QToolButton()
        btn_addSex.setText("添加做爱记录(L)")
        btn_addSex.setToolTip("添加做爱记录，包括时间，满意度，以及感受")
        btn_addSex.setIcon(QIcon(str(ICONS_PATH / "sex.png")))
        btn_addSex.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        btn_addGenitalAarousal = QToolButton()
        btn_addGenitalAarousal.setText("添加性器官唤起记录(A)")
        btn_addGenitalAarousal.setToolTip(
            "添加睡眠相关的性器官唤起记录，包括男性的晨勃起，或者女性的阴蒂充血勃起"
        )
        btn_addGenitalAarousal.setIcon(QIcon(str(ICONS_PATH / "erection.png")))
        btn_addGenitalAarousal.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        btn_addActor = QToolButton()
        btn_addActor.setText("添加新男优")
        btn_addActor.setToolTip("手动添加男优，至少需要输入一个准确的中文名与日文名")
        btn_addActor.setIcon(QIcon(str(ICONS_PATH / "mars.png")))
        btn_addActor.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # 右侧空白拉伸
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout.addWidget(btn_addWork)
        layout.addWidget(btn_addAdress)
        layout.addWidget(btn_reNewAdress)
        layout.addWidget(btn_addActor)
        layout.addWidget(btn_addMasturbate)
        layout.addWidget(btn_addSex)
        layout.addWidget(btn_addGenitalAarousal)

        layout.addWidget(spacer)

        toolbar.setObjectName("managementPageToolbar")
        toolbar.setStyleSheet("""
            #managementPageToolbar QToolButton {
                padding: 0px 0px;
                background: #F0F0F0;
                border: 1px solid #ccc;
                border-radius: 0px;
            }
            #managementPageToolbar QToolButton:hover {
                background: #D8EAF9;
            }
        """)

        return toolbar
