# design/demo.py - 展示设计系统组件与主题切换（从项目根目录运行：python -m design.demo）
import sys
from pathlib import Path

# 保证从项目根解析 config、ui
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QGridLayout,
    QFrame,
)
from PySide6.QtCore import Qt

from design import ThemeManager, ThemeId, get_builtin_icon
from design.icon import BUILTIN_ICONS
from ui.components import Button, IconPushButton, Label, Input, StateToggleButton, ToggleSwitch
from ui.basic.FlowLayout import FlowLayout

# 所有内置图标名（来自 resources/icons 内联）
BUILTIN_ICON_NAMES = tuple(BUILTIN_ICONS.keys())


def main():
    app = QApplication(sys.argv)
    theme_mgr = ThemeManager()
    theme_mgr.set_theme(app, ThemeId.LIGHT)

    win = QWidget()
    win.setWindowTitle("设计系统组件 Demo")
    win.setMinimumWidth(360)
    layout = QVBoxLayout(win)
    layout.setSpacing(12)

    layout.addWidget(Label("设计系统组件 Demo"))
    layout.addWidget(Input())
    input_placeholder = Input()
    input_placeholder.setPlaceholderText("占位符示例")
    layout.addWidget(input_placeholder)

    btn_row = QHBoxLayout()
    btn_row.addWidget(Button("默认按钮"))
    btn_row.addWidget(Button("主要按钮", variant="primary"))
    layout.addLayout(btn_row)

    layout.addWidget(Label("状态切换按钮（令牌驱动，随主题变色）"))
    toggle_row = QHBoxLayout()
    toggle_row.addWidget(StateToggleButton(theme_manager=theme_mgr))
    toggle_row.addWidget(StateToggleButton(state1_icon="eye", state2_icon="eye_off", theme_manager=theme_mgr))
    toggle_row.addWidget(StateToggleButton(state1_icon="chevron_down", state2_icon="chevron_up", theme_manager=theme_mgr))
    layout.addLayout(toggle_row)

    layout.addWidget(Label("开关 ToggleSwitch（令牌驱动，随主题变色）"))
    switch_row = QHBoxLayout()
    switch = ToggleSwitch(theme_manager=theme_mgr)
    switch.toggled.connect(lambda on: print("Switch:", on))
    switch_row.addWidget(switch)
    switch_row.addWidget(Label("默认"))
    switch_checked = ToggleSwitch(theme_manager=theme_mgr)
    switch_checked.setChecked(True)
    switch_row.addWidget(switch_checked)
    switch_row.addWidget(Label("默认开"))
    layout.addLayout(switch_row)

    layout.addWidget(Label("图标按钮（令牌驱动，随主题变色）"))
    icon_btn_row = QHBoxLayout()
    for name in ("settings", "search", "refresh_cw", "copy", "trash_2", "save"):
        btn = IconPushButton(icon_name=name, theme_manager=theme_mgr)
        btn.setToolTip(name)
        icon_btn_row.addWidget(btn)
    layout.addLayout(icon_btn_row)

    layout.addWidget(Label("内置图标（来自 resources/icons 内联，颜色随主题）"))
    icon_size = 24
    icon_container = QWidget()
    icon_flow = FlowLayout(icon_container, margin=0, spacing=4)
    icon_buttons: list[tuple[str, Button]] = []

    def refresh_icon_colors():
        color = theme_mgr.tokens().color_icon
        for name, btn in icon_buttons:
            btn.setIcon(get_builtin_icon(name, size=icon_size, color=color))
            btn.setIconSize(btn.iconSize())

    for i, name in enumerate(BUILTIN_ICON_NAMES):
        btn = Button(
            icon=get_builtin_icon(name, size=icon_size, color=theme_mgr.tokens().color_icon),
            icon_size=icon_size,
        )
        btn.setToolTip(name)
        btn.setFixedSize(40, 40)
        icon_buttons.append((name, btn))
        icon_flow.addWidget(btn)
    scroll = QScrollArea()
    scroll.setWidget(icon_container)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setMaximumHeight(220)
    layout.addWidget(scroll)

    def update_theme_buttons():
        for tid, btn in theme_buttons.items():
            btn.setProperty("variant", "primary" if theme_mgr.current() == tid else "default")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        refresh_icon_colors()

    def make_theme_switch(theme_id: ThemeId, label: str):
        def on_click():
            app = QApplication.instance()
            theme_mgr.set_theme(app, theme_id)
            update_theme_buttons()

        btn = Button(label, variant="primary" if theme_mgr.current() == theme_id else "default")
        btn.clicked.connect(on_click)
        return btn

    layout.addWidget(Label("主题切换"))
    theme_buttons = {
        ThemeId.LIGHT: make_theme_switch(ThemeId.LIGHT, "浅色"),
        ThemeId.DARK: make_theme_switch(ThemeId.DARK, "深色"),
        ThemeId.RED: make_theme_switch(ThemeId.RED, "红色"),
    }
    theme_row = QHBoxLayout()
    for btn in theme_buttons.values():
        theme_row.addWidget(btn)
    layout.addLayout(theme_row)

    layout.addStretch()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
