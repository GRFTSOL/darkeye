from typing import Optional, TYPE_CHECKING

from PySide6.QtWidgets import QGroupBox, QWidget

from ..design.theme_context import resolve_theme_manager

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class TokenGroupBox(QGroupBox):
    """令牌驱动 GroupBox：通过 objectName=DesignGroupBox 由 QSS 模板中的 {{token}} 驱动样式，
    随主题切换时自动刷新边框与标题颜色。"""

    def __init__(
        self,
        title: str = "",
        parent: Optional[QWidget] = None,
        theme_manager: Optional["ThemeManager"] = None,
    ) -> None:
        super().__init__(title, parent)
        self.setObjectName("DesignGroupBox")
        theme_manager = resolve_theme_manager(theme_manager, "TokenGroupBox")
        self._theme_manager = theme_manager
        if theme_manager is not None:
            theme_manager.themeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self, *_args) -> None:
        """主题切换时强制重新应用 QSS，保证颜色与边框即时更新。"""
        style = self.style()
        style.unpolish(self)
        style.polish(self)

