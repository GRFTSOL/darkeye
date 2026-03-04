# darkeye_ui.demo - 展示设计系统组件与主题切换（从项目根目录运行：python -m darkeye_ui.demo）
"""Sidebar2 + QStackedWidget 多页演示：按钮、文本、开关、数值、容器、颜色图标、主题。"""
import sys
from pathlib import Path

# 保证从项目根解析 config、ui、app_context
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app_context import set_theme_manager

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QFormLayout,
    QFrame,
    QButtonGroup,
    QStackedWidget,
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
    Sidebar2,
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

# 主题选项（多处复用）
THEME_OPTIONS = [
    (ThemeId.LIGHT, "浅色"),
    (ThemeId.DARK, "深色"),
    (ThemeId.RED, "红色"),
    (ThemeId.GREEN, "绿色"),
    (ThemeId.YELLOW, "黄色"),
    (ThemeId.BLUE, "蓝色"),
    (ThemeId.PURPLE, "紫色"),
]


def _make_scrollable_page() -> tuple[QWidget, QVBoxLayout, QVBoxLayout]:
    """创建可滚动的页面容器，返回 (page_widget, left_layout, right_layout)。"""
    page = QWidget()
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    content = QWidget()
    lay = QHBoxLayout(content)
    lay.setSpacing(24)
    lay.setContentsMargins(16, 16, 16, 16)

    def make_column():
        w = QWidget()
        w.setMinimumWidth(320)
        col = QVBoxLayout(w)
        col.setSpacing(12)
        return w, col

    left_col, left = make_column()
    right_col, right = make_column()
    lay.addWidget(left_col, 1)
    lay.addWidget(right_col, 1)
    scroll.setWidget(content)
    page_lay = QVBoxLayout(page)
    page_lay.setContentsMargins(0, 0, 0, 0)
    page_lay.addWidget(scroll)
    return page, left, right


def _build_page_buttons(theme_mgr: ThemeManager) -> QWidget:
    """按钮页：Button、StateToggleButton、IconPushButton。"""
    page, left, right = _make_scrollable_page()
    left.addWidget(Label("设计系统组件 Demo - 按钮"))
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
    right.addWidget(Label("图标按钮（令牌驱动，随主题变色）"))
    icon_btn_row = QHBoxLayout()
    for name in ("settings", "search", "refresh_cw", "copy", "trash_2", "save"):
        btn = IconPushButton(icon_name=name, theme_manager=theme_mgr)
        btn.setToolTip(name)
        icon_btn_row.addWidget(btn)
    right.addLayout(icon_btn_row)
    left.addStretch()
    right.addStretch()
    return page


def _build_page_text(theme_mgr: ThemeManager) -> QWidget:
    """文本与输入页：Label、LineEdit、TextEdit、VerticalTextLabel。"""
    page, left, right = _make_scrollable_page()
    left.addWidget(Label("文本与输入"))
    left.addWidget(LineEdit())
    input_ph = LineEdit()
    input_ph.setPlaceholderText("占位符示例")
    left.addWidget(input_ph)
    left.addWidget(Label("多行文本框 TextEdit"))
    text_edit = TextEdit()
    text_edit.setPlaceholderText("多行输入示例…")
    text_edit.setMinimumHeight(80)
    left.addWidget(text_edit)
    right.addWidget(Label("Label tone 变体（normal / inverse）"))
    tone_row = QHBoxLayout()
    tone_row.addWidget(Label("普通背景 normal"))
    tone_row.addWidget(Label("反相文字 inverse", tone="inverse"))
    right.addLayout(tone_row)
    right.addWidget(Label("竖排文字 VerticalTextLabel（tone 变体）"))
    vert_row = QHBoxLayout()
    v1 = VerticalTextLabel("普通竖排\nnormal", theme_manager=theme_mgr, tone="normal")
    v1.setMinimumHeight(160)
    v2 = VerticalTextLabel("反相文字\ninverse", theme_manager=theme_mgr, tone="inverse")
    v2.setMinimumHeight(160)
    vert_row.addWidget(v1)
    vert_row.addWidget(v2)
    right.addLayout(vert_row)
    right.addWidget(Label("TokenListView（随主题变色）"))
    list_view = TokenListView()
    list_view.setMinimumHeight(120)
    list_view.setModel(QStringListModel(["选项 A", "选项 B", "选项 C", "选项 D", "选项 E"]))
    right.addWidget(list_view)
    left.addStretch()
    right.addStretch()
    return page


