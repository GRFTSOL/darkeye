"""
阶段一：PaneWidget = TabBar + StackedWidget，支持 Tab 顺序拖拽与关闭。
测试文件在tests/test_pane_widget.py
"""

from typing import Callable

from PySide6.QtWidgets import (
    QTabBar,
    QStackedWidget,
    QWidget,
    QVBoxLayout,
    QToolButton,
)
from PySide6.QtCore import Signal, Qt, QPoint, QMimeData, QSize, QByteArray, QTimer
from PySide6.QtGui import QDrag, QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

MIME_TYPE_TAB = "application/x-workspace-demo-tab"

_DRAG_THRESHOLD = 8

# 仅图标且不可关闭的 tab：只显示图标时的宽度与高度（留出 margin 保证图标完整显示）
_ICON_ONLY_TAB_NO_CLOSE_WIDTH = 40
_ICON_ONLY_TAB_NO_CLOSE_HEIGHT = 32

# 关闭按钮图标（lucide x），硬编码避免依赖外部文件
_SVG_CLOSE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
    'fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>'
    "</svg>"
)

_close_icon_cache: QIcon | None = None


def _close_icon() -> QIcon:
    """从硬编码的 SVG 渲染为 QIcon（带缓存）。"""
    global _close_icon_cache
    if _close_icon_cache is not None:
        return _close_icon_cache
    renderer = QSvgRenderer(QByteArray(_SVG_CLOSE.encode("utf-8")))
    if not renderer.isValid():
        _close_icon_cache = QIcon()
        return _close_icon_cache
    size = 24
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    _close_icon_cache = QIcon(QPixmap.fromImage(image))
    return _close_icon_cache


