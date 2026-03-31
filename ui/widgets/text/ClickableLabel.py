from PySide6.QtWidgets import QApplication, QSizePolicy
from PySide6.QtCore import Qt, Signal, QTimer, QPoint, QSize, Slot, QThreadPool
from PySide6.QtGui import QMouseEvent
from controller.global_signal_bus import global_signals
from darkeye_ui.components.label import Label


class ClickableLabel(Label):
    """可点击并复制内容到剪贴板，并且有提示的 label 控件，
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
            # global_signals.statusMsgChanged.emit("复制文本到剪贴板")
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

    def search_actress_info(self, id):
        # 开始后台线程
        from core.crawler.minnanoav import SearchSingleActressInfo
        from core.crawler.worker import Worker, wire_worker_finished

        worker = Worker(
            lambda id=id: SearchSingleActressInfo(id, self.text())
        )  # 传一个函数名进去
        wire_worker_finished(worker, self.on_result)
        QThreadPool.globalInstance().start(worker)

    @Slot(object)
    def on_result(self, result: str):  # Qsignal回传信息
        pass

    def sizeHint(self):
        # 获取文本所需大小
        fm = self.fontMetrics()
        text_width = fm.horizontalAdvance(self.text())
        text_height = fm.height()
        return QSize(text_width, text_height)

    def show_copy_tip(self):
        # 获取主窗口
        main_window = self.window()

        # 创建提示标签（设为 main_window 的子控件）
        self._copy_tip = Label("复制成功", main_window)
        self._copy_tip.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self._copy_tip.setAttribute(Qt.WA_TranslucentBackground)
        self._copy_tip.setStyleSheet(
            """
            QLabel {
                font-weight: bold;
                font-size: 20px;
                padding: 10px 20px;
                border-radius: 12px;
            }
        """
        )

        self._copy_tip.adjustSize()

        # 计算位置：在整个窗口底部中央
        parent_rect = main_window.rect()
        center_x = parent_rect.width() // 2 - self._copy_tip.width() // 2
        bottom_y = parent_rect.height() - self._copy_tip.height() - 30  # 离底部 30px

        # 转为全局坐标
        global_pos = main_window.mapToGlobal(QPoint(center_x, bottom_y))
        self._copy_tip.move(global_pos)
        self._copy_tip.show()

        # 3秒后关闭并清除
        QTimer.singleShot(3000, self._copy_tip.close)
        QTimer.singleShot(3100, lambda: setattr(self, "_copy_tip", None))
