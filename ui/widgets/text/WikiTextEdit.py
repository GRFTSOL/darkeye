from pathlib import Path
import sys
root_dir = Path(__file__).resolve().parents[3]  # 上两级
sys.path.insert(0, str(root_dir))
import re
from PySide6.QtWidgets import QTextEdit, QCompleter
from PySide6.QtCore import Qt, Signal, QStringListModel
from PySide6.QtGui import QTextCursor, QDesktopServices
from ui.widgets.text.WikiHighlighter import WikiHighlighter
from ui.navigation.router import Router
from core.database.query import get_workid_by_serialnumber

class WikiTextEdit(QTextEdit):
    """
    支持 Markdown 高亮和 [[Wikilink]] 点击跳转的编辑器
    """
    
    # 信号：当点击了内部链接时触发，参数为 (target, alias)
    # 如果处理了该信号，可以阻止默认的跳转行为（如果有的话）
    link_activated = Signal(str) 

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.highlighter = WikiHighlighter(self.document())
        self.setMouseTracking(True)  # 开启鼠标追踪以支持悬停效果（可选）
        
        # 初始化自动补全器
        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains) # 支持模糊匹配（包含即可）
        self.completer.activated.connect(self._insert_completion)
        
        # 监听文本变化，用于驱动补全逻辑（比 keyPressEvent 更可靠）
        self.textChanged.connect(self._on_text_changed)
        
        # 补全数据模型
        self.model = QStringListModel()
        self.completer.setModel(self.model)

    def set_completer_list(self, words):
        """设置自动补全的词库"""
        self.model.setStringList(words)

    def mousePressEvent(self, event):
        """处理鼠标点击事件，检测是否点击了 [[链接]]"""
        if event.button() == Qt.LeftButton:
            cursor = self.cursorForPosition(event.position().toPoint())
            
            # 同样的范围检查逻辑，防止点击空白处触发
            cursor_rect = self.cursorRect(cursor)
            mouse_x = event.position().toPoint().x()
            cursor_x = cursor_rect.x()
            font_metrics = self.fontMetrics()
            char_width = font_metrics.averageCharWidth()
            
            if abs(mouse_x - cursor_x) > char_width:
                super().mousePressEvent(event)
                return
                
            mouse_y = event.position().toPoint().y()
            cursor_y = cursor_rect.y()
            cursor_height = cursor_rect.height()
            
            if mouse_y < cursor_y - cursor_height * 0.5 or mouse_y > cursor_y + cursor_height * 1.5:
                super().mousePressEvent(event)
                return

            position = cursor.position()
            
            # 获取当前文档文本
            text = self.toPlainText()
            
            # 简单的正则查找当前点击位置是否在 [[...]] 内
            # 注意：这种简单的查找可能在某些复杂嵌套或长文本下有局限，
            # 但配合 Highlighter 的视觉反馈，通常足够好用。
            # 更精确的做法是遍历所有匹配项，看 position 是否在 span 内。
            
            link_target = self._get_link_at_position(text, position)
            if link_target:
                self._handle_link_click(link_target)
                return # 阻止默认的光标移动（可选，视体验而定）

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """处理鼠标移动事件，更新光标形状"""
        # 1. 获取鼠标位置的 QTextCursor
        cursor = self.cursorForPosition(event.position().toPoint())
        
        # 2. 关键修正：检查鼠标是否真的在文字上方（而不是行尾空白处）
        # 获取光标所在行的矩形区域
        cursor_rect = self.cursorRect(cursor)
        # 获取字符的大致宽度（如果字体不等宽这只是近似，但通常够用）
        # 更精确的做法是 cursorRect(cursor) 的 right 边缘
        # 但 cursorRect 返回的是光标插入符的位置（细线）
        
        # 简单判断：如果点击位置离光标位置太远（比如超过一个字宽），说明是在行尾空白处
        # 这里用一种更通用的方法：判断鼠标位置是否在 Block 的实际渲染区域内
        # 或者，比较 cursorRect.x() 和 event.pos().x()
        
        # 修正逻辑：
        # cursorForPosition 会返回最近的字符位置。如果点在行尾很远的地方，它会返回行末位置。
        # 我们需要判断 event.pos() 是否紧邻 cursorRect
        
        mouse_x = event.position().toPoint().x()
        cursor_x = cursor_rect.x()
        font_metrics = self.fontMetrics()
        char_width = font_metrics.averageCharWidth() # 估算
        
        # 如果鼠标在光标左边太远或右边太远（允许一点容差，比如半个字宽）
        # 注意：cursor_rect 是字符左侧的插入位置
        # 如果鼠标在字符上，mouse_x 应该在 cursor_x 附近
        
        # 更严谨的做法：使用 document().documentLayout().hitTest()
        # 但 PySide6 中 QTextEdit 没有直接暴露 hitTest 详情
        
        # 采用距离判断法：如果点击位置与计算出的光标位置水平距离过大，则视为无效
        if abs(mouse_x - cursor_x) > char_width * 2: # 2个字宽作为容差
            self.viewport().setCursor(Qt.IBeamCursor)
            super().mouseMoveEvent(event)
            return

        # 增加垂直距离判断，防止点击下方空白触发跳转
        mouse_y = event.position().toPoint().y()
        cursor_y = cursor_rect.y()
        cursor_height = cursor_rect.height()
        
        # 如果鼠标 Y 坐标不在当前行的高度范围内（允许少量容差，如半行高）
        if mouse_y < cursor_y - cursor_height * 0.5 or mouse_y > cursor_y + cursor_height * 1.5:
            self.viewport().setCursor(Qt.IBeamCursor)
            super().mouseMoveEvent(event)
            return

        position = cursor.position()
        text = self.toPlainText()
        
        link_target = self._get_link_at_position(text, position)
        if link_target:
            self.viewport().setCursor(Qt.PointingHandCursor)
        else:
            self.viewport().setCursor(Qt.IBeamCursor)
            
        super().mouseMoveEvent(event)

    def _get_link_at_position(self, text, position):
        """
        判断指定位置是否在 [[...]] 链接内，并返回目标
        """
        # 使用与 Highlighter 相同的正则
        pattern = re.compile(r'\[\[(.*?)\]\]')
        
        for match in pattern.finditer(text):
            start, end = match.span()
            if start <= position <= end:
                content = match.group(1)
                # 处理别名 [[target|alias]]
                if '|' in content:
                    target = content.split('|')[0]
                else:
                    target = content
                return target.strip()
        return None

    def _handle_link_click(self, target):
        """处理链接跳转逻辑"""
        print(f"Clicked wikilink: {target}")
        
        # 尝试通过 Router 跳转
        # 这里假设 target 是作品番号 (如 SNIS-123) 或女优ID (如 a123) 或其他
        # 具体逻辑需要根据业务调整
        
        router = Router.instance()
        
        # 简单的启发式跳转逻辑
        # 1. 如果是 "w" 开头的ID (w123) -> work
        # 2. 如果是 "a" 开头的ID (a123) -> actress
        # 3. 否则尝试作为番号搜索或跳转
        
        if target.startswith("w") and target[1:].isdigit():
             router.push("work", work_id=int(target[1:]))
        elif target.startswith("a") and target[1:].isdigit():
             router.push("single_actress", actress_id=int(target[1:]))
        else:
            # 尝试作为番号查找对应的 work_id
            work_id = get_workid_by_serialnumber(target)
            if work_id:
                router.push("work", work_id=work_id)
            else:
                # 没找到则只发射信号，供外部处理（如搜索）
                self.link_activated.emit(target)


    def keyPressEvent(self, event):
        """处理键盘事件，主要负责拦截导航键"""
        # print(f"DEBUG: KeyPress {event.key()}")
        if self.completer and self.completer.popup().isVisible():
            # 如果补全框可见，优先处理补全框的按键
            if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab):
                event.ignore()
                return

        # 默认处理按键
        super().keyPressEvent(event)
        
        # 快捷键强制呼出 (Ctrl+E)
        is_shortcut = (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_E
        
        if is_shortcut and self.completer:
             self._update_completer_popup()

    def _on_text_changed(self):
        """文本变化时触发补全逻辑"""
        self._update_completer_popup()

    def _update_completer_popup(self):
        """更新补全框状态"""
        if not self.completer:
            return
            
        # 1. 获取光标前的文本
        completion_prefix = self._get_completion_prefix()
        
        # 2. 如果前缀为空（说明不在 [[ 内），则隐藏
        if completion_prefix is None:
            self.completer.popup().hide()
            return
            
        # 3. 更新补全前缀并弹出
        # print(f"DEBUG: prefix='{completion_prefix}'")
        if completion_prefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(completion_prefix)
            try:
                self.completer.popup().setCurrentIndex(self.completer.completionModel().index(0, 0))
            except Exception:
                pass
        
        # 关键：刷新 popup 位置
        cr = self.cursorRect()
        cr.setWidth(self.completer.popup().sizeHintForColumn(0) + self.completer.popup().verticalScrollBar().sizeHint().width())
        self.completer.complete(cr)

    def _get_completion_prefix(self):
        """
        获取光标前的补全前缀。
        返回 None 表示不在补全区域。
        返回 "" 表示刚输入 [[
        返回 "SN" 表示输入了 [[SN
        """
        cursor = self.textCursor()
        block_text = cursor.block().text()
        pos_in_block = cursor.positionInBlock()
        
        # 截取光标前的文本
        text_before = block_text[:pos_in_block]
        
        # 反向查找最近的 [[
        last_brackets = text_before.rfind("[[")
        
        if last_brackets == -1:
            return None
            
        # 检查 [[ 后面是否有 ]] (避免在已闭合的引用中补全)
        # 注意：这种简单检查可能不完美，但够用
        # 如果 [[ 后面已经有 ]] 且光标在 ]] 后面，则无效
        # 但我们这里只看 text_before，所以只要没有闭合的 ]] 在 [[ 和 光标之间即可
        
        text_between = text_before[last_brackets + 2:]
        if "]]" in text_between:
            return None
            
        return text_between

    def _insert_completion(self, completion):
        """插入补全内容"""
        if self.completer.widget() != self:
            return
            
        tc = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        tc.movePosition(QTextCursor.Left)
        tc.movePosition(QTextCursor.EndOfWord)
        tc.insertText(completion[-extra:])
        # 自动补全后加上 ]]
        tc.insertText("]]")
        self.setTextCursor(tc)

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QLabel

    app = QApplication(sys.argv)
    
    window = QWidget()
    window.setWindowTitle("WikiTextEdit Test")
    window.resize(600, 400)
    
    layout = QVBoxLayout(window)
    
    label = QLabel("试着输入 [[ 来触发补全，或者点击已有的链接：")
    layout.addWidget(label)
    
    editor = WikiTextEdit()
    editor.setPlaceholderText("在这里输入 markdown 内容...")
    
    # 设置初始内容
    initial_text = """# 测试文档
    
这是一个 **WikiTextEdit** 测试。

你可以引用作品，例如 [[SNIS-123]] 或者 [[ABP-456|ABP的神作]]。

也可以引用女优，例如 [[a1024|某位女优]]。

试着在下面输入 [[ 看看自动补全：
"""
    editor.setPlainText(initial_text)
    
    # 设置补全词库
    sample_data = ["SNIS-123", "SNIS-456", "ABP-123", "ABP-999", "IPX-001", "a1024", "w2048"]
    editor.set_completer_list(sample_data)
    
    # 监听点击事件
    editor.link_activated.connect(lambda target: print(f"外部监听到链接点击: {target}"))
    
    layout.addWidget(editor)
    
    window.show()
    sys.exit(app.exec())
