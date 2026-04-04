from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, QUrl, QSize
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..design.icon import get_builtin_icon
from ..design.theme_context import resolve_theme_manager
from ..design.tokens import LIGHT_TOKENS

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager

_LINK_CARD_WIDTH_PX = 400
_LINK_ICON_PX = 18


class TokenLinkCard(QFrame):
    """可点击外链卡片：标题与简介由子 QLabel 展示，边框/背景/字色由 QSS 与主题令牌驱动。"""

    def __init__(
        self,
        title: str,
        blurb: str,
        url: str,
        parent: QWidget | None = None,
        *,
        theme_manager: Optional["ThemeManager"] = None,
    ) -> None:
        super().__init__(parent)
        self._url = url
        self.setObjectName("DesignLinkCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(url)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Preferred,
        )
        self.setFixedWidth(_LINK_CARD_WIDTH_PX)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)

        title_lbl = QLabel(title, self)
        title_lbl.setObjectName("DesignLinkCardTitle")
        title_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        text_col.addWidget(title_lbl)

        desc_lbl = QLabel(blurb, self)
        desc_lbl.setObjectName("DesignLinkCardDescription")
        desc_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        desc_lbl.setWordWrap(True)
        text_col.addWidget(desc_lbl)

        root.addLayout(text_col, stretch=1)

        self._icon_lbl = QLabel(self)
        self._icon_lbl.setObjectName("DesignLinkCardIcon")
        self._icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._icon_lbl.setFixedSize(_LINK_ICON_PX, _LINK_ICON_PX)
        self._icon_lbl.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(
            self._icon_lbl,
            stretch=0,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )

        self._theme_manager = resolve_theme_manager(theme_manager, "TokenLinkCard")
        self._refresh_link_icon()
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._on_theme_changed)

    def _link_icon_color(self) -> str:
        if self._theme_manager is not None:
            return self._theme_manager.tokens().color_icon
        return LIGHT_TOKENS.color_icon

    def _refresh_link_icon(self) -> None:
        icon = get_builtin_icon(
            "link",
            size=_LINK_ICON_PX,
            color=self._link_icon_color(),
        )
        self._icon_lbl.setPixmap(icon.pixmap(QSize(_LINK_ICON_PX, _LINK_ICON_PX)))

    def _on_theme_changed(self, *_args) -> None:
        self._refresh_link_icon()
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        for child in self.findChildren(QLabel):
            style.unpolish(child)
            style.polish(child)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            QDesktopServices.openUrl(QUrl(self._url))
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            QDesktopServices.openUrl(QUrl(self._url))
        else:
            super().keyPressEvent(event)
