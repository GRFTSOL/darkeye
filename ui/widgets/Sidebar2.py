from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QVBoxLayout, QWidget

from config import ICONS_PATH
from app_context import get_theme_manager
from darkeye_ui.components import ChamferButton
from darkeye_ui.design.icon import BUILTIN_ICONS


def _resolve_icon(icon_name: str | None):
    """将 menu_defs 的 icon_name 解析为 ChamferButton 的 icon_name / icon_path。
    .svg 结尾的：从 config 取 ICONS_PATH 拼成完整路径；否则尝试按 builtin 键匹配。
    """
    if not icon_name:
        return None, None
    if icon_name.endswith(".svg"):
        return None, ICONS_PATH / icon_name
    if icon_name in BUILTIN_ICONS:
        return icon_name, None
    return None, ICONS_PATH / icon_name


class Sidebar2(QWidget):
    """
    简化版侧边栏：
    - 只保留一列八边形按钮
    - 所有按钮在侧边栏中垂直居中
    - hover 显示 tooltip，点击发射 menu_id
    - 尽量兼容现有 Sidebar 的接口（itemClicked / selectedChanged / select 等）
    """

    itemClicked = Signal(str)
    selectedChanged = Signal(str)

    def __init__(self, menu_defs=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # 与旧 Sidebar 接口保持一致
        if menu_defs is None:
            self.menu_defs = []
        else:
            self.menu_defs = menu_defs

        self._buttons: dict[str, ChamferButton] = {}
        self._current_id: str | None = None

        # 背景：用 paintEvent 绘制八边形（直倒角），不用圆角
        self.setFixedWidth(72)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("Sidebar2 { background-color: transparent; }")
        self.setAutoFillBackground(False)

        # 布局：按钮整体垂直居中
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addStretch(1)
        for mid, text, icon_name in self.menu_defs:
            iname, ipath = _resolve_icon(icon_name)
            btn = ChamferButton(
                text=text,
                icon_name=iname,
                icon_path=ipath,
                out_size=40,
                chamfer_ratio=0.5,
                menu_id=mid,
                parent=self,
            )
            btn.clicked.connect(lambda _=False, m=mid: self._on_button_clicked(m))
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)
            self._buttons[mid] = btn
        layout.addStretch(1)

        # 默认选中第一个
        if self.menu_defs:
            first_id = self.menu_defs[0][0]
            if first_id in self._buttons:
                self._current_id = first_id
                self._buttons[first_id].set_selected(True)

        # 令牌驱动：背景色随主题切换
        theme_mgr = get_theme_manager()
        if theme_mgr is not None:
            theme_mgr.themeChanged.connect(self.update)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        """绘制侧边栏整体背景为八边形（直倒角），上下留白 20px，左右各 5px。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 上下空白 20px，左右各 5px
        r = self.rect().adjusted(5, 20, -5, -20)
        w, h = r.width(), r.height()
        x, y = r.x(), r.y()
        chamfer = 12

        path = QPainterPath()
        path.moveTo(x + chamfer, y)
        path.lineTo(x + w - chamfer, y)
        path.lineTo(x + w, y + chamfer)
        path.lineTo(x + w, y + h - chamfer)
        path.lineTo(x + w - chamfer, y + h)
        path.lineTo(x + chamfer, y + h)
        path.lineTo(x, y + h - chamfer)
        path.lineTo(x, y + chamfer)
        path.closeSubpath()

        # 背景色由令牌控制（color_bg_input 用于侧边栏等次级面板）
        color_str = "#D4ECD7"  # 回退默认
        theme_mgr = get_theme_manager()
        if theme_mgr is not None:
            tokens = theme_mgr.tokens()
            color_str = getattr(tokens, "color_bg_input", color_str)
        c = QColor(color_str)
        painter.setPen(QPen(c, 1))
        painter.setBrush(QBrush(c))
        painter.drawPath(path)

    # --------- 兼容接口 ---------
    def _on_button_clicked(self, menu_id: str) -> None:
        # 与旧 Sidebar 一样：点击当前按钮再次会取消选中，并发射空 selectedChanged
        if self._current_id == menu_id:
            btn = self._buttons.get(menu_id)
            if btn:
                btn.set_selected(False)
            self._current_id = None
            self.selectedChanged.emit("")
        else:
            prev_btn = self._buttons.get(self._current_id or "")
            if prev_btn:
                prev_btn.set_selected(False)

            new_btn = self._buttons.get(menu_id)
            if new_btn:
                new_btn.set_selected(True)
            self._current_id = menu_id
            self.selectedChanged.emit(menu_id)

        self.itemClicked.emit(menu_id)

    def get_selected_id(self):
        return self._current_id

    def clear_selection(self) -> None:
        if self._current_id is None:
            return
        btn = self._buttons.get(self._current_id)
        if btn:
            btn.set_selected(False)
        self._current_id = None
        self.selectedChanged.emit("")

    def select(self, menu_id: str) -> None:
        if self._current_id == menu_id:
            return

        prev_btn = self._buttons.get(self._current_id or "")
        if prev_btn:
            prev_btn.set_selected(False)

        new_btn = self._buttons.get(menu_id)
        if new_btn:
            new_btn.set_selected(True)
            self._current_id = menu_id
            self.selectedChanged.emit(menu_id)

    def toggle_menu(self) -> None:
        """
        为兼容旧 Sidebar 接口而保留的空方法。
        Sidebar2 不再提供展开/折叠动画。
        """
        pass

