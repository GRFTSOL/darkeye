# darkeye_ui/components/token_tab_widget.py - 令牌驱动 TabWidget，样式由 mymain.qss 令牌驱动，随主题切换
from typing import Optional, TYPE_CHECKING

from PySide6.QtWidgets import QTabWidget, QWidget

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class TokenTabWidget(QTabWidget):
    """令牌驱动 TabWidget：通过 objectName=DesignTabWidget 由 QSS 模板中的 {{token}} 驱动样式，
    随主题切换变色（未选灰、悬停深灰、选中加粗+底线）。"""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        theme_manager: Optional["ThemeManager"] = None,
    ):
        super().__init__(parent)
        self.setObjectName("DesignTabWidget")
        self._theme_manager = theme_manager
        if theme_manager is not None:
            theme_manager.themeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self) -> None:
        """主题切换时触发展示刷新，确保 QSS 重新应用后样式正确。"""
        self.style().unpolish(self)
        self.style().polish(self)
        tab_bar = self.tabBar()
        if tab_bar is not None:
            self.style().unpolish(tab_bar)
            self.style().polish(tab_bar)
