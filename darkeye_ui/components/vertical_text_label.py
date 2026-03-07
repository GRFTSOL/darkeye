from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from .._logging import get_logger, warn_once
from ..design.theme_context import resolve_theme_manager
from ..layouts import VerticalTextLayout
from ..design.tokens import ThemeTokens, LIGHT_TOKENS

if TYPE_CHECKING:
    from ..design.theme_manager import ThemeManager


class VerticalTextLabel(QWidget):
    """竖排文字标签组件。

    - 支持中日文竖排与英文旋转排版
    - 排版逻辑由 `VerticalTextLayout` 提供
    - 颜色与字体可通过 ThemeManager / 设计令牌驱动
    - tone 变体：normal / inverse
    """

    def __init__(
        self,
        text: str = "",
        theme_manager: Optional["ThemeManager"] = None,
        tone: str = "normal",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._logger = get_logger(__name__)

        theme_manager = resolve_theme_manager(theme_manager, "VerticalTextLabel")
        self._theme_manager = theme_manager
        self._tone = tone  # normal / inverse
        self.setProperty("tone", tone)

        tokens = self._tokens()

        # 字体：优先使用设计令牌，否则回退到默认值
        font_family = tokens.font_family_base
        try:
            base_size = int(tokens.font_size_base.replace("px", ""))
        except (ValueError, AttributeError) as exc:
            warn_once(
                self._logger,
                "VerticalTextLabel:invalid_font_size_base",
                "VerticalTextLabel: invalid font_size_base token, fallback to default size 14.",
                exc_info=exc,
            )
            base_size = 14

        self._font = QFont(font_family, base_size + 2)
        fm = QFontMetrics(self._font)

        # 颜色：走设计令牌（根据 tone 切换）
        self._text_color = QColor()

        # 行距与列距与字体高度相关
        self._line_spacing = fm.height() * 0.05
        self._column_spacing = fm.height() * 0.1
        self._text = ""
        self._layout = VerticalTextLayout(fm, self._line_spacing, self._column_spacing)
        self._text_blocks = []  # 缓存排版结果

        self._apply_tokens(tokens)

        self.setText(text)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._on_theme_changed)

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _apply_tokens(self, tokens: ThemeTokens) -> None:
        """根据当前 tone 从令牌中选择合适的文字颜色。"""
        if self._tone == "inverse":
            color_str = tokens.color_text_inverse
        else:
            color_str = tokens.color_text

        self._text_color = QColor(color_str)

    def _on_theme_changed(self, *_args) -> None:
        """主题切换时刷新颜色。"""
        tokens = self._tokens()
        self._apply_tokens(tokens)
        self.update()

    # --- 公共 API ---
    def setText(self, text: str) -> None:
        text = VerticalTextLayout.replace_ellipsis(text)
        self._text = text
        self._updateLayout()
        self.update()
        self.updateGeometry()

    def text(self) -> str:
        return self._text

    def setFont(self, font: QFont) -> None:
        self._font = font
        self._layout = VerticalTextLayout(
            QFontMetrics(self._font),
            self._line_spacing,
            self._column_spacing,
        )
        self._updateLayout()
        self.update()

    def font(self) -> QFont:  # type: ignore[override]
        return self._font

    def setTextColor(self, color: QColor | str) -> None:
        """显式覆盖文字颜色（绕过 tone 逻辑）。"""
        self._text_color = QColor(color)
        self.update()

    def set_tone(self, tone: str) -> None:
        """切换 tone 变体：normal / inverse。"""
        self._tone = tone
        self.setProperty("tone", tone)
        self._apply_tokens(self._tokens())
        self.update()

    # --- 内部实现 ---
    def _updateLayout(self) -> None:
        """更新文本布局。"""
        self._text_blocks = self._layout.calculate_layout(
            self._text,
            self.width(),
            self.height(),
        )

    def paintEvent(self, event) -> None:  # type: ignore[override]
        """使用预先计算好的布局信息进行绘制。"""
        super().paintEvent(event)
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.TextAntialiasing)
            painter.setFont(self._font)
            painter.setPen(self._text_color)

            for block in self._text_blocks:
                if block.is_english:
                    painter.save()
                    center = block.rect.center()
                    painter.translate(center)
                    painter.rotate(block.rotation)

                    text_width = painter.fontMetrics().boundingRect(block.text).width()
                    fm = painter.fontMetrics()
                    baseline_offset = (fm.ascent() - fm.descent()) / 2

                    painter.drawText(-text_width / 2, baseline_offset, block.text)
                    painter.restore()
                else:
                    painter.drawText(block.rect, Qt.AlignCenter, block.text)

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return self.minimumSizeHint()

    def minimumSizeHint(self) -> QSize:  # type: ignore[override]
        """使用排版类计算所需尺寸。"""
        return self._layout.calculate_size(self._text, self.height())

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        """当控件大小改变时，重新计算布局。"""
        super().resizeEvent(event)
        self._updateLayout()
