# ui/components/button.py - 设计系统按钮，样式由 mymain.qss + 令牌驱动
from pathlib import Path
from typing import Union

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton

from ..design.icon import svg_to_icon


class Button(QPushButton):
    """可复用按钮，通过 objectName=DesignButton 与 variant 由 QSS 驱动样式。支持 icon（路径、内联 SVG 字符串或 QIcon）。"""

    def __init__(
        self,
        text: str = "",
        variant: str = "default",
        icon: Union[str, Path, QIcon, None] = None,
        icon_size: Union[int, tuple] = 24,
        icon_color: Union[str, None] = None,
        parent=None,
    ):
        super().__init__(text, parent)
        self.setObjectName("DesignButton")
        self.setProperty("variant", variant)
        if icon is not None:
            if isinstance(icon, QIcon):
                self.setIcon(icon)
            else:
                self.setIcon(svg_to_icon(icon, size=icon_size, color=icon_color))
            w, h = (
                (icon_size, icon_size)
                if isinstance(icon_size, int)
                else (icon_size[0], icon_size[1])
            )
            self.setIconSize(QSize(w, h))
