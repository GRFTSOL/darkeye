# 单部作品详细页面
from PySide6.QtWidgets import (
    QHBoxLayout,
    QWidget,
    QLabel,
    QGraphicsOpacityEffect,
    QSizePolicy,
    QVBoxLayout,
    QLayoutItem,
    QMenu,
)
from PySide6.QtGui import QPixmap, QPainter, QLinearGradient, QColor, QFont
from PySide6.QtCore import Qt, QPointF, Signal, Slot
import logging

from darkeye_ui.components import TokenVLabel
from darkeye_ui.layouts import VFlowLayout
from darkeye_ui.components.heart_label import HeartLabel
from config import WORKCOVER_PATH, ICONS_PATH
from ui.widgets.text.VerticalTagLabel2 import (
    VerticalActressLabel,
    VerticalTagLabel,
    VerticalActorLabel,
)
from darkeye_ui import LazyWidget
from darkeye_ui.components.vertical_text_label import VerticalTextLabel
from darkeye_ui.components.transparent_widget import TransparentWidget
from darkeye_ui.components.icon_push_button import IconPushButton


# 渐变层纯绘图层
class GradientOverlay(QWidget):
    # 上面的渐变层
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def resizeEvent(self, event):
        # 始终覆盖父窗口
        if self.parent():
            self.resize(self.parent().size())
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        window_width = self.width()
        window_height = self.height()

        gradient = QLinearGradient(
            QPointF(window_width - 1.5 * window_height, 0), QPointF(window_width, 0)
        )
        gradient.setColorAt(0, QColor(20, 20, 20, 255))
        gradient.setColorAt(1, QColor(0, 0, 0, 0))

        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, window_width, window_height)

        grad_right = QLinearGradient(
            QPointF(window_width, 0), QPointF(window_width - 0.1 * window_height, 0)
        )
        grad_right.setColorAt(0, QColor(20, 20, 20, 255))  # 右边黑色
        grad_right.setColorAt(1, QColor(0, 0, 0, 0))  # 中间透明
        painter.setBrush(grad_right)
        painter.drawRect(
            window_width - 0.1 * window_height, 0, window_width, window_height
        )
        painter.end()


