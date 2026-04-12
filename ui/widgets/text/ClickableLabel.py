from PySide6.QtWidgets import QApplication, QSizePolicy
from PySide6.QtCore import Qt, Signal, QSize, Slot, QThreadPool
from PySide6.QtGui import QMouseEvent

from darkeye_ui.components.label import Label
from darkeye_ui.components.toast_notification import Toast


class ClickableLabel(Label):
    """可点击并复制内容到剪贴板，并以 Toast 提示的 label 控件，
    专门给那些名字使用，提供复制功能，还有右键跳转功能。
    样式由主题 QLabel#DesignLabel 驱动，会随主题变色；若在外部对本品 setStyleSheet，避免写死 color，否则会覆盖主题颜色。"""

    clicked = Signal()

    def __init__(self, text="xxx", actress_jump=False, parent=None):
        if text is None:
            text = ""
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.actress_jump = actress_jump
        self.setWordWrap(False)  # 禁止换行

    def mouseReleaseEvent(self, event: QMouseEvent):
        from core.crawler.jump import jump_minnanoav
        from core.database.query import exist_actress

        if event.button() == Qt.LeftButton:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.text())
            self.show_copy_tip()
        if self.actress_jump:
            if event.button() == Qt.RightButton:
                # 跳转功能
                jump_minnanoav(self.text())
                """
                #合并女优的性名链条的问题，这个后面再解决，现在直插没有问题，但是合并链条就有问题
                id=exist_actress(self.text())
                if id:
                    from core.crawler.SearchActressInfo import SearchSingleActressInfo
                    #SearchSingleActressInfo(id,self.text())
                    self.search_actress_info(id)
        """
        super().mouseReleaseEvent(event)


    @Slot(object)
    def on_result(self, result: str):  # Qsignal回传信息
        pass

    def sizeHint(self):
        # 获取文本所需大小
        fm = self.fontMetrics()
        text_width = fm.horizontalAdvance(self.text())
        text_height = fm.height()
        return QSize(text_width, text_height)

    def show_copy_tip(self) -> None:
        Toast.show_success(self.window(), "复制成功", duration_ms=2000)
