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
    color_text_inverse: str
    color_text_placeholder: str
    color_text_disabled: str
    color_success: str
    color_warning: str
    color_error: str
    color_info: str
    color_icon: str
    color_icon_disabled: str
    radius_md: str
    font_family_base: str
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
    color_text_inverse="#ffffff",
    color_text_placeholder="#bbb",
    color_text_disabled="#999",
    color_success="#2e7d32",
    color_warning="#ed6c02",
    color_error="#c62828",
    color_info="#0288d1",
    color_icon="#333333",
    color_icon_disabled="#999",
    radius_md="8px",
    font_family_base="Microsoft YaHei",
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
    color_text_inverse="#1e1e1e",
    color_text_placeholder="#888",
    color_text_disabled="#666",
    color_success="#66bb6a",
    color_warning="#ffb74d",
    color_error="#ef5350",
    color_info="#29b6f6",
    color_icon="#e0e0e0",
    color_icon_disabled="#666",
    radius_md="8px",
    font_family_base="Microsoft YaHei",
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
    color_text_inverse="#ffffff",
    color_text_placeholder="#c62828",
    color_text_disabled="#8d6e63",
    color_success="#1b5e20",
    color_warning="#e65100",
    color_error="#b71c1c",
    color_info="#01579b",
    color_icon="#4a1515",
    color_icon_disabled="#8d6e63",
    radius_md="8px",
    font_family_base="Microsoft YaHei",
    font_size_base="12px",
    border_width="2px",
)

GREEN_TOKENS = ThemeTokens(
    color_primary="#2e7d32",
    color_primary_hover="#1b5e20",
    color_bg="#f1f8e9",
    color_bg_input="#e8f5e9",
    color_bg_page="#e0f2e9",
    color_border="#a5d6a7",
    color_border_focus="#2e7d32",
    color_text="#1b3d1f",
    color_text_inverse="#ffffff",
    color_text_placeholder="#388e3c",
    color_text_disabled="#6b7c6d",
    color_success="#1b5e20",
    color_warning="#e65100",
    color_error="#c62828",
    color_info="#1565c0",
    color_icon="#1b3d1f",
    color_icon_disabled="#6b7c6d",
    radius_md="8px",
    font_family_base="Microsoft YaHei",
    font_size_base="12px",
    border_width="2px",
)

YELLOW_TOKENS = ThemeTokens(
    color_primary="#f9a825",
    color_primary_hover="#f57f17",
    color_bg="#fffde7",
    color_bg_input="#fff8e1",
    color_bg_page="#ffecb3",
    color_border="#ffe082",
    color_border_focus="#f9a825",
    color_text="#3e2723",
    color_text_inverse="#ffffff",
    color_text_placeholder="#ff8f00",
    color_text_disabled="#8d6e63",
    color_success="#2e7d32",
    color_warning="#e65100",
    color_error="#c62828",
    color_info="#0277bd",
    color_icon="#3e2723",
    color_icon_disabled="#8d6e63",
    radius_md="8px",
    font_family_base="Microsoft YaHei",
    font_size_base="12px",
    border_width="2px",
)

BLUE_TOKENS = ThemeTokens(
    color_primary="#1976d2",
    color_primary_hover="#1565c0",
    color_bg="#f8fbff",
    color_bg_input="#e8f4fc",
    color_bg_page="#e1f0fa",
    color_border="#90caf9",
    color_border_focus="#1976d2",
    color_text="#1e3a5f",
    color_text_inverse="#ffffff",
    color_text_placeholder="#5c9fd6",
    color_text_disabled="#78909c",
    color_success="#2e7d32",
    color_warning="#e65100",
    color_error="#c62828",
    color_info="#0288d1",
    color_icon="#1e3a5f",
    color_icon_disabled="#78909c",
    radius_md="8px",
    font_family_base="Microsoft YaHei",
    font_size_base="12px",
    border_width="2px",
)

PURPLE_TOKENS = ThemeTokens(
    color_primary="#8e24aa",
    color_primary_hover="#7b1fa2",
    color_bg="#faf8fc",
    color_bg_input="#f3e5f5",
    color_bg_page="#ede7f6",
    color_border="#d1c4e9",
    color_border_focus="#8e24aa",
    color_text="#3e2a4a",
    color_text_inverse="#ffffff",
    color_text_placeholder="#9575cd",
    color_text_disabled="#78909c",
    color_success="#2e7d32",
    color_warning="#e65100",
    color_error="#c62828",
    color_info="#7e57c2",
    color_icon="#3e2a4a",
    color_icon_disabled="#78909c",
    radius_md="8px",
    font_family_base="Microsoft YaHei",
    font_size_base="12px",
    border_width="2px",
)
