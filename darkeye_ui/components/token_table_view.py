from typing import Optional, TYPE_CHECKING

from PySide6.QtWidgets import QTableView, QWidget

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class TokenTableView(QTableView):
    """令牌驱动 TableView。

    - 通过 objectName=DesignTableView，使样式由 QSS 中的 {{token}} 驱动
    - 可选接入 ThemeManager，在主题切换时自动刷新样式
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        theme_manager: Optional["ThemeManager"] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DesignTableView")

        self._theme_manager = theme_manager
        if theme_manager is not None:
            theme_manager.themeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self, *_args) -> None:
        """主题切换时强制重新应用 QSS。"""
        style = self.style()
        style.unpolish(self)
        style.polish(self)

