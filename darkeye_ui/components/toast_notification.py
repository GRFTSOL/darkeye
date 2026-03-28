from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QWidget

from ..design.theme_context import resolve_theme_manager
from ..design.tokens import LIGHT_TOKENS, ThemeTokens

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class Toast(QFrame):
    """Token-driven toast message widget."""

    _active_toasts: ClassVar[dict[int, list["Toast"]]] = {}

    def __init__(
        self,
        message: str,
        parent: Optional[QWidget] = None,
        theme_manager: Optional["ThemeManager"] = None,
        level: str = "info",
        duration_ms: int = 2500,
    ) -> None:
        super().__init__(parent)
        self._anchor = parent
        self._duration_ms = max(0, duration_ms)
        self._level = level

        self.setObjectName("DesignToast")
        self.setWindowFlags(
            Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        self._theme_manager = resolve_theme_manager(theme_manager, "Toast")
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._apply_token_style)

        self._label = QLabel(message)
        self._label.setObjectName("DesignToastLabel")
        self._label.setWordWrap(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        layout.addWidget(self._label)

        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self.close)

        self._apply_token_style()

    @classmethod
    def show_message(
        cls,
        parent: Optional[QWidget],
        message: str,
        *,
        theme_manager: Optional["ThemeManager"] = None,
        level: str = "info",
        duration_ms: int = 2500,
    ) -> "Toast":
        toast = cls(
            message=message,
            parent=parent,
            theme_manager=theme_manager,
            level=level,
            duration_ms=duration_ms,
        )
        key = cls._group_key(parent)
        cls._active_toasts.setdefault(key, []).append(toast)
        toast.destroyed.connect(lambda *_: cls._on_toast_destroyed(key, toast))

        cls._reposition_group(parent)
        toast.show()
        if toast._duration_ms > 0:
            toast._close_timer.start(toast._duration_ms)
        return toast

    @classmethod
    def show_success(
        cls,
        parent: Optional[QWidget],
        message: str,
        *,
        theme_manager: Optional["ThemeManager"] = None,
        duration_ms: int = 2500,
    ) -> "Toast":
        return cls.show_message(
            parent,
            message,
            theme_manager=theme_manager,
            level="success",
            duration_ms=duration_ms,
        )

    @classmethod
    def show_warning(
        cls,
        parent: Optional[QWidget],
        message: str,
        *,
        theme_manager: Optional["ThemeManager"] = None,
        duration_ms: int = 3000,
    ) -> "Toast":
        return cls.show_message(
            parent,
            message,
            theme_manager=theme_manager,
            level="warning",
            duration_ms=duration_ms,
        )

    @classmethod
    def show_error(
        cls,
        parent: Optional[QWidget],
        message: str,
        *,
        theme_manager: Optional["ThemeManager"] = None,
        duration_ms: int = 3500,
    ) -> "Toast":
        return cls.show_message(
            parent,
            message,
            theme_manager=theme_manager,
            level="error",
            duration_ms=duration_ms,
        )

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _accent_color(self, t: ThemeTokens) -> str:
        if self._level == "success":
            return t.color_success
        if self._level == "warning":
            return t.color_warning
        if self._level == "error":
            return t.color_error
        return t.color_info

    def _apply_token_style(self, *_args) -> None:
        t = self._tokens()
        accent = self._accent_color(t)
        self.setStyleSheet(f"""
QFrame#DesignToast {{
    background-color: {t.color_bg};
    border: {t.border_width} solid {accent};
    border-radius: {t.radius_md};
}}
QLabel#DesignToastLabel {{
    color: {t.color_text};
    font-family: {t.font_family_base};
    font-size: {t.font_size_base};
}}
""")

    @classmethod
    def _group_key(cls, parent: Optional[QWidget]) -> int:
        return id(parent) if parent is not None else 0

    @classmethod
    def _on_toast_destroyed(cls, key: int, toast: "Toast") -> None:
        group = cls._active_toasts.get(key)
        if not group:
            return
        if toast in group:
            group.remove(toast)
        if not group:
            cls._active_toasts.pop(key, None)
            return
        anchor = group[0]._anchor if group else None
        cls._reposition_group(anchor)

    @classmethod
    def _reposition_group(cls, parent: Optional[QWidget]) -> None:
        key = cls._group_key(parent)
        group = cls._active_toasts.get(key)
        if not group:
            return

        margin = 16
        gap = 8

        if parent is not None:
            rect = parent.rect()
            top_left = parent.mapToGlobal(rect.topLeft())
            top = top_left.y()
            right = top_left.x() + rect.width()
        else:
            app = QApplication.instance()
            screen = app.primaryScreen() if app is not None else None
            available = screen.availableGeometry() if screen is not None else None
            if available is None:
                top = 0
                right = 800
            else:
                top = available.top()
                right = available.right()

        y = top + margin
        for toast in group:
            toast.adjustSize()
            x = right - toast.width() - margin
            toast.move(x, y)
            y += toast.height() + gap


# Backward-compatible alias.
Notification = Toast
