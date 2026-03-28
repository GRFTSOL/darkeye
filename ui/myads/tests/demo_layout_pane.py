"""可显示的 Demo：把 LayoutTree 和 PaneWidget 放进窗口，以选中的窗格为节点进行拆分测试。"""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root_dir))

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from PySide6.QtCore import Qt, QEvent, QObject

from ui.demo.layout_tree import LayoutTree, SplitModelNode
from ui.demo.pane_widget import PaneWidget

SPLITTER_STYLE = """
    QSplitter::handle {
        background: #cccccc;
        width: 4px;
        height: 4px;
        border: none;
        margin: 0;
    }
    QSplitter::handle:hover {
        background: #888;
    }
"""


def _style_splitter(splitter):
    splitter.setStyleSheet(SPLITTER_STYLE)
    splitter.setChildrenCollapsible(False)


def _placeholder(text: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    layout.addWidget(QLabel(text))
    return w


def _pane_under_cursor(tree: LayoutTree, global_pos):
    """从点击位置向上查找属于 tree 的 PaneWidget。"""
    w = QApplication.widgetAt(global_pos)
    while w:
        if isinstance(w, PaneWidget) and tree.find_parent_of_pane(w) is not None:
            return w
        w = w.parent() if hasattr(w, "parent") else None
    return None


def _tree_state_str(tree: LayoutTree) -> str:
    """返回当前布局树的状态字符串（多行）。"""
    lines = tree.dump_tree()
    if not lines or (len(lines) == 1 and "children=0" in lines[0]):
        return "LayoutTree(空)"
    return "LayoutTree:\n" + "\n".join(lines)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 布局树：根为 SplitModelNode（逻辑根设计）
    root = SplitModelNode(Qt.Horizontal, [])
    tree = LayoutTree(root, style_splitter=_style_splitter)

    def on_pane_empty(pane: PaneWidget):
        """关闭窗格最后一个 Tab 时从树中移除并回收该窗格。"""
        pane.pane_empty.disconnect(on_pane_empty)
        tree.remove_pane(pane)

    def register_pane(pane: PaneWidget):
        pane.pane_empty.connect(on_pane_empty)

    p1 = PaneWidget(pane_id="p1")
    p1.add_content(
        "c1",
        "窗格 1",
        _placeholder("这是第一个窗格 (p1)\n点击窗格可选中，再点按钮以该窗格为节点拆分"),
    )
    tree.add_pane_to_root(p1)
    register_pane(p1)

    # 用于“拆分”时选中的窗格（点击某窗格即选中，以该窗格为节点进行拆分）
    split_target_holder = [p1]
    pane_counter = 2

    def add_pane_right():
        nonlocal pane_counter
        split_target = split_target_holder[0]
        new_pane = PaneWidget(pane_id=f"p{pane_counter}")
        new_pane.add_content(
            f"c{pane_counter}",
            f"窗格 {pane_counter}",
            _placeholder(f"窗格 p{pane_counter}\n在选中窗格右侧水平拆分加入"),
        )
        if tree.find_parent_of_pane(split_target) is not None:
            tree.split(
                split_target, Qt.Horizontal, insert_before=False, new_pane=new_pane
            )
        else:
            tree.add_pane_to_root(new_pane)
            split_target_holder[0] = new_pane
        register_pane(new_pane)
        pane_counter += 1

    def add_pane_below():
        nonlocal pane_counter
        split_target = split_target_holder[0]
        new_pane = PaneWidget(pane_id=f"p{pane_counter}")
        new_pane.add_content(
            f"c{pane_counter}",
            f"窗格 {pane_counter}",
            _placeholder(f"窗格 p{pane_counter}\n在选中窗格下方垂直拆分加入"),
        )
        if tree.find_parent_of_pane(split_target) is not None:
            tree.split(
                split_target, Qt.Vertical, insert_before=False, new_pane=new_pane
            )
        else:
            tree.add_pane_to_root(new_pane)
            split_target_holder[0] = new_pane
        register_pane(new_pane)
        pane_counter += 1

    # 窗口：顶部按钮 + 下方为树的 splitter
    win = QMainWindow()
    win.setWindowTitle("LayoutTree Demo — 以选中窗格为节点拆分")

    central = QWidget()
    layout = QVBoxLayout(central)
    layout.setContentsMargins(8, 8, 8, 8)

    # 显示当前选中的窗格，点击布局区域内某窗格即可选中
    current_target_label = QLabel("当前拆分目标: p1")
    layout.addWidget(current_target_label)

    def update_target_label():
        current_target_label.setText("当前拆分目标: " + split_target_holder[0].pane_id)

    class PaneSelectFilter(QObject):
        """点击窗格时将其设为当前拆分目标。"""

        def eventFilter(self, obj, event):
            if (
                event.type() == QEvent.MouseButtonPress
                and event.button() == Qt.LeftButton
            ):
                pos = (
                    event.globalPosition().toPoint()
                    if hasattr(event, "globalPosition")
                    else event.globalPos()
                )
                pane = _pane_under_cursor(tree, pos)
                if pane is not None:
                    split_target_holder[0] = pane
                    update_target_label()
            return False

    _pane_select_filter = PaneSelectFilter(central)
    central.installEventFilter(_pane_select_filter)

    btn_row = QHBoxLayout()
    btn_row.addWidget(QLabel("以当前选中窗格为节点："))
    btn_right = QPushButton("右侧添加窗格 (水平拆分)")
    btn_right.clicked.connect(add_pane_right)
    btn_row.addWidget(btn_right)
    btn_below = QPushButton("下方添加窗格 (垂直拆分)")
    btn_below.clicked.connect(add_pane_below)
    btn_row.addWidget(btn_below)
    btn_print = QPushButton("打印当前树状态")
    btn_print.clicked.connect(lambda: print(_tree_state_str(tree)))
    btn_row.addWidget(btn_print)
    btn_row.addStretch()
    layout.addLayout(btn_row)

    layout.addWidget(tree.root(), 1)

    win.setCentralWidget(central)
    win.resize(700, 450)
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
