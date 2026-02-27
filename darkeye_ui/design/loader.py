# design/loader.py - QSS 模板加载与令牌替换
from pathlib import Path
from typing import Union

from .tokens import ThemeTokens


def load_stylesheet(
    template_path: Path,
    tokens: Union[ThemeTokens, dict],
) -> str:
    """读取 QSS 模板，将 {{token_name}} 替换为 tokens 中的值，返回最终样式表。
    tokens 可为 ThemeTokens 或已包含扩展令牌的 dict。"""
    raw = template_path.read_text(encoding="utf-8")
    d = tokens.to_dict() if isinstance(tokens, ThemeTokens) else tokens
    for key, value in d.items():
        raw = raw.replace("{{" + key + "}}", str(value))
    return raw
