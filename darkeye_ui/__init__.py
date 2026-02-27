"""
darkeye_ui - 可复用的设计系统与组件库

对外主要暴露：
- 设计系统：ThemeManager, ThemeId, tokens, 图标工具
- 组件：Button, IconPushButton, Label, Input, StateToggleButton, ToggleSwitch
- 布局：FlowLayout, WaterfallLayout, VFlowLayout, VerticalTextLayout
- 基类：LazyWidget
"""

from .base import LazyWidget
from .design import (  # type: ignore[F401]
    ThemeTokens,
    ThemeId,
    LIGHT_TOKENS,
    DARK_TOKENS,
    RED_TOKENS,
    load_stylesheet,
    ThemeManager,
    svg_to_icon,
    get_builtin_icon,
    BUILTIN_ICONS,
    SVG_CHECK,
    SVG_MINUS,
)

from .components import (  # type: ignore[F401]
    Button,
    IconPushButton,
    Label,
    LineEdit,
    StateToggleButton,
    ToggleSwitch,
)

from .layouts import (  # type: ignore[F401]
    FlowLayout,
    WaterfallLayout,
    VFlowLayout,
    VerticalTextLayout,
)

__all__ = [
    # base
    "LazyWidget",
    # design
    "ThemeTokens",
    "ThemeId",
    "LIGHT_TOKENS",
    "DARK_TOKENS",
    "RED_TOKENS",
    "load_stylesheet",
    "ThemeManager",
    "svg_to_icon",
    "get_builtin_icon",
    "BUILTIN_ICONS",
    "SVG_CHECK",
    "SVG_MINUS",
    # components
    "Button",
    "IconPushButton",
    "Label",
    "Input",
    "StateToggleButton",
    "ToggleSwitch",
    # layouts
    "FlowLayout",
    "WaterfallLayout",
    "VFlowLayout",
    "VerticalTextLayout",
]

