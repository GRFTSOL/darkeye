"""手动测试 PaneWidget：Tab 栏、多页内容、关闭、顺序拖拽、空窗格信号。"""
import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parents[3]  
sys.path.insert(0, str(root_dir))

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
)
from PySide6.QtCore import Qt

from ui.demo.pane_widget import PaneWidget
from config import ICONS_PATH

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    win = QMainWindow()
    win.setWindowTitle("PaneWidget 手动测试")

    central = QWidget()
    layout = QVBoxLayout(central)

    pane = PaneWidget(pane_id="test-pane")
    layout.addWidget(pane)

    # 预置几个 Tab
    for i in range(3):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.addWidget(QLabel(f"内容页 {i + 1} (content-{i})"))
        pane.add_content(f"content-{i+1}", f"Tab {i + 1}", page,QIcon(str(ICONS_PATH/"library-big.svg")))


    # 操作区：添加 Tab、打印状态
    btn_layout = QHBoxLayout()
    add_btn = QPushButton("添加新 Tab")
    def on_add():
        n = pane.content_count() + 1
        w = QWidget()
        w.setLayout(QVBoxLayout())
        w.layout().addWidget(QLabel(f"动态添加的页 {n}"))
        pane.add_content(f"dynamic-{n}", f"动态{n}", w,QIcon(str(ICONS_PATH/"library-big.svg")))
    add_btn.clicked.connect(on_add)
    btn_layout.addWidget(add_btn)

    status_btn = QPushButton("打印状态")
    def on_status():
        print("content_ids:", pane.content_ids())
        print("current_content_id:", pane.current_content_id())
        print("content_count:", pane.content_count())
    status_btn.clicked.connect(on_status)
    btn_layout.addWidget(status_btn)

    pane.pane_empty.connect(lambda p: print("pane_empty 信号:", p.pane_id))
    layout.addLayout(btn_layout)

    win.setCentralWidget(central)
    win.resize(600, 400)
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
