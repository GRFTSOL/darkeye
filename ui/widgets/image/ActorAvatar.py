from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import Qt, Signal, QTimer
import logging

from ui.navigation.router import Router
from darkeye_ui.components.oct_image import OctImage

from ui.widgets.image.ActressAvatarDropWidget import ActressAvatarDropWidget


class ActorAvatarDropWidget(ActressAvatarDropWidget):
    """编辑页用的男优头像拖放区：与 CoverDropWidget 相同的外框自适应，数据目录为男优图。"""

    def __init__(self, aspect_ratio: float = 1.0):
        super().__init__("actor", aspect_ratio=aspect_ratio)


class ActorAvatar(OctImage):
    """正八边形的头像框，加上发射跳转信号的功能"""

    def __init__(self, image_path: str, actor_id: int, parent=None):
        super().__init__(image_path, parent)
        self._d = 150  # 直径
        # self.setStyleSheet("border: 1px solid red; border-radius: 4px;")
        self._actor_id = actor_id
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent):
        from controller.global_signal_bus import global_signals

        if event.button() == Qt.MouseButton.RightButton:
            # QTimer.singleShot(0, lambda: global_signals.modify_actor_clicked.emit(self._actor_id))
            # 使用路由替代信号跳转
            QTimer.singleShot(
                0, lambda: Router.instance().push("actor_edit", actor_id=self._actor_id)
            )
        if event.button() == Qt.MouseButton.LeftButton:
            logging.debug(f"准备跳转男优界面：ID:{self._actor_id}")
            # QTimer.singleShot(0, lambda: global_signals.actor_clicked.emit(self._actor_id))
            # 使用路由替代信号跳转
            QTimer.singleShot(
                0, lambda: Router.instance().push("mutiwork", actor_id=self._actor_id)
            )
