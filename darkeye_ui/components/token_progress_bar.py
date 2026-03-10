from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import QProgressBar, QWidget

from ..design.theme_context import resolve_theme_manager

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class ProgressBar(QProgressBar):
    """Token-driven progress bar using global QSS + objectName."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        theme_manager: Optional["ThemeManager"] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DesignProgressBar")
        self.setTextVisible(True)
        theme_manager = resolve_theme_manager(theme_manager, "ProgressBar")
        self._theme_manager = theme_manager
        if theme_manager is not None:
            theme_manager.themeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self, *_args) -> None:
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()


class IndeterminateProgressBar(ProgressBar):
    """Indeterminate progress bar (busy state)."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        theme_manager: Optional["ThemeManager"] = None,
    ) -> None:
        super().__init__(parent=parent, theme_manager=theme_manager)
        self.start()

    def start(self) -> None:
        self.setRange(0, 0)

    def stop(self, value: int = 0) -> None:
        self.setRange(0, 100)
        self.setValue(max(0, min(100, value)))


# Backward-compatible alias.
TokenProgressBar = ProgressBar