def _build_page_toggles(theme_mgr: ThemeManager) -> QWidget:
    """开关选择页：ToggleSwitch、TokenRadioButton、TokenCheckBox。"""
    page, left, right = _make_scrollable_page()
    parent = page
    left.addWidget(Label("开关 ToggleSwitch（令牌驱动，随主题变色）"))
    switch_row = QHBoxLayout()
    s1 = ToggleSwitch(theme_manager=theme_mgr)
    s1.toggled.connect(lambda on: print("Switch:", on))
    switch_row.addWidget(s1)
    switch_row.addWidget(Label("默认"))
    s2 = ToggleSwitch(theme_manager=theme_mgr)
    s2.setChecked(True)
    switch_row.addWidget(s2)
    switch_row.addWidget(Label("默认开"))
    left.addLayout(switch_row)
    left.addWidget(Label("令牌驱动 RadioButton（随主题变色）"))
    radio_group = QButtonGroup(parent)
    for text in ("选项 A", "选项 B", "选项 C"):
        r = TokenRadioButton(text, parent)
        radio_group.addButton(r)
        left.addWidget(r)
    rb = list(radio_group.buttons())[1]
    rb.setChecked(True)
    left.addWidget(Label("令牌驱动 CheckBox（随主题变色）"))
    cb_row = QHBoxLayout()
    for t in ("选项一", "选项二", "选项三"):
        c = TokenCheckBox(t, parent)
        if t == "选项二":
            c.setChecked(True)
        cb_row.addWidget(c)
    left.addLayout(cb_row)
    left.addStretch()
    right.addStretch()
    return page


def _build_page_inputs(theme_mgr: ThemeManager) -> QWidget:
    """数值与滑块页：TokenDateTimeEdit、TokenSpinBox、ClickableSlider。"""
    page, left, right = _make_scrollable_page()
    parent = page
    left.addWidget(Label("令牌驱动 DateTimeEdit（随主题变色）"))
    dt = TokenDateTimeEdit(parent)
    dt.setDisplayFormat("yy-MM-dd HH:mm")
    dt.setDateTime(QDateTime.currentDateTime())
    dt.setCalendarPopup(True)
    dt.setMinimumTime(QTime(0, 0))
    dt.setMaximumTime(QTime(23, 59))
    left.addWidget(dt)
    left.addWidget(Label("令牌驱动 SpinBox（随主题变色）"))
    spin_section = QWidget()
    spin_layout = QFormLayout(spin_section)
    for label_text, min_val, max_val, default in [("数量", 0, 999, 10), ("透明度", 0, 100, 80)]:
        sb = TokenSpinBox(parent)
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
        s = ClickableSlider(Qt.Orientation.Horizontal, parent, theme_manager=theme_mgr)
        s.setMinimum(min_val)
        s.setMaximum(max_val)
        s.setValue(default)
        s.valueChanged.connect(lambda v, n=label_text: print(f"{n}: {v}"))
        slider_layout.addRow(Label(label_text), s)
    left.addWidget(slider_section)
    left.addStretch()
    right.addStretch()
    return page


def _build_page_containers(theme_mgr: ThemeManager) -> QWidget:
    """标签页分组页：TokenTabWidget、TokenGroupBox。"""
    page, left, right = _make_scrollable_page()
    parent = page
    left.addWidget(Label("令牌驱动 TabWidget（随主题变色）"))
    tab = TokenTabWidget(parent, theme_manager=theme_mgr)
    tab.addTab(Label("第一个标签页内容"), "概览")
    tab.addTab(Label("第二个标签页内容"), "详情")
    tab.addTab(Label("第三个标签页内容"), "设置")
    left.addWidget(tab)
    left.addWidget(Label("令牌驱动 GroupBox（随主题变色）"))
    gb = TokenGroupBox("分组设置示例", parent, theme_manager=theme_mgr)
    gb_lay = QVBoxLayout(gb)
    gb_lay.setSpacing(6)
    gb_lay.addWidget(TokenCheckBox("启用此功能", parent))
    gb_lay.addWidget(TokenCheckBox("显示高级选项", parent))
    gb_lay.addWidget(TokenRadioButton("模式 A", parent))
    gb_lay.addWidget(TokenRadioButton("模式 B", parent))
    left.addWidget(gb)
    left.addStretch()
    right.addStretch()
    return page


