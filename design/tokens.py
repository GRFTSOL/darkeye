# design/tokens.py - 设计令牌定义与多套主题值
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ThemeTokens:
    """一套主题对应的所有设计令牌。"""
    color_primary: str
    color_primary_hover: str
    color_bg: str
    color_bg_input: str
    color_bg_page: str
    color_border: str
    color_border_focus: str
    color_text: str
    color_text_placeholder: str
    color_text_disabled: str
    color_success: str
    color_warning: str
    color_error: str
    color_info: str
    color_icon: str
    color_icon_disabled: str
    radius_md: str
    font_size_base: str
    border_width: str

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


LIGHT_TOKENS = ThemeTokens(
    color_primary="#00aaff",
    color_primary_hover="#0099ee",
    color_bg="#ffffff",
    color_bg_input="#f0faff",
    color_bg_page="#f5f5f5",
    color_border="#ccc",
    color_border_focus="#00aaff",
    color_text="#333333",
    color_text_placeholder="#bbb",
    color_text_disabled="#999",
    color_success="#2e7d32",
    color_warning="#ed6c02",
    color_error="#c62828",
    color_info="#0288d1",
    color_icon="#333333",
    color_icon_disabled="#999",
    radius_md="8px",
    font_size_base="12px",
    border_width="2px",
)

DARK_TOKENS = ThemeTokens(
    color_primary="#00aaff",
    color_primary_hover="#33bbff",
    color_bg="#1e1e1e",
    color_bg_input="#2d2d2d",
    color_bg_page="#252526",
    color_border="#444",
    color_border_focus="#00aaff",
    color_text="#e0e0e0",
    color_text_placeholder="#888",
    color_text_disabled="#666",
    color_success="#66bb6a",
    color_warning="#ffb74d",
    color_error="#ef5350",
    color_info="#29b6f6",
    color_icon="#e0e0e0",
    color_icon_disabled="#666",
    radius_md="8px",
    font_size_base="12px",
    border_width="2px",
)

RED_TOKENS = ThemeTokens(
    color_primary="#c62828",
    color_primary_hover="#b71c1c",
    color_bg="#fff5f5",
    color_bg_input="#ffebee",
    color_bg_page="#fce4ec",
    color_border="#ef9a9a",
    color_border_focus="#c62828",
    color_text="#4a1515",
    color_text_placeholder="#c62828",
    color_text_disabled="#8d6e63",
    color_success="#1b5e20",
    color_warning="#e65100",
    color_error="#b71c1c",
    color_info="#01579b",
    color_icon="#4a1515",
    color_icon_disabled="#8d6e63",
    radius_md="8px",
    font_size_base="12px",
    border_width="2px",
)
