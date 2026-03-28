import re
from typing import List, Set, Tuple, Optional
import logging


def parse_wikilinks(text: str) -> List[Tuple[str, Optional[str]]]:
    """
    解析文本中的双括号引用 [[target|alias]] 或 [[target]]

    Args:
        text (str): 需要解析的文本内容

    Returns:
        List[Tuple[str, Optional[str]]]: 返回解析结果列表，每项为 (target, alias)
        - target: 链接的目标（如作品番号、标题或ID）
        - alias: 显示的别名（如果没有别名则为 None）

    Example:
        >>> text = "这是 [[SNIS-123]] 的后续，推荐 [[SNIS-456|前作]]"
        >>> parse_wikilinks(text)
        [('SNIS-123', None), ('SNIS-456', '前作')]
    """
    if not text:
        return []

    # 正则表达式匹配 [[...]]
    # (.*?) 非贪婪匹配括号内的内容
    pattern = re.compile(r"\[\[(.*?)\]\]")

    matches = pattern.findall(text)
    results = []

    for match in matches:
        # 处理 [[target|alias]] 的情况
        if "|" in match:
            # 只分割第一个竖线，支持 alias 中包含竖线（虽然不常见，但为了健壮性）
            # 或者按照 Obsidian 惯例，最后一个竖线后是别名？通常是 split('|', 1)
            parts = match.split("|", 1)
            target = parts[0].strip()
            alias = parts[1].strip()
            if target:  # 确保目标不为空
                results.append((target, alias))
        else:
            target = match.strip()
            if target:
                results.append((target, None))

    return results


def extract_references(text: str) -> Set[str]:
    """
    仅提取去重后的目标引用列表，忽略别名

    Args:
        text (str): 文本内容

    Returns:
        Set[str]: 唯一的目标集合
    """
    links = parse_wikilinks(text)
    return {link[0] for link in links}
