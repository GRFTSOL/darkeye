from pathlib import Path
import logging
import sys

root_dir = Path(__file__).resolve().parents[3]  # 上两级
sys.path.insert(0, str(root_dir))
import re
from PySide6.QtWidgets import (
    QTextEdit,
    QCompleter,
    QLabel,
    QWidget,
    QVBoxLayout,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, QStringListModel, QEvent, QTimer, QSize
from PySide6.QtGui import QTextCursor, QDesktopServices, QPixmap, QImage
from ui.widgets.text.WikiHighlighter import WikiHighlighter
from ui.navigation.router import Router
from core.database.query import (
    get_workid_by_serialnumber,
    exist_actress,
    get_actress_info,
)
from config import WORKCOVER_PATH, ACTRESSIMAGES_PATH
from functools import lru_cache
from darkeye_ui.components.input import TextEdit


class ImagePreviewWindow(QWidget):
    """
    自动补全时的图片预览窗口
    """

    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)  # 不抢占焦点

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.image_label)

        # 设置样式：白色背景，带边框和阴影
        self.setStyleSheet("""
            background-color: #333333;
            border: 1px solid #555555;
            border-radius: 4px;
        """)

        self.current_path = None

    def show_image(self, path):
        """显示图片"""
        if not path:
            self.hide()
            return

        path_str = str(path)
        if self.current_path == path_str and self.isVisible():
            return

        self.current_path = path_str
        img = QImage(str(path_str))
        if not img.isNull():
            w, h = img.width(), img.height()
            crop_x = w - h * 0.7
            crop_w = h * 0.7
            img = img.copy(crop_x, 0, crop_w, h)  # 裁剪
            img = img.scaled(
                QSize(140, 200),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        # 异步或直接加载图片
        # pixmap = QPixmap(path_str)
        # if pixmap.isNull():
        #    self.hide()
        #    return

        # 限制最大高度，保持比例
        # max_height = 200
        # if pixmap.height() > max_height:
        #    pixmap = pixmap.scaledToHeight(max_height, Qt.SmoothTransformation)
        pixmap = QPixmap.fromImage(img)

        self.image_label.setPixmap(pixmap)
        self.resize(pixmap.size() + QSize(4, 4))  # 加上边距
        self.show()


@lru_cache(maxsize=128)
def get_image_path_for_text(text):
    """
    根据文本（番号或女优名）查找图片路径
    """
    if not text:
        return None
    text = str(text).strip()

    from core.database.query import get_cover_image_url_by_serial

    # 2. 尝试作为番号查询
    cover_url = get_cover_image_url_by_serial(text)
    if cover_url:
        path = WORKCOVER_PATH / cover_url
        if path.exists():
            return path

    return None


class WikiTextEdit(TextEdit):
    """
    支持 Markdown 高亮和 [[Wikilink]] 点击跳转的编辑器
    [[跳出自动补全，并且有预览图片的功能
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
        self.completer.setFilterMode(Qt.MatchContains)  # 支持模糊匹配（包含即可）
        self.completer.activated.connect(self._insert_completion)

        # 监听文本变化，用于驱动补全逻辑（比 keyPressEvent 更可靠）
        self.textChanged.connect(self._on_text_changed)

        # 补全数据模型
        self.model = QStringListModel()
        self.completer.setModel(self.model)

        # 美化补全框样式
        self._setup_completer_style()

        # 图片预览窗口
        self.preview_window = ImagePreviewWindow(self)

        # 监听 Popup 事件
        popup = self.completer.popup()
        # 必须开启 MouseTracking 才能实时获取 MouseMove
        popup.setMouseTracking(True)
        popup.installEventFilter(self)

        # 关键：QAbstractItemView 的内容在 viewport 上，必须监听 viewport 的事件
        popup.viewport().setMouseTracking(True)
        popup.viewport().installEventFilter(self)

        # 监听键盘选择
        if popup.selectionModel():
            popup.selectionModel().currentChanged.connect(
                self._on_popup_selection_changed
            )

        self.func = None
        self._current_selected_text = None
        from controller.GlobalSignalBus import global_signals

        global_signals.work_data_changed.connect(self._on_model_changed)

    def set_completer_func(self, func):
        """设置自动补全的函数，通过自动调用函数获取补全词库"""
        self.func = func
        self._on_model_changed()

    def _on_model_changed(self):
        """当数据库变化时，自动补全词库更新"""
        if self.func:
            words = self.func()
            self.set_completer_list(words)

    def set_completer_list(self, words):
        """设置自动补全的词库"""
        self.model.setStringList(words)

    def eventFilter(self, obj, event):
        popup = self.completer.popup()
        if self.completer and (obj == popup or obj == popup.viewport()):
            if event.type() == QEvent.MouseMove:
                # 获取鼠标位置
                pos = event.pos()

                # indexAt 需要的是 viewport 坐标
                # 如果 obj 是 popup (Frame)，需要映射到 viewport 坐标
                # 如果 obj 是 viewport，pos 本身就是 viewport 坐标
                if obj == popup:
                    # 将 popup 坐标转换为 viewport 坐标
                    # viewport() 是 popup 的子控件，通常位于 (frameWidth, frameWidth)
                    pos = popup.viewport().mapFromParent(pos)

                index = popup.indexAt(pos)

                if index.isValid():
                    # 鼠标悬停在某项上 -> 显示该项预览
                    text = index.data()
                    self._update_preview(text)
                else:
                    # 鼠标在列表内但不在项上（如空白处） -> 恢复选中项预览
                    self._update_preview(self._current_selected_text)

            elif event.type() == QEvent.Leave:
                # 鼠标离开列表 -> 恢复选中项预览
                self._update_preview(self._current_selected_text)

            elif event.type() == QEvent.Hide:
                self.preview_window.hide()
                self._current_selected_text = None

        return super().eventFilter(obj, event)

    def _on_popup_selection_changed(self, current, previous):
        if current.isValid():
            text = current.data()
            self._current_selected_text = text
            self._update_preview(text)

    def _update_preview(self, text, rect=None):
        """更新预览窗口位置和内容"""
        # 如果 text 为空，则隐藏
        if not text:
            self.preview_window.hide()
            return

        path = get_image_path_for_text(text)
        if path:
            self.preview_window.show_image(path)

            # 计算位置
            popup = self.completer.popup()
            # 获取整个 Popup 的全局坐标，而不是单个 Item 的坐标
            popup_global_rect = popup.mapToGlobal(popup.rect().topLeft())

            # 默认在左侧，距离 5px
            # Y 轴与 Popup 的顶部对齐，而不是跟随当前 Item
            x = popup_global_rect.x() - self.preview_window.width() - 5
            y = popup_global_rect.y()

            # 如果左侧空间不足，显示在右侧
            if x < 0:
                x = popup_global_rect.x() + popup.width() + 5

            self.preview_window.move(x, y)
        else:
            self.preview_window.hide()

    def _setup_completer_style(self):
        """设置自动补全框的样式"""
        popup = self.completer.popup()

        # 使用 QSS 美化：
        # 1. 设置背景色和圆角
        # 2. 增加 padding 来撑大行高（行间距）
        # 3. 设置选中和悬停效果
        popup.setStyleSheet("""
            QListView {
                background-color: #FFFFFF;
                color: #111111;
                border: 1px solid #454545;
                border-radius: 4px;
                padding: 2px;
                outline: 0;
            }
            
            QListView::item {
                padding: 4px 10px;  /* 上下 8px，增加行高 */
                margin: 2px 0;      /* 增加项目之间的微小间距 */
                border-radius: 4px;
            }
            
            QListView::item:selected {
                background-color: #d5d5d5;
                color: #ffffff;
            }
            
            QListView::item:hover:!selected {
                background-color: #d5d5d5;
            }
            
            QScrollBar:vertical {
                border: none;
                background: #e5e5e5;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #cccccc;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

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

            if (
                mouse_y < cursor_y - cursor_height * 0.5
                or mouse_y > cursor_y + cursor_height * 1.5
            ):
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
                return  # 阻止默认的光标移动（可选，视体验而定）

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
        char_width = font_metrics.averageCharWidth()  # 估算

        # 如果鼠标在光标左边太远或右边太远（允许一点容差，比如半个字宽）
        # 注意：cursor_rect 是字符左侧的插入位置
        # 如果鼠标在字符上，mouse_x 应该在 cursor_x 附近

        # 更严谨的做法：使用 document().documentLayout().hitTest()
        # 但 PySide6 中 QTextEdit 没有直接暴露 hitTest 详情

        # 采用距离判断法：如果点击位置与计算出的光标位置水平距离过大，则视为无效
        if abs(mouse_x - cursor_x) > char_width * 2:  # 2个字宽作为容差
            self.viewport().setCursor(Qt.IBeamCursor)
            super().mouseMoveEvent(event)
            return

        # 增加垂直距离判断，防止点击下方空白触发跳转
        mouse_y = event.position().toPoint().y()
        cursor_y = cursor_rect.y()
        cursor_height = cursor_rect.height()

        # 如果鼠标 Y 坐标不在当前行的高度范围内（允许少量容差，如半行高）
        if (
            mouse_y < cursor_y - cursor_height * 0.5
            or mouse_y > cursor_y + cursor_height * 1.5
        ):
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
        pattern = re.compile(r"\[\[(.*?)\]\]")

        for match in pattern.finditer(text):
            start, end = match.span()
            if start <= position <= end:
                content = match.group(1)
                # 处理别名 [[target|alias]]
                if "|" in content:
                    target = content.split("|")[0]
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
            if event.key() in (
                Qt.Key_Enter,
                Qt.Key_Return,
                Qt.Key_Escape,
                Qt.Key_Tab,
                Qt.Key_Backtab,
            ):
                event.ignore()
                return

        # 默认处理按键
        super().keyPressEvent(event)

        # 快捷键强制呼出 (Ctrl+E)
        is_shortcut = (
            event.modifiers() & Qt.ControlModifier
        ) and event.key() == Qt.Key_E

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
                self.completer.popup().setCurrentIndex(
                    self.completer.completionModel().index(0, 0)
                )
            except Exception as e:
                logging.debug(
                    "WikiTextEdit: 更新补全 popup 当前项失败（可能无候选）: %s",
                    e,
                    exc_info=True,
                )

        # 关键：刷新 popup 位置
        cr = self.cursorRect()
        min_width = 150  # 你想要的最小宽度（像素），可根据实际内容调整
        popup_width = max(
            min_width,
            self.completer.popup().sizeHintForColumn(0)
            + self.completer.popup().verticalScrollBar().sizeHint().width(),
        )
        cr.setWidth(popup_width)
        # cr.setWidth(self.completer.popup().sizeHintForColumn(0) + self.completer.popup().verticalScrollBar().sizeHint().width())
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

        text_between = text_before[last_brackets + 2 :]
        if "]]" in text_between:
            return None

        return text_between

    def _insert_completion(self, completion):
        """插入补全内容"""
        if self.completer.widget() != self:
            return

        tc = self.textCursor()
        # 获取当前前缀长度
        prefix_len = len(self.completer.completionPrefix())

        # 选中光标左侧的前缀文本
        tc.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, prefix_len)

        # 直接用完整的补全内容替换选中的前缀
        tc.insertText(completion)

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
    sample_data = [
        "SONE-979",
        "START-451",
        "START-108",
        "START-403",
        "IPX-327",
        "HODV-21134",
        "ATID-412",
    ]
    editor.set_completer_list(sample_data)

    # 监听点击事件
    editor.link_activated.connect(lambda target: print(f"外部监听到链接点击: {target}"))

    layout.addWidget(editor)

    window.show()
    sys.exit(app.exec())