class Cover(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._path = None
        self.setAlignment(Qt.AlignRight | Qt.AlignTop)

    def load_cover(self):
        """加载"""
        if self._path is None:
            path = str(ICONS_PATH / "none.png")
            pixmap = QPixmap(path)
            if pixmap.isNull():
                logging.info(f"加载失败: {path}")
                pixmap = QPixmap(800, 600)
                pixmap.fill(Qt.black)
            self.original_pixmap = pixmap
            return

        from PySide6.QtGui import QImage

        imgmap = QImage(str(WORKCOVER_PATH / self._path))
        if imgmap.isNull():
            logging.info(f"加载失败: {path}")
            imgmap = QImage(800, 600)
            imgmap.fill(Qt.black)
        self.original_pixmap = QPixmap.fromImage(
            imgmap
        )  # 现在的问题是这个存的东西会过大，几个逻辑重复
        del imgmap
        # logging.debug("加载封面")

    def update_background_image(self, animate=False):
        """缩放"""
        # 更新背景的图片，包括动画

        window_width = self.width()
        window_height = self.height()
        image_height = self.original_pixmap.height()
        image_width = self.original_pixmap.width()
        scale_factor = window_height / image_height
        scaled_width = int(image_width * scale_factor)
        scaled_height = window_height
        scaled_pixmap = self.original_pixmap.scaled(
            scaled_width, scaled_height, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        self.setPixmap(scaled_pixmap)  # 这里才是真正的设置了图片，并显示

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._path:
            self.update_background_image()

    # 对外使用
    def set_cover(self, path):
        self._path = path
        self.load_cover()
        self.update_background_image()


class WorkInfo(TransparentWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        from controller.MessageService import MessageBoxService

        self.msg = MessageBoxService(self)

        self._work_id = None
        # self.setStyleSheet("border: 2px solid red;")
        self.title = VerticalTextLabel()
        self.title.setFixedHeight(550)
        self.title.setTextColor("#FFFFFF")
        self.title.setFont(QFont("Microsoft YaHei", 24))
        self.title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.story = VerticalTextLabel()
        self.story.setFixedHeight(550)
        self.story.setTextColor("#FFFFFF")
        self.story.setFont(QFont("Microsoft YaHei", 12))
        self.story.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.serial_number_label = TokenVLabel(
            "番号",
            text_color="#FFFFFF",
            background_color="#00000000",
            border_color="#FFFFFF",
        )
        self.serial_number = TokenVLabel(
            " ",
            text_color="#FFFFFF",
            background_color="#00000000",
            border_color="#FFFFFF",
        )
        # self.serial_number.setTextColor("#FFFFFF")

        self.release_date_label = TokenVLabel(
            "发行日期",
            text_color="#FFFFFF",
            background_color="#00000000",
            border_color="#FFFFFF",
        )
        self.release_date = TokenVLabel(
            " ",
            text_color="#FFFFFF",
            background_color="#00000000",
            border_color="#FFFFFF",
        )
        # self.release_date.setTextColor("#FFFFFF")

        # 这些东西都要动态添加，有些是空的就会有大问题
        self.director_label = TokenVLabel(
            "导演",
            text_color="#FFFFFF",
            background_color="#00000000",
            border_color="#FFFFFF",
        )
        self.director = TokenVLabel(
            " ",
            text_color="#FFFFFF",
            background_color="#00000000",
            border_color="#FFFFFF",
        )  # 这个有bug，不能是空的

        self.studio_label = TokenVLabel(
            "制作商",
            text_color="#FFFFFF",
            background_color="#00000000",
            border_color="#FFFFFF",
        )
        self.studio = TokenVLabel(
            " ",
            text_color="#FFFFFF",
            background_color="#00000000",
            border_color="#FFFFFF",
        )  # 这个有bug，不能是空的
        self.label_tag = TokenVLabel(
            "作品标签",
            text_color="#FFFFFF",
            background_color="#00000000",
            border_color="#FFFFFF",
        )

        self.actress = TransparentWidget(self)
        self.label = TransparentWidget(self)
        self.label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.actress.setFixedHeight(550)
        self.label.setFixedHeight(550)
        self.actress_layout = VFlowLayout(self.actress, spacing=5)  # 这个要改
        self.label_layout = VFlowLayout(self.label, spacing=5)  # 这个要改

        self.label_layout.addWidget(self.label_tag)

        self.heart = HeartLabel()
        self.trash = IconPushButton(
            icon_name="trash_2",
            icon_size=24,
            out_size=32,
            hoverable=True,
            inverted=True,
        )
        self.modify = IconPushButton(
            icon_name="square_pen",
            icon_size=24,
            out_size=32,
            hoverable=True,
            inverted=True,
        )
        self.watch = IconPushButton(
            icon_name="tv", icon_size=24, out_size=32, hoverable=True, inverted=True
        )

        tool_v_layout = QVBoxLayout()
        tool_v_layout.addWidget(self.heart, 0, Qt.AlignCenter)
        tool_v_layout.addWidget(self.trash, 0, Qt.AlignCenter)
        tool_v_layout.addWidget(self.modify, 0, Qt.AlignCenter)
        tool_v_layout.addWidget(self.watch, 0, Qt.AlignCenter)
        tool_v_layout.addStretch()

        serialnumber_v_layout = QVBoxLayout()

        serialnumber_v_layout.addWidget(self.serial_number_label, 0, Qt.AlignLeft)
        serialnumber_v_layout.addWidget(self.serial_number, 0, Qt.AlignLeft)
        serialnumber_v_layout.addWidget(self.release_date_label, 0, Qt.AlignLeft)
        serialnumber_v_layout.addWidget(self.release_date, 0, Qt.AlignLeft)
        serialnumber_v_layout.addStretch()

        director_v_layout = QVBoxLayout()
        director_v_layout.addWidget(self.director_label)
        director_v_layout.addWidget(self.director)
        director_v_layout.addWidget(self.studio_label)
        director_v_layout.addWidget(self.studio)
        director_v_layout.addStretch()

        # 内容行：所有列打包到一个容器，容器只占内容宽度，避免被拉宽产生列间空隙（透明容器）
        content_row = TransparentWidget(self)
        content_row.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        content_row.setFixedHeight(550)

        row_layout = QHBoxLayout(content_row)
        row_layout.setSpacing(5)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addStretch()  # 把整块内容压到右侧
        row_layout.addLayout(tool_v_layout)
        row_layout.addWidget(self.label)
        row_layout.addWidget(self.actress)
        row_layout.addLayout(director_v_layout)
        row_layout.addWidget(self.story, 0, Qt.AlignLeft | Qt.AlignTop)
        row_layout.addLayout(serialnumber_v_layout)
        row_layout.addWidget(self.title, 0, Qt.AlignLeft | Qt.AlignTop)

        # 最外侧：左侧弹性空间 + 内容行
        mainlayout = QHBoxLayout(self)
        mainlayout.setSpacing(0)
        mainlayout.setContentsMargins(0, 0, 0, 0)
        mainlayout.addStretch()
        mainlayout.addWidget(content_row)

        self.signal_connect()

    def signal_connect(self):
        self.heart.clicked.connect(self.on_clicked_heart)
        self.trash.clicked.connect(self.on_clicked_delete)
        self.modify.clicked.connect(self.on_modify_clicked)
        self.watch.clicked.connect(self.show_video_menu)

    def update_actress(self, actress_list: list[dict], actor_list: list[dict]):
        """更新女优出现的按钮，动态的

        Args:
            actress_list:字典列表

        """
        # actress_list 是 [{"actress_id": ..., "actress_name": ...}, ...]

        # 1. 先清空所有的按钮
        while self.actress_layout.count():
            item: QLayoutItem = self.actress_layout.takeAt(0)
            widget: QWidget = item.widget()
            if widget:
                widget.deleteLater()

        if actress_list is None:
            # self.actress.deleteLater()
            return

        label_actress = TokenVLabel(
            "女优",
            text_color="#FFFFFF",
            background_color="#00000000",
            border_color="#FFFFFF",
        )
        self.actress_layout.addWidget(label_actress)
        # 2. 动态创建按钮并添加女优列表
        for actress in actress_list:
            actress_id = actress["actress_id"]
            name = actress["actress_name"]
            label = VerticalActressLabel(actress_id, name, background_color="#FFFFFF")

            self.actress_layout.addWidget(label)

        # 处理男优空值的问题
        if actor_list is None:
            return
        # 添加男优的标签
        label_actor = TokenVLabel(
            "男优",
            text_color="#FFFFFF",
            background_color="#00000000",
            border_color="#FFFFFF",
        )
        self.actress_layout.addWidget(label_actor)

        for actor in actor_list:
            actor_id = actor["actor_id"]
            name = actor["actor_name"]
            label = VerticalActorLabel(actor_id, name, background_color="#FFFFFF")
            # label.clicked.connect(self.on_actor_clicked)
            self.actress_layout.addWidget(label)

    def update_tag(self, tag_list: list[dict]):
        """更新tag"""
        # 1. 先清空之前按钮
        while self.label_layout.count() > 1:
            item: QLayoutItem = self.label_layout.takeAt(1)
            widget: QWidget = item.widget()
            if widget:
                widget.deleteLater()

        # 2. 动态创建按钮并添加
        # logging.debug(tag_list)
        for tag in tag_list:
            label = VerticalTagLabel(
                tag["tag_id"], tag["tag_name"], tag["color"], tag["detail"]
            )
            self.label_layout.addWidget(label)

    def set_info(self, info: dict):
        """更新信息"""
        if info["cn_title"] is not None:
            if len(info["cn_title"]) <= 35:
                titletext = info["cn_title"]
            else:
                titletext = info["cn_title"][:35] + "..."
        else:
            titletext = ""
        if info["cn_story"] is not None:
            if len(info["cn_story"]) <= 120:
                storytext = info["cn_story"]
            else:
                storytext = info["cn_story"][:120] + "..."
        else:
            storytext = ""

        self.title.setText(titletext)
        self.story.setText(storytext)
        self.release_date.setTextDynamic(info["release_date"])
        self.serial_number.setTextDynamic(info["serial_number"])
        self.director.setTextDynamic(info["director"])
        if info["studio_name"] is not None:
            self.studio.setTextDynamic(info["studio_name"])
        else:
            self.studio.setTextDynamic("----")

    @Slot()
    def on_clicked_delete(self):
        from core.database.update import mark_delete

        if self._work_id is None:
            return
        if self.msg.ask_yes_no("确认删除", "确定要删除该作品吗？"):
            if mark_delete(self._work_id):
                self.msg.show_info("成功", "已标记删除")

    @Slot()
    def on_clicked_heart(self):
        from core.database.insert import insert_liked_work
        from core.database.delete import delete_favorite_work

        if self.heart.get_statue():
            """添加到喜欢"""
            insert_liked_work(self._work_id)
        else:
            """删除"""
            delete_favorite_work(self._work_id)
        from controller.GlobalSignalBus import global_signals

        global_signals.like_work_changed.emit()

    @Slot()
    def on_modify_clicked(self):
        """点击了修改按钮"""
        # from controller.GlobalSignalBus import global_signals
        if self._work_id is None:
            return
        # global_signals.modify_work_clicked.emit(self.serial_number.text().strip())
        serial_number = self.serial_number.text().strip()
        from ui.navigation.router import Router

        Router.instance().push("work_edit", serial_number=serial_number)

    @Slot()
    def show_video_menu(self):
        """点击按钮后即时弹出菜单供选择"""
        from pathlib import Path
        from utils.utils import find_video, play_video
        from config import get_video_path

        self.video_paths = find_video(
            self.serial_number.text().strip(), get_video_path()
        )
        if not self.video_paths:
            self.msg.show_info("提示", "没有可播放的视频")
            return

        # 创建 QMenu（轻量、非模态、即时弹出）
        menu = QMenu(self)

        for path in self.video_paths:
            action = menu.addAction(path.name)  # 显示文件名（更友好）
            action.setData(str(path))  # 存储完整路径

        # 在按钮位置弹出菜单
        button_pos = self.watch.mapToGlobal(self.watch.rect().bottomLeft())
        chosen_action = menu.exec(button_pos)

        if chosen_action:
            selected_path = Path(chosen_action.data())
            play_video(selected_path)

    def update(self, work_id):
        from core.database.query import (
            get_workinfo_by_workid,
            get_actress_from_work_id,
            get_worktaginfo_by_workid,
            query_work,
            get_actor_from_work_id,
        )

        self._work_id = work_id
        self.set_info(get_workinfo_by_workid(work_id))
        self.update_actress(
            get_actress_from_work_id(work_id), get_actor_from_work_id(work_id)
        )
        self.update_tag(get_worktaginfo_by_workid(work_id))

        # 更新爱心状态
        if query_work(work_id):
            self.heart.set_statue(True)
        else:
            self.heart.set_statue(False)


class SingleWork(QWidget):

    def __init__(self):
        super().__init__()
        # 父层不填充背景，WorkInfo 的透明才能透出下面的 Cover / GradientOverlay
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

        self._h = self.height()
        # 背景图片层
        self.bg_label = Cover(self)

        # 在 self.bg_label 上添加透明度效果
        self.opacity_effect = QGraphicsOpacityEffect(self.bg_label)
        self.bg_label.setGraphicsEffect(self.opacity_effect)

        # 这个是上层阴影效果
        self.gradient_overlay = GradientOverlay(self)
        self.gradient_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.work_info = WorkInfo(self)

        self.bg_label.lower()
        self.gradient_overlay.raise_()
        self.work_info.raise_()

        self.hlayout = QHBoxLayout()
        mainlayout = QVBoxLayout(self)
        mainlayout.addStretch()
        mainlayout.addLayout(self.hlayout)
        mainlayout.addStretch()
        self.hlayout.addStretch()
        self.hlayout.addWidget(self.work_info)
        self.hlayout.setContentsMargins(
            0, 0, self._h * 0.8, 0
        )  # 这里的定位使用layout里的margin+stretch定位
        mainlayout.setContentsMargins(0, 0, 0, 0)

    def resizeEvent(self, event):
        self._h = self.height()
        self.hlayout.setContentsMargins(0, 0, self._h * 0.8, 0)
        rect = self.rect()
        self.bg_label.setGeometry(rect)
        self.gradient_overlay.setGeometry(rect)


class SingleWorkPage(LazyWidget):
    """单个作品的展示页面，这个才是最主要的，总装在这里"""

    def __init__(self):
        super().__init__()

    def _lazy_load(self):
        logging.info("----------加载单独作品界面----------")
        mainlayout = QVBoxLayout(self)
        mainlayout.setContentsMargins(0, 0, 0, 0)
        # mainlayout.addSpacing(70)

        self.cover = SingleWork()

        mainlayout.addWidget(self.cover)

    def update(self, work_id):
        """传入一个work_id并更新整个页面"""
        from core.database.query import get_cover_image_url

        self.cover.work_info.update(work_id)
        self.cover.bg_label.set_cover(get_cover_image_url(work_id))
