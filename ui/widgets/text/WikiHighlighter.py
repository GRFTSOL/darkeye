
import re
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import Qt, QRegularExpression

class WikiHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        
        self.rules = []
        
        # 1. WikiLinks [[target|alias]] or [[target]]
        # 匹配 [[...]] 内部的内容
        link_format = QTextCharFormat()
        link_format.setForeground(QColor("#3498db"))  # 蓝色
        link_format.setFontUnderline(True)           # 下划线
        link_format.setFontWeight(QFont.Bold)
        
        # 正则：\[\[([^\]]+)\]\]
        # 解释：匹配 [[ 开头，后面跟任意非 ] 字符，以 ]] 结尾
        rule = (QRegularExpression(r"\[\[([^\]]+)\]\]"), link_format)
        self.rules.append(rule)
        
        # 2. Markdown Header (H1, H2, H3) - 三级字号方案
        # H1: # Title
        h1_format = QTextCharFormat()
        h1_format.setForeground(QColor("#e67e22")) # 橙色
        h1_format.setFontWeight(QFont.Bold)
        h1_format.setFontPointSize(24) # 一级大标题
        self.rules.append((QRegularExpression(r"^#\s.*$"), h1_format))

        # H2: ## Title
        h2_format = QTextCharFormat()
        h2_format.setForeground(QColor("#d35400")) # 深橙色
        h2_format.setFontWeight(QFont.Bold)
        h2_format.setFontPointSize(18) # 二级中标题
        self.rules.append((QRegularExpression(r"^##\s.*$"), h2_format))

        # H3+: ### Title
        h3_format = QTextCharFormat()
        h3_format.setForeground(QColor("#c0392b")) # 红褐色
        h3_format.setFontWeight(QFont.Bold)
        h3_format.setFontPointSize(14) # 三级小标题
        self.rules.append((QRegularExpression(r"^###+\s.*$"), h3_format))
        
        # 3. Bold (**bold**)
        bold_format = QTextCharFormat()
        bold_format.setFontWeight(QFont.Bold)
        bold_format.setForeground(QColor("#e74c3c"))
        self.rules.append((QRegularExpression(r"\*\*.*?\*\*"), bold_format))
        
        # 4. Italic (*italic*)
        italic_format = QTextCharFormat()
        italic_format.setFontItalic(True)
        italic_format.setForeground(QColor("#9b59b6"))
        self.rules.append((QRegularExpression(r"\*.*?\*"), italic_format))

    def highlightBlock(self, text):
        for pattern, format in self.rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)
