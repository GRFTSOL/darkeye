# darkeye_ui/components/sidebar2.py - 侧边栏导航组件
"""侧边栏：八边形按钮列，hover 呼出 tooltip，点击选中，令牌驱动。"""
from pathlib import Path
from typing import Optional, Sequence, Union, TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .._logging import get_logger, warn_once
from ..design.theme_context import resolve_theme_manager
from .callout_tooltip import CalloutTooltip
from .chamfer_button import ChamferButton
from ..design.icon import BUILTIN_ICONS

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager

# menu_defs: [(menu_id, text, icon_name), ...]
# icon_name: 内置键（如 "mars"）或 .svg 文件名 / 其他文件名，需 icons_base_path
MenuDef = tuple[str, str, str]
logger = get_logger(__name__)


def _resolve_icon(
    icon_name: str | None,
    icons_base_path: Path | None,
) -> tuple[Optional[str], Optional[Path]]:
    """将 menu_defs 的 icon_name 解析为 ChamferButton 的 icon_name / icon_path。
    - 内置键：直接返回 (icon_name, None)
    - .svg 或路径：需要 icons_base_path，返回 (None, full_path)
    """
    if not icon_name:
        return None, None
    if icon_name in BUILTIN_ICONS:
        return icon_name, None
    if icons_base_path is not None:
        return None, icons_base_path / icon_name
    # 回退：尝试从应用 config 获取（兼容旧用法）
    try:
        from config import ICONS_PATH  # type: ignore[import-untyped]
        return None, Path(ICONS_PATH) / icon_name
    except ImportError as exc:
        warn_once(
            logger,
            "Sidebar2:missing_icons_path",
            "Sidebar2: ICONS_PATH is unavailable, icon %s will be skipped.",
            icon_name,
            exc_info=exc,
        )
        return None, None


class Sidebar2(QWidget):
    """
    侧边栏导航：一列八边形按钮，垂直居中。
    - menu_defs: [(menu_id, text, icon_name), ...]，icon_name 为 builtin 键或文件名
    - icons_base_path: 外部图标根路径，None 时优先用 config.ICONS_PATH（应用内）
    - hover 显示 callout tooltip
    - 支持 itemClicked / selectedChanged / select / get_selected_id / clear_selection
    """

    itemClicked = Signal(str)
    selectedChanged = Signal(str)

    def __init__(
        self,
        menu_defs: Sequence[MenuDef] | None = None,
        icons_base_path: Optional[Union[str, Path]] = None,
        theme_manager: Optional["ThemeManager"] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.menu_defs = list(menu_defs) if menu_defs else []
        base = Path(icons_base_path) if icons_base_path else None
        self._theme_manager = resolve_theme_manager(theme_manager, "Sidebar2")

        self._buttons: dict[str, ChamferButton] = {}
        self._current_id: str | None = None
        self._callout_tooltip = CalloutTooltip(theme_manager=self._theme_manager)
        self._tooltip_timer = QTimer(self)
        self._tooltip_timer.setSingleShot(True)
        self._tooltip_timer.timeout.connect(self._show_callout_tooltip)
        self._hovered_btn: ChamferButton | None = None
        self._hovered_text: str = ""

        self.setFixedWidth(72)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("Sidebar2 { background-color: transparent; }")
        self.setAutoFillBackground(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addStretch(1)
        for mid, text, icon_name in self.menu_defs:
            iname, ipath = _resolve_icon(icon_name, base)
            btn = ChamferButton(
                text=text,
                icon_name=iname,
                icon_path=ipath,
                out_size=40,
                chamfer_ratio=0.5,
                menu_id=mid,
                use_native_tooltip=False,
                theme_manager=self._theme_manager,
                parent=self,
            )
            btn.clicked.connect(lambda _=False, m=mid: self._on_button_clicked(m))
            btn.installEventFilter(self)
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)
            self._buttons[mid] = btn
        self._btn_to_text = {self._buttons[mid]: text for mid, text, _ in self.menu_defs}
        layout.addStretch(1)

        if self.menu_defs:
            first_id = self.menu_defs[0][0]
            if first_id in self._buttons:
                self._current_id = first_id
                self._buttons[first_id].set_selected(True)

        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self.update)
            self._theme_manager.themeChanged.connect(self._callout_tooltip.update)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Enter:
            if obj in self._btn_to_text:
                self._tooltip_timer.stop()
                self._hovered_btn = obj
                self._hovered_text = self._btn_to_text[obj]
                self._tooltip_timer.start(300)
        elif event.type() == QEvent.Type.Leave:
            self._tooltip_timer.stop()
            self._hovered_btn = None
            self._hovered_text = ""
            self._callout_tooltip.hide()
        return super().eventFilter(obj, event)

    def _show_callout_tooltip(self) -> None:
        if self._hovered_btn is not None and self._hovered_text:
            self._callout_tooltip.show_for(self._hovered_btn, self._hovered_text)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

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

        color_str = "#D4ECD7"
        if self._theme_manager is not None:
            try:
                tokens = self._theme_manager.tokens()
                color_str = getattr(tokens, "color_bg_input", color_str)
            except (AttributeError, RuntimeError, TypeError) as exc:
                warn_once(
                    logger,
                    "Sidebar2:read_tokens_failed",
                    "Sidebar2: failed to read theme tokens in paintEvent, use default fallback color.",
                    exc_info=exc,
                )
        c = QColor(color_str)
        painter.setPen(QPen(c, 1))
        painter.setBrush(QBrush(c))
        painter.drawPath(path)
        painter.end()

    def _on_button_clicked(self, menu_id: str) -> None:
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

    def get_selected_id(self) -> str | None:
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
        """兼容旧 Sidebar 接口，无实现。"""
        pass
