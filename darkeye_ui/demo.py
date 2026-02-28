# darkeye_ui.design.demo - 展示设计系统组件与主题切换（从项目根目录运行：python -m darkeye_ui.design.demo）
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
    QFormLayout,
    QFrame,
    QButtonGroup,
    QGroupBox,
)
from PySide6.QtCore import Qt, QStringListModel, QDateTime, QTime
from PySide6.QtGui import QColor

from darkeye_ui.design import ThemeManager, ThemeId, get_builtin_icon
from darkeye_ui.design.icon import BUILTIN_ICONS
from darkeye_ui.components import (
    Button,
    ClickableSlider,
    ColorPicker,
    ComboBox,
    IconPushButton,
    LineEdit,
    Label,
    StateToggleButton,
    TextEdit,
    ToggleSwitch,
    TokenListView,
    TokenRadioButton,
    TokenCheckBox,
    TokenDateTimeEdit,
    TokenSpinBox,
    TokenTabWidget,
    TokenGroupBox,
    VerticalTextLabel,
)
from darkeye_ui.layouts import FlowLayout

# 所有内置图标名（来自 resources/icons 内联）
BUILTIN_ICON_NAMES = tuple(BUILTIN_ICONS.keys())


def main():
    app = QApplication(sys.argv)
    theme_mgr = ThemeManager()
    theme_mgr.set_theme(app, ThemeId.LIGHT)

    win = QWidget()
    win.setWindowTitle("设计系统组件 Demo")
    win.setMinimumWidth(720)

    # 主布局：可滚动区域 + 两列
    main_layout = QVBoxLayout(win)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    content = QWidget()
    content_layout = QHBoxLayout(content)
    content_layout.setSpacing(24)
    content_layout.setContentsMargins(0, 0, 0, 0)

    def make_column():
        w = QWidget()
        w.setMinimumWidth(320)
        lay = QVBoxLayout(w)
        lay.setSpacing(12)
        return w, lay

    left_col, left = make_column()
    right_col, right = make_column()

    # ----- 左列 -----
    left.addWidget(Label("设计系统组件 Demo"))
    left.addWidget(LineEdit())
    input_placeholder = LineEdit()
    input_placeholder.setPlaceholderText("占位符示例")
    left.addWidget(input_placeholder)

    left.addWidget(Label("多行文本框 TextEdit"))
    text_edit = TextEdit()
    text_edit.setPlaceholderText("多行输入示例…")
    text_edit.setMinimumHeight(80)
    left.addWidget(text_edit)

    btn_row = QHBoxLayout()
    btn_row.addWidget(Button("默认按钮"))
    btn_row.addWidget(Button("主要按钮", variant="primary"))
    left.addLayout(btn_row)

    left.addWidget(Label("状态切换按钮（令牌驱动，随主题变色）"))
    toggle_row = QHBoxLayout()
    toggle_row.addWidget(StateToggleButton(theme_manager=theme_mgr))
    toggle_row.addWidget(StateToggleButton(state1_icon="eye", state2_icon="eye_off", theme_manager=theme_mgr))
    toggle_row.addWidget(StateToggleButton(state1_icon="chevron_down", state2_icon="chevron_up", theme_manager=theme_mgr))
    left.addLayout(toggle_row)

    left.addWidget(Label("开关 ToggleSwitch（令牌驱动，随主题变色）"))
    switch_row = QHBoxLayout()
    switch = ToggleSwitch(theme_manager=theme_mgr)
    switch.toggled.connect(lambda on: print("Switch:", on))
    switch_row.addWidget(switch)
    switch_row.addWidget(Label("默认"))
    switch_checked = ToggleSwitch(theme_manager=theme_mgr)
    switch_checked.setChecked(True)
    switch_row.addWidget(switch_checked)
    switch_row.addWidget(Label("默认开"))
    left.addLayout(switch_row)

    left.addWidget(Label("令牌驱动 RadioButton（随主题变色）"))
    radio_group = QButtonGroup(left_col)
    radio_a = TokenRadioButton("选项 A", left_col)
    radio_b = TokenRadioButton("选项 B", left_col)
    radio_c = TokenRadioButton("选项 C", left_col)
    radio_group.addButton(radio_a)
    radio_group.addButton(radio_b)
    radio_group.addButton(radio_c)
    radio_b.setChecked(True)
    radio_a.toggled.connect(lambda checked: checked and print("选中: 选项 A"))
    radio_b.toggled.connect(lambda checked: checked and print("选中: 选项 B"))
    radio_c.toggled.connect(lambda checked: checked and print("选中: 选项 C"))
    left.addWidget(radio_a)
    left.addWidget(radio_b)
    left.addWidget(radio_c)

    left.addWidget(Label("令牌驱动 CheckBox（随主题变色）"))
    cb_row = QHBoxLayout()
    cb1 = TokenCheckBox("选项一", left_col)
    cb2 = TokenCheckBox("选项二", left_col)
    cb2.setChecked(True)
    cb3 = TokenCheckBox("选项三", left_col)
    cb1.toggled.connect(lambda checked: print("CheckBox 选项一:", checked))
    cb2.toggled.connect(lambda checked: print("CheckBox 选项二:", checked))
    cb3.toggled.connect(lambda checked: print("CheckBox 选项三:", checked))
    cb_row.addWidget(cb1)
    cb_row.addWidget(cb2)
    cb_row.addWidget(cb3)
    left.addLayout(cb_row)

    left.addWidget(Label("令牌驱动 DateTimeEdit（随主题变色）"))
    dt_edit = TokenDateTimeEdit(left_col)
    dt_edit.setDisplayFormat("yy-MM-dd HH:mm")
    dt_edit.setDateTime(QDateTime.currentDateTime())
    dt_edit.setCalendarPopup(True)
    dt_edit.setMinimumTime(QTime(0, 0))
    dt_edit.setMaximumTime(QTime(23, 59))
    dt_edit.dateTimeChanged.connect(lambda dt: print("日期时间:", dt.toString("yyyy-MM-dd HH:mm")))
    left.addWidget(dt_edit)

    left.addWidget(Label("令牌驱动 SpinBox（随主题变色）"))
    spin_section = QWidget()
    spin_layout = QFormLayout(spin_section)
    for label_text, min_val, max_val, default in [
        ("数量", 0, 999, 10),
        ("透明度", 0, 100, 80),
    ]:
        sb = TokenSpinBox(spin_section)
        sb.setMinimum(min_val)
        sb.setMaximum(max_val)
        sb.setValue(default)
        sb.valueChanged.connect(lambda v, n=label_text: print(f"{n}: {v}"))
        spin_layout.addRow(Label(label_text), sb)
    left.addWidget(spin_section)

    left.addWidget(Label("令牌驱动 ClickableSlider（可点击跳转，随主题变色）"))
    slider_section = QWidget()
    slider_layout = QFormLayout(slider_section)
    for label_text, min_val, max_val, default in [
        ("音量", 0, 100, 60),
        ("亮度", 0, 100, 80),
        ("对比度", 0, 100, 50),
    ]:
        s = ClickableSlider(Qt.Orientation.Horizontal, slider_section, theme_manager=theme_mgr)
        s.setMinimum(min_val)
        s.setMaximum(max_val)
        s.setValue(default)
        s.valueChanged.connect(lambda v, n=label_text: print(f"{n}: {v}"))
        slider_layout.addRow(Label(label_text), s)
    left.addWidget(slider_section)

    left.addWidget(Label("令牌驱动 TabWidget（随主题变色）"))
    tab_widget = TokenTabWidget(left_col, theme_manager=theme_mgr)
    tab_widget.addTab(Label("第一个标签页内容"), "概览")
    tab_widget.addTab(Label("第二个标签页内容"), "详情")
    tab_widget.addTab(Label("第三个标签页内容"), "设置")
    left.addWidget(tab_widget)

    # 令牌驱动 GroupBox 示例
    left.addWidget(Label("令牌驱动 GroupBox（随主题变色）"))
    group_box = TokenGroupBox("分组设置示例", left_col, theme_manager=theme_mgr)
    gb_layout = QVBoxLayout(group_box)
    gb_layout.setSpacing(6)
    gb_layout.addWidget(TokenCheckBox("启用此功能", group_box))
    gb_layout.addWidget(TokenCheckBox("显示高级选项", group_box))
    gb_layout.addWidget(TokenRadioButton("模式 A", group_box))
    gb_layout.addWidget(TokenRadioButton("模式 B", group_box))
    left.addWidget(group_box)

    left.addWidget(Label("颜色选择器 ColorPicker（点击弹出色轮）"))
    color_row = QHBoxLayout()
    picker_default = ColorPicker()
    picker_default.colorChanged.connect(lambda c: print("颜色已更改:", c))
    color_row.addWidget(picker_default)
    picker_pink = ColorPicker(QColor("#FF4081"))
    picker_pink.colorChanged.connect(lambda c: print("颜色已更改:", c))
    color_row.addWidget(picker_pink)
    # 矩形但不显示文字
    picker_no_text = ColorPicker(QColor("#4CAF50"), show_text=False)
    picker_no_text.colorChanged.connect(lambda c: print("颜色已更改:", c))
    color_row.addWidget(picker_no_text)
    # 圆形（无文字）
    picker_circle = ColorPicker(QColor("#2196F3"), shape=ColorPicker.ShapeCircle)
    picker_circle.colorChanged.connect(lambda c: print("颜色已更改:", c))
    color_row.addWidget(picker_circle)
    left.addLayout(color_row)

    # 主题切换（左列底部）
    theme_options = [
        (ThemeId.LIGHT, "浅色"),
        (ThemeId.DARK, "深色"),
        (ThemeId.RED, "红色"),
        (ThemeId.GREEN, "绿色"),
        (ThemeId.YELLOW, "黄色"),
        (ThemeId.BLUE, "蓝色"),
        (ThemeId.PURPLE, "紫色"),
    ]
    theme_combo = ComboBox()
    for _tid, label in theme_options:
        theme_combo.addItem(label)
    current_index = next(i for i, (tid, _) in enumerate(theme_options) if tid == theme_mgr.current())
    theme_combo.setCurrentIndex(current_index)

    def refresh_icon_colors():
        color = theme_mgr.tokens().color_icon
        for name, btn in icon_buttons:
            btn.setIcon(get_builtin_icon(name, size=icon_size, color=color))
            btn.setIconSize(btn.iconSize())

    def on_theme_changed(index: int):
        app = QApplication.instance()
        theme_id = theme_options[index][0]
        theme_mgr.set_theme(app, theme_id)
        refresh_icon_colors()

    theme_combo.currentIndexChanged.connect(on_theme_changed)
    left.addWidget(Label("主题切换"))
    left.addWidget(theme_combo)
    left.addStretch()

    # ----- 右列 -----
    right.addWidget(Label("图标按钮（令牌驱动，随主题变色）"))
    icon_btn_row = QHBoxLayout()
    for name in ("settings", "search", "refresh_cw", "copy", "trash_2", "save"):
        btn = IconPushButton(icon_name=name, theme_manager=theme_mgr)
        btn.setToolTip(name)
        icon_btn_row.addWidget(btn)
    right.addLayout(icon_btn_row)

    right.addWidget(Label("内置图标（来自 resources/icons 内联，颜色随主题）"))
    icon_size = 24
    icon_container = QWidget()
    icon_flow = FlowLayout(icon_container, margin=0, spacing=4)
    icon_buttons: list[tuple[str, Button]] = []

    for i, name in enumerate(BUILTIN_ICON_NAMES):
        btn = Button(
            icon=get_builtin_icon(name, size=icon_size, color=theme_mgr.tokens().color_icon),
            icon_size=icon_size,
        )
        btn.setToolTip(name)
        btn.setFixedSize(40, 40)
        icon_buttons.append((name, btn))
        icon_flow.addWidget(btn)
    icon_scroll = QScrollArea()
    icon_scroll.setWidget(icon_container)
    icon_scroll.setWidgetResizable(True)
    icon_scroll.setFrameShape(QFrame.Shape.NoFrame)
    icon_scroll.setMaximumHeight(220)
    right.addWidget(icon_scroll)

    right.addWidget(Label("Label tone 变体（normal / inverse）"))
    label_tone_row = QHBoxLayout()
    label_tone_row.addWidget(Label("普通背景 normal"))
    label_tone_row.addWidget(Label("反相文字 inverse", tone="inverse"))
    right.addLayout(label_tone_row)

    right.addWidget(Label("竖排文字 VerticalTextLabel（tone 变体）"))
    vertical_row = QHBoxLayout()
    vlabel_normal = VerticalTextLabel(
        "普通竖排\nnormal",
        theme_manager=theme_mgr,
        tone="normal",
    )
    vlabel_normal.setMinimumHeight(160)
    vertical_row.addWidget(vlabel_normal)
    vlabel_inverse = VerticalTextLabel(
        "反相文字\ninverse",
        theme_manager=theme_mgr,
        tone="inverse",
    )
    vlabel_inverse.setMinimumHeight(160)
    vertical_row.addWidget(vlabel_inverse)
    right.addLayout(vertical_row)

    right.addWidget(Label("QListView 跟随令牌 TokenListView（随主题变色）"))
    list_view = TokenListView()
    list_view.setMinimumHeight(120)
    list_model = QStringListModel(["选项 A", "选项 B", "选项 C", "选项 D", "选项 E"])
    list_view.setModel(list_model)
    right.addWidget(list_view)

    right.addStretch()

    content_layout.addWidget(left_col, 1)
    content_layout.addWidget(right_col, 1)
    scroll.setWidget(content)
    main_layout.addWidget(scroll)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
