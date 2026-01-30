import sys
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QLabel
from ui.widgets.text.WikiTextEdit import WikiTextEdit

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = QWidget()
    window.setWindowTitle("WikiTextEdit Test")
    window.resize(600, 500)
    
    layout = QVBoxLayout(window)
    
    label = QLabel("试着输入 [[ 来触发补全，或者点击已有的链接：")
    layout.addWidget(label)
    
    editor = WikiTextEdit()
    editor.setPlaceholderText("在这里输入 markdown 内容...")
    
    # 设置初始内容
    initial_text = """# 一级标题 (H1)
## 二级标题 (H2)
### 三级标题 (H3)

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