def _build_page_color_icons(
    theme_mgr: ThemeManager, refresh_callbacks: list,
) -> QWidget:
    """颜色与图标页：ColorPicker、内置图标网格。"""
    page, left, right = _make_scrollable_page()
    left.addWidget(Label("颜色选择器 ColorPicker（点击弹出色轮）"))
    color_row = QHBoxLayout()
    p1 = ColorPicker()
    p1.colorChanged.connect(lambda c: print("颜色已更改:", c))
    color_row.addWidget(p1)
    p2 = ColorPicker(QColor("#FF4081"))
    p2.colorChanged.connect(lambda c: print("颜色已更改:", c))
    color_row.addWidget(p2)
    p3 = ColorPicker(QColor("#4CAF50"), show_text=False)
    p3.colorChanged.connect(lambda c: print("颜色已更改:", c))
    color_row.addWidget(p3)
    p4 = ColorPicker(QColor("#2196F3"), shape=ColorPicker.ShapeCircle)
    p4.colorChanged.connect(lambda c: print("颜色已更改:", c))
    color_row.addWidget(p4)
    left.addLayout(color_row)
    right.addWidget(Label("内置图标（来自 resources/icons 内联，颜色随主题）"))
    icon_size = 24
    icon_container = QWidget()
    icon_flow = FlowLayout(icon_container, margin=0, spacing=4)
    icon_buttons: list[tuple[str, Button]] = []
    for name in BUILTIN_ICON_NAMES:
        btn = Button(
            icon=get_builtin_icon(name, size=icon_size, color=theme_mgr.tokens().color_icon),
            icon_size=icon_size,
        )
        btn.setToolTip(name)
        btn.setFixedSize(40, 40)
        icon_buttons.append((name, btn))
        icon_flow.addWidget(btn)

    def refresh():
        color = theme_mgr.tokens().color_icon
        for name, btn in icon_buttons:
            btn.setIcon(get_builtin_icon(name, size=icon_size, color=color))
            btn.setIconSize(btn.iconSize())

    refresh_callbacks.append(refresh)
    icon_scroll = QScrollArea()
    icon_scroll.setWidget(icon_container)
    icon_scroll.setWidgetResizable(True)
    icon_scroll.setFrameShape(QFrame.Shape.NoFrame)
    icon_scroll.setMaximumHeight(220)
    right.addWidget(icon_scroll)
    left.addStretch()
    right.addStretch()
    return page


def _build_page_theme(
    theme_mgr: ThemeManager, refresh_callbacks: list,
) -> QWidget:
    """主题切换页。"""
    page, left, right = _make_scrollable_page()
    left.addWidget(Label("主题切换"))
    theme_combo = ComboBox()
    for _tid, label in THEME_OPTIONS:
        theme_combo.addItem(label)
    idx = next(i for i, (tid, _) in enumerate(THEME_OPTIONS) if tid == theme_mgr.current())
    theme_combo.setCurrentIndex(idx)

    def on_theme_changed(index: int):
        app = QApplication.instance()
        if app:
            theme_mgr.set_theme(app, THEME_OPTIONS[index][0])
        for cb in refresh_callbacks:
            cb()

    theme_combo.currentIndexChanged.connect(on_theme_changed)
    left.addWidget(theme_combo)
    left.addWidget(Label("切换上方主题可预览设计令牌在各组件上的效果。"))
    left.addStretch()
    right.addStretch()
    return page


def main():
    app = QApplication(sys.argv)
    theme_mgr = ThemeManager()
    theme_mgr.set_theme(app, ThemeId.LIGHT)
    set_theme_manager(theme_mgr)  # 供 Sidebar2 / ChamferButton 通过 app_context 获取，以随主题切换更新

    win = QWidget()
    win.setWindowTitle("设计系统组件 Demo")
    win.setMinimumWidth(1080)
    win.setMinimumHeight(720)

    menu_defs = [
        ("buttons", "按钮", "square_pen"),
        ("text", "文本输入", "scroll_text"),
        ("toggles", "开关选择", "check"),
        ("inputs", "数值滑块", "list_plus"),
        ("containers", "标签页分组", "layout_panel_left"),
        ("color_icons", "颜色图标", "copy"),
        ("theme", "主题", "refresh_cw"),
    ]
    sidebar = Sidebar2(menu_defs=menu_defs)
    stack = QStackedWidget()

    refresh_callbacks: list = []
    stack.addWidget(_build_page_buttons(theme_mgr))
    stack.addWidget(_build_page_text(theme_mgr))
    stack.addWidget(_build_page_toggles(theme_mgr))
    stack.addWidget(_build_page_inputs(theme_mgr))
    stack.addWidget(_build_page_containers(theme_mgr))
    stack.addWidget(_build_page_color_icons(theme_mgr, refresh_callbacks))
    stack.addWidget(_build_page_theme(theme_mgr, refresh_callbacks))

    menu_id_to_index = {mid: i for i, (mid, _, _) in enumerate(menu_defs)}

    def on_sidebar_clicked(menu_id: str):
        idx = menu_id_to_index.get(menu_id, 0)
        stack.setCurrentIndex(idx)

    sidebar.itemClicked.connect(on_sidebar_clicked)
    sidebar.select(menu_defs[0][0])

    main_layout = QHBoxLayout(win)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)
    main_layout.addWidget(sidebar)
    main_layout.addWidget(stack, 1)

    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
