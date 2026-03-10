from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPainterPath, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QWidget

from ..design.theme_context import resolve_theme_manager
from ..design.tokens import LIGHT_TOKENS, ThemeTokens

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class Avatar(QWidget):
    """Circular avatar with text initials or image."""

    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
        *,
        image_path: Optional[str] = None,
        size: int = 32,
        theme_manager: Optional["ThemeManager"] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DesignAvatar")
        self._text = text
        self._size = max(16, size)
        self._pixmap = QPixmap(image_path) if image_path else QPixmap()

        self.setMinimumSize(self._size, self._size)
        self.setMaximumSize(self._size, self._size)

        self._theme_manager = resolve_theme_manager(theme_manager, "Avatar")
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._on_theme_changed)

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def set_text(self, text: str) -> None:
        self._text = text
        self.update()

    def set_image_path(self, image_path: Optional[str]) -> None:
        self._pixmap = QPixmap(image_path) if image_path else QPixmap()
        self.update()

    def _initials(self) -> str:
        parts = [p for p in self._text.strip().split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][:1] + parts[-1][:1]).upper()

    def _bg_color(self, tokens: ThemeTokens) -> QColor:
        base = QColor(tokens.color_primary)
        # Slightly vary hue by text hash for visual differentiation.
        h, s, l, a = base.getHsl()
        shift = (sum(ord(ch) for ch in self._text) % 36) - 18
        new_h = (h + shift) % 360 if h >= 0 else 200
        color = QColor()
        color.setHsl(new_h, max(40, s), l, a)
        return color

    def paintEvent(self, event: QPaintEvent) -> None:
        _ = event
        t = self._tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)

        path = QPainterPath()
        path.addEllipse(rect)
        painter.setClipPath(path)

        bg = self._bg_color(t)
        painter.fillPath(path, bg)

        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(rect.topLeft(), scaled)
        else:
            painter.setPen(QColor(t.color_text_inverse))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(max(8, int(self._size * 0.35)))
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._initials())

        # Draw ring to separate overlapping avatars in group.
        painter.setClipping(False)
        painter.setPen(QColor(t.color_bg_page))
        painter.drawEllipse(rect)

    def _on_theme_changed(self, *_args) -> None:
        self.update()


class AvatarGroup(QWidget):
    """Overlapped avatar group widget."""

    def __init__(
        self,
        avatars: Optional[Iterable[str]] = None,
        parent: Optional[QWidget] = None,
        *,
        avatar_size: int = 32,
        overlap: int = 10,
        max_visible: int = 5,
        theme_manager: Optional["ThemeManager"] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DesignAvatarGroup")
        self._avatar_size = max(16, avatar_size)
        self._overlap = max(0, overlap)
        self._max_visible = max(1, max_visible)
        self._theme_manager = resolve_theme_manager(theme_manager, "AvatarGroup")

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(-self._overlap)

        self.set_avatars(list(avatars or []))

    def set_avatars(self, avatars: Iterable[str]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        values = list(avatars)
        hidden_count = max(0, len(values) - self._max_visible)
        shown = values[: self._max_visible]
        if hidden_count > 0 and shown:
            shown = shown[:-1] + [f"+{hidden_count}"]

        for text in shown:
            avatar = Avatar(
                text=text,
                size=self._avatar_size,
                theme_manager=self._theme_manager,
            )
            self._layout.addWidget(avatar)
        self._layout.addStretch(1)
