# darkeye_ui/components/token_vertical_tab_bar.py - 竖排 TabBar，由设计令牌驱动
"""竖排 TabBar，文字颜色由设计令牌驱动，支持主题切换。"""

import re
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QStyle, QStyleOptionTab, QStylePainter, QTabBar

from .._logging import get_logger, warn_once
from ..design.theme_context import resolve_theme_manager
from ..design.tokens import LIGHT_TOKENS, ThemeTokens

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class TokenVerticalTabBar(QTabBar):
    """竖排 TabBar：文字颜色由设计令牌驱动，主题切换时自动更新。"""

    def __init__(
        self,
        theme_manager: Optional["ThemeManager"] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._logger = get_logger(__name__)
        self.setObjectName("VerticalTabBar")
        self.setShape(QTabBar.RoundedWest)
        fm = self.fontMetrics()
        self._line_spacing = fm.height() * 0.05
        self._column_spacing = fm.height() * 0.1
        # 顶部额外留白（控制“margin-top”效果）
        self._top_margin = fm.height() * 0.3
        self.setFont(QFont("Microsoft YaHei", 12))

        theme_manager = resolve_theme_manager(theme_manager, "TokenVerticalTabBar")
        self._theme_manager = theme_manager
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._apply_token_styles)
        self._apply_token_styles()

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _apply_token_styles(self) -> None:
        t = self._tokens()
        self.setProperty("tabTextColor", t.color_text)
        self.setProperty("tabTextColorSelected", t.color_text_inverse)
        try:
            self.style().unpolish(self)
            self.style().polish(self)
        except (AttributeError, RuntimeError) as exc:
            warn_once(
                self._logger,
                "TokenVerticalTabBar:polish_failed",
                "TokenVerticalTabBar: style polish failed after theme change.",
                exc_info=exc,
            )
        self.update()

    def _replace_ellipsis(self, text: str) -> str:
        if text == "" or text is None:
            return ""
        text = text.replace("，", "\ufe10")
        text = text.replace("、", "\ufe11")
        text = text.replace("。", "\ufe12")
        text = text.replace("：", "\ufe13")
        text = text.replace("；", "\ufe14")
        text = text.replace("！", "\ufe15")
        text = text.replace("？", "\ufe16")
        text = text.replace("……", "\ufe19")
        text = text.replace("\u2026", "\ufe19")
        text = text.replace("\u22ef", "\ufe19")
        text = text.replace("（", "\ufe35")
        text = text.replace("）", "\ufe36")
        text = text.replace("【", "\ufe3b")
        text = text.replace("】", "\ufe3c")
        text = text.replace("《", "\ufe3d")
        text = text.replace("》", "\ufe3e")
        text = text.replace("〈", "\ufe3f")
        text = text.replace("〉", "\ufe40")
        text = text.replace("'", "\ufe41")
        text = text.replace("'", "\ufe42")
        text = text.replace("「", "\ufe41")
        text = text.replace("」", "\ufe42")
        text = text.replace("『", "\ufe43")
        text = text.replace("』", "\ufe44")
        return text

    def split_text_blocks(self, text: str):
        blocks = []
        buffer = ""
        is_english = None
        for ch in text:
            if re.match(r"[A-Za-z0-9\-()]", ch):
                if is_english is False:
                    blocks.append(buffer)
                    buffer = ""
                buffer += ch
                is_english = True
            else:
                if is_english is True:
                    blocks.append(buffer)
                    buffer = ""
                buffer += ch
                is_english = False
        if buffer:
            blocks.append(buffer)
        return blocks

    def paintEvent(self, event):
        painter = QStylePainter(self)
        opt = QStyleOptionTab()
        try:
            for i in range(self.count()):
                self.initStyleOption(opt, i)
                rect = self.tabRect(i)
                painter.drawControl(QStyle.CE_TabBarTabShape, opt)
                text_color = None
                if opt.state & QStyle.State_Selected:
                    text_color = self.property("tabTextColorSelected")
                if text_color is None or not text_color:
                    text_color = self.property("tabTextColor")
                if text_color is not None and text_color:
                    try:
                        c = QColor(str(text_color))
                        if c.isValid():
                            painter.setPen(c)
                    except (TypeError, ValueError) as exc:
                        warn_once(
                            self._logger,
                            "TokenVerticalTabBar:invalid_text_color",
                            "TokenVerticalTabBar: invalid tab text color, fallback to palette color.",
                            exc_info=exc,
                        )
                        painter.setPen(self.palette().color(self.foregroundRole()))
                else:
                    painter.setPen(self.palette().color(self.foregroundRole()))
                painter.setFont(self.font())
                painter.setRenderHint(QPainter.TextAntialiasing)
                text = self._replace_ellipsis(self.tabText(i))
                fm = painter.fontMetrics()
                char_height = fm.height() + self._line_spacing
                char_width = fm.maxWidth()
                x = rect.right() - char_width
                # 顶部预留一定间距，让文字整体向下偏移
                y = rect.top() + int(self._top_margin)
                for block in self.split_text_blocks(text):
                    if re.match(r"[A-Za-z0-9\-()]+$", block):
                        br = fm.boundingRect(block)
                        block_w = br.width()
                        painter.save()
                        painter.translate(x + char_width / 2, y + block_w / 2)
                        painter.rotate(90)
                        painter.drawText(
                            -block_w / 2, fm.ascent() - br.height() / 2, block
                        )
                        painter.restore()
                        y += block_w + self._line_spacing
                    else:
                        for ch in block:
                            painter.drawText(
                                QRect(x, y, char_width, char_height), Qt.AlignCenter, ch
                            )
                            y += char_height
        finally:
            painter.end()

    def tabSizeHint(self, index):
        text = self._replace_ellipsis(self.tabText(index))
        fm = self.fontMetrics()
        char_height = fm.height()
        char_width = fm.maxWidth()
        padding_vertical = int(char_height * 0.2)
        padding_horizontal = int(char_width * 0.3)
        total_height = padding_vertical * 2
        for block in self.split_text_blocks(text):
            if re.match(r"[A-Za-z0-9\-()]+$", block):
                block_width = fm.boundingRect(block).width()
                total_height += block_width + self._line_spacing
            else:
                total_height += (char_height + self._line_spacing) * len(block)
        max_single_width = (
            max(fm.horizontalAdvance(c) for c in text if c.strip()) if text else 0
        )
        min_width = int(max_single_width * 1.5) if max_single_width else 40
        ideal_width = (
            max_single_width + padding_horizontal * 2 if max_single_width else 60
        )
        max_width = int(max_single_width * 2.5) if max_single_width else 120
        width = max(min_width, min(ideal_width, max_width))
        return QSize(width, total_height)
