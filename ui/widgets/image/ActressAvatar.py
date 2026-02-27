
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import Qt,Signal,QTimer
import logging

from darkeye_ui.components.oct_image import OctImage

class ActressAvatar(OctImage):
    '''正八边形的头像框，加上发射跳转信号的功能'''

    def __init__(self,image_path: str,actress_id:int, parent=None):
        super().__init__(image_path,parent)
        self._d=150#直径

        self._actress_id=actress_id

    def mouseReleaseEvent(self, event: QMouseEvent):
        from ui.navigation.router import Router
        
        if event.button() == Qt.MouseButton.RightButton:
            QTimer.singleShot(0, lambda: Router.instance().push("actress_edit", actress_id=self._actress_id))
            
        if event.button() == Qt.MouseButton.LeftButton:
            logging.debug(f"准备跳转女优界面：ID:{self._actress_id}")
            QTimer.singleShot(0, lambda: Router.instance().push("single_actress", actress_id=self._actress_id))