class ClosableTabBar(QTabBar):
    """支持关闭按钮的 TabBar；关闭时发出 tab_close_requested(index)，是否为空由 PaneWidget 判断。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(True)
        self.setTabsClosable(True)
        self.setExpanding(False)
        self.setObjectName("WorkspaceDemoTabBar")
        self.currentChanged.connect(self._update_close_buttons_visibility)

    def _on_close_button_clicked(self) -> None:
        """根据被点击的按钮找到对应 tab 并发出关闭请求。"""
        sender = self.sender()
        if not isinstance(sender, QToolButton):
            return
        for i in range(self.count()):
            if self.tabButton(i, QTabBar.RightSide) is sender:
                self.tabCloseRequested.emit(i)
                return

    def tabInserted(self, index: int) -> None:
        """插入 tab 时用自定义 QToolButton 替换默认关闭按钮，保证 SVG 图标正确显示。"""
        super().tabInserted(index)
        # 用自定义按钮替换 Qt 默认按钮，避免样式/主题覆盖图标
        close_btn = QToolButton(self)
        close_btn.setIcon(_close_icon())
        close_btn.setIconSize(QSize(16, 16))
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self._on_close_button_clicked)
        self.setTabButton(index, QTabBar.RightSide, close_btn)
        self._update_close_buttons_visibility()

    def tabSizeHint(self, index: int):
        """仅图标 pane 且该 content 不可关闭时，tab 仅图标、宽度缩小并居中。"""
        pane = self.parent()
        if not isinstance(pane, PaneWidget) or not getattr(pane, "_icon_only", False):
            return super().tabSizeHint(index)
        content_id = self.tabData(index)
        if not isinstance(content_id, str) or pane.is_content_closeable(content_id):
            return super().tabSizeHint(index)
        return QSize(_ICON_ONLY_TAB_NO_CLOSE_WIDTH, _ICON_ONLY_TAB_NO_CLOSE_HEIGHT)

    def _update_close_buttons_visibility(self) -> None:
        """按 closeable 与当前 tab、hover 控制关闭按钮尺寸、可见性与样式；关闭图标居中。"""
        pane = self.parent()
        is_pane = isinstance(pane, PaneWidget)
        current = self.currentIndex()
        icon = _close_icon()
        for i in range(self.count()):
            btn = self.tabButton(i, QTabBar.RightSide)
            if not isinstance(btn, QToolButton):
                continue
            content_id = self.tabData(i)
            closeable = (
                pane.is_content_closeable(content_id)
                if is_pane and isinstance(content_id, str)
                else True
            )
            if closeable:
                btn.setFixedSize(20, 20)
                btn.setVisible(True)
                btn.setEnabled(True)
                btn.setIcon(icon)
                btn.setIconSize(QSize(16, 16))
                base_style = (
                    "QToolButton { padding: 0; margin: 0; border: none; "
                    "background: transparent; min-width: 20px; min-height: 20px; }\n"
                )
            else:
                # 不可关闭时完全取消占位：既隐藏按钮，也移除最小尺寸约束
                btn.setFixedSize(0, 0)
                btn.setVisible(False)
                btn.setEnabled(False)
                base_style = (
                    "QToolButton { padding: 0; margin: 0; border: none; "
                    "background: transparent; min-width: 0px; min-height: 0px; }\n"
                )
            if i == current:
                btn.setStyleSheet(
                    base_style
                    + """
                    QToolButton { opacity: 1; }
                    QToolButton:hover { background-color: #e0e0e0; border-radius: 2px; }
                    QToolButton:pressed { background-color: #c0c0c0; }
                    """
                )
            else:
                btn.setStyleSheet(
                    base_style
                    + """
                    QToolButton { opacity: 0; }
                    QToolButton:hover { background-color: #e0e0e0; border-radius: 2px; opacity: 1; }
                    QToolButton:pressed { background-color: #c0c0c0; opacity: 1; }
                    """
                )


class DraggableTabBar(ClosableTabBar):
    """支持跨窗格拖拽的 TabBar。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_start_pos: QPoint | None = None
        self._drag_source_content_id: str | None = (
            None  # 拖动开始时记录的 tab，避免栏内换位后取错
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.position().toPoint()
            self._drag_source_content_id = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return
        if (event.buttons() & Qt.LeftButton) == 0:
            super().mouseMoveEvent(event)
            return
        diff = event.position().toPoint() - self._drag_start_pos
        if diff.manhattanLength() < _DRAG_THRESHOLD:
            super().mouseMoveEvent(event)
            return

        idx = self.tabAt(self._drag_start_pos)
        if idx < 0:
            super().mouseMoveEvent(event)
            return

        # 首次超过阈值时固定被拖 tab 的 content_id，避免栏内换位后 tabAt(_drag_start_pos) 指到别的 tab
        if self._drag_source_content_id is None:
            cid = self.tabData(idx)
            self._drag_source_content_id = cid if isinstance(cid, str) else None

        # 若仍停留在 Tab 栏内，交由 Qt 内置 setMovable(True) 处理同一窗格内的 Tab 重排
        pos = event.position().toPoint()
        if self.rect().contains(pos):
            super().mouseMoveEvent(event)
            return

        # 鼠标已移出 Tab 栏：先让 Qt 处理事件以结束其内部拖拽，避免 Tab 卡住
        super().mouseMoveEvent(event)
        # 用开始时记录的 content_id 取当前索引/标题，再启动跨窗格拖拽
        pane = self.parent()
        if not isinstance(pane, PaneWidget) or not self._drag_source_content_id:
            self._drag_start_pos = None
            self._drag_source_content_id = None
            return
        content_id = self._drag_source_content_id
        idx = pane._index_for_content_id(content_id)
        if idx is None:
            self._drag_start_pos = None
            self._drag_source_content_id = None
            return
        title = self.tabText(idx) or self.tabToolTip(idx) or ""

        # 通知 overlay 开始接收拖放（在 exec 前激活，使后续 DragEnter/Move/Drop 进 overlay）
        drag_start_cb = getattr(pane, "_drag_start_callback", None)
        if callable(drag_start_cb):
            drag_start_cb()

        mime = QMimeData()
        mime.setData(
            MIME_TYPE_TAB,
            f"{content_id}\n{pane.pane_id}\n{title}".encode("utf-8"),
        )
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)
        # 拖拽结束（无论 drop 或取消）后恢复 overlay 穿透，避免一直拦截鼠标
        drag_end_cb = getattr(pane, "_drag_end_callback", None)
        if callable(drag_end_cb):
            drag_end_cb()
        self._drag_start_pos = None
        self._drag_source_content_id = None


class PaneWidget(QWidget):
    """窗格 = Tab 栏 + 内容区（StackedWidget），每个 Tab 对应一个内容页。"""

    paneEmpty = Signal(object)  # 参数为 self（被关闭的 PaneWidget）

    def __init__(self, pane_id: str = "", parent=None):
        super().__init__(parent)
        self._pane_id = pane_id or id(self).__hex__()
        self._icon_only = False
        self._get_content_closeable: Callable[[str], bool] | None = (
            None  # 由 WorkspaceManager 设置，单一数据源
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tab_bar = DraggableTabBar(self)
        self._tab_bar.tabCloseRequested.connect(self._on_tab_close_requested)
        layout.addWidget(self._tab_bar)

        self._stack = QStackedWidget(self)
        layout.addWidget(self._stack, 1)

        self._tab_bar.currentChanged.connect(self._stack.setCurrentIndex)
        self._tab_bar.tabMoved.connect(self._on_tab_moved)

        self._drag_start_callback = None  # 跨窗格拖拽开始时调用，用于激活 overlay
        self._drag_end_callback = None  # 跨窗格拖拽结束时调用，用于恢复 overlay 穿透

    @property
    def pane_id(self) -> str:
        return self._pane_id

    def set_icon_only(self, icon_only: bool) -> None:
        """设置是否仅显示图标（不显示 Tab 文字）。TabBar 样式与普通模式一致。"""
        if self._icon_only == icon_only:
            return
        self._icon_only = icon_only
        for i in range(self._tab_bar.count()):
            if icon_only:
                title = self._tab_bar.tabText(i)
                self._tab_bar.setTabToolTip(i, title)
                self._tab_bar.setTabText(i, "")
            else:
                title = self._tab_bar.tabToolTip(i) or self._tab_bar.tabText(i)
                self._tab_bar.setTabText(i, title)
        self._refresh_tab_bar_layout()

    def _index_for_content_id(self, content_id: str) -> int | None:
        """根据 content_id 在 TabBar 中的索引，不存在返回 None。"""
        for i in range(self._tab_bar.count()):
            if self._tab_bar.tabData(i) == content_id:
                return i
        return None

    def is_content_closeable(self, content_id: str) -> bool:
        """该 content 是否可关闭（用于 TabBar 关闭按钮尺寸与可见性）。由 Manager 回调查询，未设置时默认 True。"""
        if self._get_content_closeable is not None:
            return self._get_content_closeable(content_id)
        return True

    def _refresh_tab_bar_layout(self) -> None:
        """强制 TabBar 与窗格重新计算布局，解决移动 tab 后尺寸未及时更新的问题。"""
        self._tab_bar.updateGeometry()
        self._tab_bar.update()
        self.updateGeometry()
        self.update()

    def add_content(
        self,
        content_id: str,
        title: str,
        widget: QWidget,
        icon: QIcon | None = None,
    ) -> None:
        """添加一个内容页，若已存在则更新标题与图标。closeable 由 set_get_content_closeable 回调查询（Manager 为单一数据源）。"""
        idx = self._index_for_content_id(content_id)
        if idx is not None:
            old_w = self._stack.widget(idx)
            self._tab_bar.setTabText(idx, "" if self._icon_only else title)
            if self._icon_only:
                self._tab_bar.setTabToolTip(idx, title)
            if icon is not None:
                self._tab_bar.setTabIcon(idx, icon)
            else:
                self._tab_bar.setTabIcon(idx, QIcon())
            if old_w:
                self._stack.removeWidget(old_w)
            self._stack.insertWidget(idx, widget)
            self._tab_bar.setCurrentIndex(idx)
            self._stack.setCurrentIndex(idx)
            self._tab_bar._update_close_buttons_visibility()
            self._refresh_tab_bar_layout()
            QTimer.singleShot(0, self._refresh_tab_bar_layout)
            return
        idx = self._stack.addWidget(widget)
        display_title = "" if self._icon_only else title
        if icon is not None:
            self._tab_bar.addTab(icon, display_title)
        else:
            self._tab_bar.addTab(display_title)
        if self._icon_only:
            self._tab_bar.setTabToolTip(idx, title)
        self._tab_bar.setTabData(idx, content_id)
        self._tab_bar.setCurrentIndex(idx)
        self._stack.setCurrentIndex(idx)
        self._tab_bar._update_close_buttons_visibility()
        self._refresh_tab_bar_layout()
        QTimer.singleShot(0, self._refresh_tab_bar_layout)

    def _on_tab_close_requested(self, index: int) -> None:
        """Tab 关闭请求：按 content_id 移除内容，空则发出 pane_empty（empty 判断在此统一处理）。"""
        content_id = self._tab_bar.tabData(index)
        if content_id is not None:
            self.remove_content(content_id)

    def remove_content(self, content_id: str) -> bool:
        """移除内容页，返回是否成功。当 widget 已被移走（如先 add 到别窗格再 remove）时只移除 tab，不从 stack 移除。"""
        idx = self._index_for_content_id(content_id)
        if idx is None:
            return False
        # 若 stack 数量少于 tab 数量，说明对应 widget 已被 reparent 走（如拖拽分裂时先 add 后 remove），只移 tab
        only_remove_tab = self._stack.count() < self._tab_bar.count()
        self._tab_bar.removeTab(idx)
        if not only_remove_tab:
            w = self._stack.widget(idx)
            if w:
                self._stack.removeWidget(w)
        self._refresh_tab_bar_layout()
        QTimer.singleShot(0, self._refresh_tab_bar_layout)
        if self._tab_bar.count() == 0:
            self.paneEmpty.emit(self)
        return True

    def current_content_id(self) -> str | None:
        """当前选中 Tab 对应的 content_id。"""
        idx = self._tab_bar.currentIndex()
        if idx < 0:
            return None
        cid = self._tab_bar.tabData(idx)
        return cid if isinstance(cid, str) else None

    def content_ids(self) -> list[str]:
        """所有内容 ID 列表。"""
        return [
            cid
            for i in range(self._tab_bar.count())
            if (cid := self._tab_bar.tabData(i)) is not None
        ]

    def content_count(self) -> int:
        return self._tab_bar.count()

    def _on_tab_moved(self, from_index: int, to_index: int) -> None:
        """Tab 栏内拖拽重排时，同步 StackedWidget 顺序。"""
        w = self._stack.widget(from_index)
        if w is None:
            return
        self._stack.removeWidget(w)
        self._stack.insertWidget(to_index, w)

    def get_content_title(self, content_id: str) -> str:
        """根据 content_id 获取 Tab 标题（tabText 或 tabToolTip）。"""
        idx = self._index_for_content_id(content_id)
        if idx is None:
            return ""
        return self._tab_bar.tabText(idx) or self._tab_bar.tabToolTip(idx) or ""

    def get_content_widget(self, content_id: str) -> QWidget | None:
        """根据 content_id 获取内容 widget。"""
        idx = self._index_for_content_id(content_id)
        if idx is None:
            return None
        return self._stack.widget(idx)

    def get_icon_for_content(self, content_id: str) -> QIcon | None:
        """根据 content_id 获取关联的 Tab 图标（从 TabBar 按索引读取，无需单独缓存）。"""
        idx = self._index_for_content_id(content_id)
        if idx is None:
            return None
        icon = self._tab_bar.tabIcon(idx)
        return icon if not icon.isNull() else None

    def set_drag_start_callback(self, callback: Callable[[], None] | None) -> None:
        """设置跨窗格拖拽开始时的回调（在 Tab 栏发起 QDrag.exec 前调用），用于激活 overlay。"""
        self._drag_start_callback = callback

    def set_drag_end_callback(self, callback: Callable[[], None] | None) -> None:
        """设置跨窗格拖拽结束时的回调（在 QDrag.exec 返回后调用），用于恢复 overlay 穿透。"""
        self._drag_end_callback = callback

    def set_get_content_closeable(self, callback: Callable[[str], bool] | None) -> None:
        """设置按 content_id 查询是否可关闭的回调（由 WorkspaceManager 注入，closeable 单一数据源）。"""
        self._get_content_closeable = callback
