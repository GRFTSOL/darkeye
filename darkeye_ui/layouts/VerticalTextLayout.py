from dataclasses import dataclass
from typing import List, Tuple, Optional
from PySide6.QtCore import QRect, QPoint, QSize
from PySide6.QtGui import QFontMetrics
import re

#用于排版竖向文本，包括中日文、标点、英文和数字的混合排版
#标准参考：
# 标点符号用法GB/T 15834-2011 

#包括标题符号的替换、分块划分、布局计算、尺寸估计等功能

#以后所有的竖向排版都用这个类来处理

@dataclass
class TextBlock:
    """文字块的信息"""
    text: str
    is_english: bool
    rect: QRect
    rotation: float = 0  # 旋转角度
    ascent: float = 0    # 基线位置（用于英文旋转）

class VerticalTextLayout:
    """竖排文字的排版计算类"""
    def __init__(self, font_metrics: QFontMetrics, line_spacing: float, column_spacing: float):
        self.fm = font_metrics
        self.line_spacing = line_spacing
        self.column_spacing = column_spacing
        self.char_height = self.fm.height() + self.line_spacing
        self.char_width = self.fm.maxWidth()
        
    @staticmethod
    def replace_ellipsis(text: str) -> str:
        """替换标点符号为竖排专用符号，这个还有其他的解决方法
        
        符合中文标点符号用法GB/T 15834-2011
        
        Args:
            text: 原始文本
            
        Returns:
            str: 替换标点后的文本
        """
        if text == "" or text is None:
            return ""
            
        replacements = {
            "，": "\uFE10",  # 顿号
            "、": "\uFE11",  # 顿号
            "。": "\uFE12",  # 句号
            "：": "\uFE13",  # 冒号
            "；": "\uFE14",  # 分号
            "！": "\uFE15",  # 感叹号
            "？": "\uFE16",  # 问号
            "……": "\uFE19",  # 中文全角省略号
            "\u2026": "\uFE19",  # 单个 U+2026
            "\u22EF": "\uFE19",  # ⋯
            "（": "\uFE35",  # 左圆括号
            "）": "\uFE36",  # 右圆括号
            "【": "\uFE3B",  # 左方括号
            "】": "\uFE3C",  # 右方括号
            "《": "\uFE3D",  # 左书名号
            "》": "\uFE3E",  # 右书名号
            "〈": "\uFE3F",  # 左单书名号
            "〉": "\uFE40",  # 右单书名号
            "「": "\uFE41",  # 左单引号（替代）
            "」": "\uFE42",  # 右单引号（替代）
            "『": "\uFE43",  # 左双引号
            "』": "\uFE44",  # 右双引号
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
            
        return text

    def split_text_blocks(self, text: str) -> List[Tuple[str, bool]]:
        """分词逻辑，把字符串分成 [(text, is_english), ...] 这样的块"""
        blocks = []
        buffer = ""
        is_english = None

        for ch in text:
            # 使用 ASCII 范围判断，包含空格、数字、英文标点等
            # 这样 "Hello World." 会被视为一个完整的英文块
            if ord(ch) < 128:
                # 当前是英文/数字/ASCII符号
                if is_english is False:  # 前一个是中文 → 先保存
                    blocks.append((buffer, False))
                    buffer = ""
                buffer += ch
                is_english = True
            else:
                # 当前是中文/全角标点
                if is_english is True:  # 前一个是英文 → 先保存
                    blocks.append((buffer, True))
                    buffer = ""
                buffer += ch
                is_english = False

        if buffer:
            blocks.append((buffer, is_english))
        return blocks

    def calculate_layout(self, text: str, width: int, height: int) -> List[TextBlock]:
        """计算文本布局
        
        Args:
            text: 要排版的文本
            width: 可用宽度
            height: 可用高度
            
        Returns:
            List[TextBlock]: 排版后的文本块列表
        """
        blocks = self.split_text_blocks(text)
        result = []
        
        x = width - self.char_width  # 从右往左
        y = 0

        for text, is_english in blocks:
            if is_english:
                # 英文数字块：整体旋转90度
                br = self.fm.boundingRect(text)
                block_w = br.width()
                block_h = br.height()

                # 检查是否需要换列
                if y + block_w + self.line_spacing > height and height > 0:
                    y = 0
                    x -= self.char_width + self.column_spacing
                    # 只要还有哪怕一点点空间能显示出字的一部分（或者为了排版完整性），就不应该 break
                    # 这里的判断可以宽松一点，比如 x + self.char_width > 0
                    # 即使 x < 0，如果能显示一部分也是好的，或者交给绘制层的 clip 去处理
                    # 但为了性能，如果完全不可见了（x + char_width <= 0），再 break
                    if x + self.char_width <= 0:
                        break

                # 计算文本框和旋转中心
                rect = QRect(x, y, self.char_width, block_w)
                result.append(TextBlock(
                    text=text,
                    is_english=True,
                    rect=rect,
                    rotation=90,
                    ascent=self.fm.ascent()
                ))

                y += block_w + self.line_spacing
            else:
                # 中文和标点：逐字排版
                for ch in text:
                    # 检查是否需要换列
                    if y + self.char_height > height and height > 0:
                        y = 0
                        x -= self.char_width + self.column_spacing
                        # 同上，放宽截断条件
                        if x + self.char_width <= 0:
                            break

                    rect = QRect(x, y, self.char_width, self.char_height)
                    result.append(TextBlock(
                        text=ch,
                        is_english=False,
                        rect=rect
                    ))
                    y += self.char_height

        return result

    def calculate_size(self, text: str, height: int = 0) -> QSize:
        """计算文本需要的尺寸
        
        Args:
            text: 要排版的文本
            height: 当前高度约束（0表示无约束）
            
        Returns:
            QSize: 所需的尺寸
        """
        if not text:
            return QSize(50, 50)

        max_height = 0
        current_height = 0
        cols = 1

        for text, is_english in self.split_text_blocks(text):
            if is_english:
                # 英文数字块
                block_height = self.fm.boundingRect(text).width() + self.line_spacing
                if current_height + block_height > height and height > 0:
                    cols += 1
                    current_height = block_height
                else:
                    current_height += block_height
            else:
                # 中文和标点
                for _ in text:
                    if current_height + self.char_height > height and height > 0:
                        cols += 1
                        current_height = self.char_height
                    else:
                        current_height += self.char_height

            max_height = max(max_height, current_height)

        # 计算总宽度
        total_width = cols * self.char_width + (cols - 1) * self.column_spacing

        # 如果有高度约束，使用约束的高度
        if height > 0:
            # 不要强行设为 height，而是取实际内容高度和限制高度的较小值
            # 或者是只要内容不超过 height，就用内容高度；如果超过了，用 height（但这已经在布局循环中隐含了）
            # 这里主要是为了 minimumSizeHint，如果不填满 height，应该返回实际高度
            # 但如果是 SizeHint，通常返回"最合适的大小"，所以返回 max_height 即可
            # 只有当需要强制填满时才用 height。通常 layout 不需要强制填满。
            pass

        return QSize(total_width, max_height)
