from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..design.theme_context import resolve_theme_manager
from ..design.tokens import LIGHT_TOKENS, ThemeTokens
from .button import Button

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


def _dialog_qss_from_tokens(t: ThemeTokens) -> str:
    return f"""
QDialog#DesignModalDialog {{
    background-color: {t.color_bg};
    border: {t.border_width} solid {t.color_border};
    border-radius: {t.radius_md};
}}
QLabel#DesignModalTitle {{
    color: {t.color_text};
    font-family: {t.font_family_base};
    font-size: 16px;
    font-weight: 700;
}}
QLabel#DesignModalMessage {{
    color: {t.color_text};
    font-family: {t.font_family_base};
    font-size: {t.font_size_base};
}}
"""


def _danger_button_qss_from_tokens(t: ThemeTokens) -> str:
    return f"""
QPushButton#DesignButton {{
    background-color: {t.color_error};
    color: {t.color_text_inverse};
    border: {t.border_width} solid {t.color_error};
    border-radius: {t.radius_md};
    padding: 4px 12px;
}}
QPushButton#DesignButton:hover {{
    background-color: {t.color_error};
    border-color: {t.color_error};
}}
"""


class ModalDialog(QDialog):
    """Token-driven modal dialog with confirm/cancel actions."""

    def __init__(
        self,
        title: str,
        message: str,
        parent: Optional[QWidget] = None,
        theme_manager: Optional["ThemeManager"] = None,
        confirm_text: str = "Confirm",
        cancel_text: str = "Cancel",
        show_cancel: bool = True,
        danger: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DesignModalDialog")
        self.setModal(True)
        self.setWindowTitle(title or "Notice")
        self.setMinimumWidth(420)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self._theme_manager = resolve_theme_manager(theme_manager, "ModalDialog")
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._apply_token_style)

        self._title_label = QLabel(title or "Notice")
        self._title_label.setObjectName("DesignModalTitle")
        self._title_label.setWordWrap(True)

        self._message_label = QLabel(message or "")
        self._message_label.setObjectName("DesignModalMessage")
        self._message_label.setWordWrap(True)
        self._message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._confirm_btn = Button(confirm_text, variant="primary")
        self._confirm_btn.clicked.connect(self.accept)
        self._cancel_btn = Button(cancel_text)
        self._cancel_btn.clicked.connect(self.reject)

        footer = QHBoxLayout()
        footer.addStretch(1)
        if show_cancel:
            footer.addWidget(self._cancel_btn)
        footer.addWidget(self._confirm_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(self._title_label)
        layout.addWidget(self._message_label)
        layout.addLayout(footer)

        self._danger = danger
        self._apply_token_style()

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _apply_token_style(self, *_args) -> None:
        t = self._tokens()
        self.setStyleSheet(_dialog_qss_from_tokens(t))
        if self._danger:
            self._confirm_btn.setStyleSheet(_danger_button_qss_from_tokens(t))
        else:
            self._confirm_btn.setStyleSheet("")

    @classmethod
    def confirm(
        cls,
        parent: Optional[QWidget],
        title: str,
        message: str,
        theme_manager: Optional["ThemeManager"] = None,
        confirm_text: str = "Confirm",
        cancel_text: str = "Cancel",
    ) -> bool:
        dialog = cls(
            title=title,
            message=message,
            parent=parent,
            theme_manager=theme_manager,
            confirm_text=confirm_text,
            cancel_text=cancel_text,
            show_cancel=True,
            danger=False,
        )
        return dialog.exec() == QDialog.DialogCode.Accepted

    @classmethod
    def danger_confirm(
        cls,
        parent: Optional[QWidget],
        title: str,
        message: str,
        theme_manager: Optional["ThemeManager"] = None,
        confirm_text: str = "Delete",
        cancel_text: str = "Cancel",
    ) -> bool:
        dialog = cls(
            title=title,
            message=message,
            parent=parent,
            theme_manager=theme_manager,
            confirm_text=confirm_text,
            cancel_text=cancel_text,
            show_cancel=True,
            danger=True,
        )
        return dialog.exec() == QDialog.DialogCode.Accepted


# Backward-compatible aliases.
Dialog = ModalDialog
TokenModalDialog = ModalDialog
