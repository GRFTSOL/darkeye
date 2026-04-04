"""
Force-directed view settings panel: UI and signals/slots only.
Parent connects panel signals to view/session.
"""

import logging
import token
from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
    QFormLayout,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog
from PySide6.QtCore import Qt, Signal, QSize, QTimer

from darkeye_ui.components.clickable_slider import ClickableSlider
from darkeye_ui.components.label import Label
from darkeye_ui.components.toggle_switch import ToggleSwitch
from darkeye_ui.design.tokens import LIGHT_TOKENS, ThemeTokens
from darkeye_ui.components import TokenCollapsibleSection
from darkeye_ui.components.button import Button
from darkeye_ui.components.token_radio_button import TokenRadioButton
from darkeye_ui.components.token_check_box import TokenCheckBox

if TYPE_CHECKING:
    from darkeye_ui.design.theme_manager import ThemeManager


def _make_color_button(
    initial: QColor,
    group: str,
    parent: QWidget,
    on_changed,
    *,
    get_border_color=None,
) -> QPushButton:
    """创建颜色选择按钮，点击打开取色器。get_border_color() 返回边框色，可由主题令牌提供。"""
    if get_border_color is None:
        get_border_color = lambda: "#888"
    border_color = get_border_color()
    btn = QPushButton(parent)
    btn.setFixedSize(56, 24)
    btn._current_color = initial  # 供主题切换时保留背景色、仅更新边框
    btn._get_border_color = get_border_color
    btn.setStyleSheet(
        f"background-color: {initial.name()}; border: 1px solid {border_color}; border-radius: 3px;"
    )
    btn.setCursor(Qt.PointingHandCursor)

    def _pick():
        c = QColorDialog.getColor(
            btn._current_color, parent, "选择颜色", QColorDialog.ShowAlphaChannel
        )
        if c.isValid():
            btn._current_color = c
            bc = btn._get_border_color()
            btn.setStyleSheet(
                f"background-color: {c.name()}; border: 1px solid {bc}; border-radius: 3px;"
            )
            on_changed(group, c)

    btn.clicked.connect(_pick)
    return btn


class ForceViewSettingsPanel(QScrollArea):
    """Settings panel for force-directed view. Emits signals for parent to connect to view/session."""

    # --- Outgoing signals (parent connects to view/session) ---

    # Physics parameters
    fitInViewRequested = Signal()
    manyBodyStrengthChanged = Signal(float)
    centerStrengthChanged = Signal(float)
    linkStrengthChanged = Signal(float)
    linkDistanceChanged = Signal(float)

    # Display parameters
    radiusFactorChanged = Signal(float)
    textThresholdFactorChanged = Signal(float)
    linkWidthFactorChanged = Signal(float)
    neighborDepthChanged = Signal(int)
    arrowEnabledChanged = Signal(bool)
    arrowScaleChanged = Signal(float)
    imageOverlayEnabledChanged = Signal(bool)
    graphNeighborDepthChanged = Signal(int)
    nodeColorGroupChanged = Signal(
        str, "QColor"
    )  # group: "actress"|"work"|"center"|"default"

    # Simulation controls
    restartRequested = Signal()
    pauseRequested = Signal()
    resumeRequested = Signal()

    # Graph modification
    addNodeRequested = Signal()
    removeNodeRequested = Signal()
    addEdgeRequested = Signal()
    removeEdgeRequested = Signal()

    # Graph mode
    graphModeChanged = Signal(str)

    # Layout changes
    contentSizeChanged = Signal()

    def __init__(self, parent=None):
        """Initialize the settings panel with a solid background."""
        super().__init__(parent)
        self.setObjectName("my_panel")

        self._theme_manager: Optional["ThemeManager"] = None
        try:
            from controller.app_context import get_theme_manager

            self._theme_manager = get_theme_manager()
        except ImportError as e:
            logging.debug(
                "ForceViewSettingsPanel: 无法导入主题管理器: %s",
                e,
                exc_info=True,
            )

        self._sliders: list[ClickableSlider] = []
        self._color_buttons: list[QPushButton] = []

        self.setVisible(False)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._build_ui()
        self._connect_internal()

        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._apply_styles)
        self._apply_styles()

    def _build_ui(self):
        """Build the UI with effect, display, and test sections."""
        # 设置面板的大小策略：横向优先，纵向可扩展
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        # Status labels
        self.label_cal = Label()
        self.label_paint = Label()

        # --- Effect Section ---
        effect_section = TokenCollapsibleSection("效果", self._theme_manager, self)
        effect_form = QFormLayout()

        # Physics parameters
        self.many_body_strength = ClickableSlider(Qt.Horizontal)  # type: ignore[arg-type]
        self.many_body_strength.setMinimum(1000)
        self.many_body_strength.setMaximum(50000)
        self.many_body_strength.setValue(10000)
        self._sliders.append(self.many_body_strength)

        self.center_strength = ClickableSlider(Qt.Horizontal)  # type: ignore[arg-type]
        self.center_strength.setMinimum(1)  # Range 0.005-0.05
        self.center_strength.setMaximum(50)
        self.center_strength.setValue(10)
        self._sliders.append(self.center_strength)

        self.link_strength = ClickableSlider(Qt.Horizontal)  # type: ignore[arg-type]
        self.link_strength.setMinimum(1)  # Range 0.01-1
        self.link_strength.setMaximum(100)
        self.link_strength.setValue(30)
        self._sliders.append(self.link_strength)

        self.link_length = ClickableSlider(Qt.Horizontal)  # type: ignore[arg-type]
        self.link_length.setMinimum(10)
        self.link_length.setMaximum(80)
        self.link_length.setValue(40)
        self._sliders.append(self.link_length)

        effect_form.addRow(Label("斥力强度"), self.many_body_strength)
        effect_form.addRow(Label("中心力强度"), self.center_strength)
        effect_form.addRow(Label("连接力强度"), self.link_strength)
        effect_form.addRow(Label("连接距离"), self.link_length)

        # Graph type radio buttons
        self.radio_graph_all = TokenRadioButton("总图", self)
        self.radio_graph_favorite = TokenRadioButton("片关系图", self)
        self.radio_graph_test = TokenRadioButton("2000点图", self)
        self.radio_graph_all.setChecked(True)

        effect_section.add_layout(effect_form)

        # --- Display Section ---
        display_section = TokenCollapsibleSection("显示", self._theme_manager, self)
        display_form = QFormLayout()

        self.show_image = ToggleSwitch(width=48, height=24)
        self.show_image.setChecked(True)
        self.show_arrow = ToggleSwitch(width=48, height=24)
        self.show_arrow.setChecked(True)

        # Display parameters
        self.text_fade_threshold = ClickableSlider(Qt.Horizontal)  # type: ignore[arg-type]
        self.text_fade_threshold.setMinimum(10)
        self.text_fade_threshold.setMaximum(1000)
        self.text_fade_threshold.setValue(100)
        self._sliders.append(self.text_fade_threshold)

        self.node_size = ClickableSlider(Qt.Horizontal)  # type: ignore[arg-type]
        self.node_size.setMinimum(10)
        self.node_size.setMaximum(300)
        self.node_size.setValue(100)
        self._sliders.append(self.node_size)

        self.link_width = ClickableSlider(Qt.Horizontal)  # type: ignore[arg-type]
        self.link_width.setMinimum(10)
        self.link_width.setMaximum(300)
        self.link_width.setValue(60)
        self._sliders.append(self.link_width)

        self.neighbor_depth = ClickableSlider(Qt.Horizontal)  # type: ignore[arg-type]
        self.neighbor_depth.setMinimum(1)
        self.neighbor_depth.setMaximum(5)
        self.neighbor_depth.setValue(2)
        self._sliders.append(self.neighbor_depth)

        self.arrow_size = ClickableSlider(Qt.Horizontal)  # type: ignore[arg-type]
        self.arrow_size.setMinimum(3)
        self.arrow_size.setMaximum(30)
        self.arrow_size.setValue(10)
        self._sliders.append(self.arrow_size)

        self.graph_neighbor_depth = ClickableSlider(Qt.Horizontal)
        self.graph_neighbor_depth.setMinimum(1)  # 图邻居深度，专用过滤模式的邻居深度
        self.graph_neighbor_depth.setMaximum(5)
        self.graph_neighbor_depth.setValue(3)
        self._sliders.append(self.graph_neighbor_depth)

        self.show_coordinate_sys = TokenCheckBox("显示坐标轴", self)
        self.show_coordinate_sys.setChecked(False)

        display_form.addRow(Label("显示箭头"), self.show_arrow)
        display_form.addRow(Label("箭头大小"), self.arrow_size)
        display_form.addRow(Label("显示图片"), self.show_image)
        display_form.addRow(Label("文字渐隐"), self.text_fade_threshold)
        display_form.addRow(Label("节点大小"), self.node_size)
        display_form.addRow(Label("连线宽度"), self.link_width)
        display_form.addRow(Label("邻居深度"), self.neighbor_depth)
        display_form.addRow(Label("图邻居深度"), self.graph_neighbor_depth)

        # 节点颜色（按类型覆盖，初始颜色固定，边框接入主题令牌）
        color_emit = lambda g, c: self.nodeColorGroupChanged.emit(g, c)
        get_border = lambda: self._tokens().color_border
        self.color_actress = _make_color_button(
            QColor("#ff99cc"), "actress", self, color_emit, get_border_color=get_border
        )
        self.color_work = _make_color_button(
            QColor("#99ccff"), "work", self, color_emit, get_border_color=get_border
        )
        self.color_center = _make_color_button(
            QColor("#FFD700"), "center", self, color_emit, get_border_color=get_border
        )
        self.color_default = _make_color_button(
            QColor("#5C5C5C"), "default", self, color_emit, get_border_color=get_border
        )
        self._color_buttons.extend(
            [self.color_actress, self.color_work, self.color_center, self.color_default]
        )
        color_column = QVBoxLayout()
        color_column.setContentsMargins(0, 0, 0, 0)
        color_column.setSpacing(6)
        for text, btn in (
            ("女优", self.color_actress),
            ("作品", self.color_work),
            ("中心", self.color_center),
            ("默认", self.color_default),
        ):
            pair = QHBoxLayout()
            pair.setContentsMargins(0, 0, 0, 0)
            pair.addWidget(Label(text))
            pair.addWidget(btn)
            pair.addStretch()
            color_column.addLayout(pair)
        display_form.addRow(Label("节点颜色"), color_column)

        display_section.add_layout(display_form)

        # --- Test Section ---
        test_section = TokenCollapsibleSection("测试", self._theme_manager, self)

        # Status labels
        self.label_scale = Label()
        self.label_fps = Label()
        self.label_alpha = Label()
        graph_type_layout = QHBoxLayout()
        graph_type_layout.addWidget(self.radio_graph_all)
        graph_type_layout.addWidget(self.radio_graph_favorite)
        graph_type_layout.addWidget(self.radio_graph_test)

        # Control buttons
        self.btn_fitinview = Button("适配视图", self)
        self.btn_restart = Button("Restart", self)
        self.btn_pause = Button("Pause", self)
        self.btn_resume = Button("Resume", self)
        self.btn_add_node = Button("加点", self)
        self.btn_remove_node = Button("减点", self)
        self.btn_add_edge = Button("加边", self)
        self.btn_remove_edge = Button("减边", self)

        test_section.add_widget(self.btn_fitinview)
        test_section.add_widget(self.btn_restart)
        test_section.add_widget(self.btn_pause)
        test_section.add_widget(self.btn_resume)
        test_section.add_widget(self.show_coordinate_sys)
        test_section.add_widget(self.btn_add_node)
        test_section.add_widget(self.btn_remove_node)
        test_section.add_widget(self.btn_add_edge)
        test_section.add_widget(self.btn_remove_edge)

        form_layout = QFormLayout()
        form_layout.addRow(Label("图类型"), graph_type_layout)
        form_layout.addRow(Label("tick消耗"), self.label_cal)
        form_layout.addRow(Label("paint消耗"), self.label_paint)
        form_layout.addRow(Label("当前缩放"), self.label_scale)
        form_layout.addRow(Label("当前帧率"), self.label_fps)
        form_layout.addRow(Label("当前模拟热度"), self.label_alpha)
        test_section.add_layout(form_layout)

        # Create content container
        scroll_content = QWidget()
        # 设置内容区域的大小策略：横向固定，纵向可扩展
        scroll_content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)

        # 设置各个区域的大小策略，防止横向扩展
        effect_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        display_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        test_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        # Add three sections to scroll layout
        scroll_layout.addWidget(effect_section)
        scroll_layout.addWidget(display_section)
        scroll_layout.addWidget(test_section)
        scroll_layout.addStretch()

        # Set scroll area content
        self.setWidget(scroll_content)

        # Store references for later use
        self._effect_section = effect_section
        self._display_section = display_section
        self._test_section = test_section
        self._max_panel_height = None  # Initialize max height
        self._cached_content_height = 0  # 内容所需高度，供 sizeHint 使用
        self._scroll_content = scroll_content  # 保存引用用于后续调整宽度

    def resizeEvent(self, event):
        """重写 resizeEvent 来同步内容宽度并更新内容高度缓存"""
        super().resizeEvent(event)
        self._update_content_width()
        self._adjust_panel_height()

    def _update_content_width(self):
        """更新内容区域的宽度以匹配视口"""
        if (
            hasattr(self, "_scroll_content")
            and self._scroll_content
            and self.viewport().width() > 0
        ):
            # 只根据视口宽度锁定内容宽度，避免被滚动条遮挡或裁剪
            content_width = self.viewport().width()
            self._scroll_content.setFixedWidth(content_width)
            # 高度交给布局和 sizeHint 控制，避免因为固定高度导致底部空白和提前出现滚动条
            self._scroll_content.setMinimumHeight(0)
            # 强制更新布局
            if self._scroll_content.layout():
                self._scroll_content.layout().activate()

    def showEvent(self, event):
        """重写 showEvent 来确保内容宽度正确"""
        super().showEvent(event)
        # 延迟调用以确保布局完成
        QTimer.singleShot(0, self._update_content_width)

    def _connect_internal(self):
        """Connect all internal controls to their corresponding signals."""
        # View controls
        self.btn_fitinview.clicked.connect(self.fitInViewRequested.emit)

        self.show_arrow.toggled.connect(self.arrowEnabledChanged.emit)
        self.show_image.toggled.connect(self.imageOverlayEnabledChanged.emit)
        self.arrow_size.valueChanged.connect(
            lambda x: self.arrowScaleChanged.emit(float(x) / 10.0)
        )
        self.graph_neighbor_depth.valueChanged.connect(
            self.graphNeighborDepthChanged.emit
        )

        # Physics parameters
        self.many_body_strength.valueChanged.connect(self.manyBodyStrengthChanged.emit)
        self.center_strength.valueChanged.connect(
            lambda x: self.centerStrengthChanged.emit(float(x) / 1000.0)
        )
        self.link_strength.valueChanged.connect(
            lambda x: self.linkStrengthChanged.emit(float(x) / 100.0)
        )
        self.link_length.valueChanged.connect(self.linkDistanceChanged.emit)

        # Display parameters
        self.neighbor_depth.valueChanged.connect(self.neighborDepthChanged.emit)
        self.node_size.valueChanged.connect(
            lambda x: self.radiusFactorChanged.emit(float(x) / 100.0)
        )
        self.text_fade_threshold.valueChanged.connect(
            lambda x: self.textThresholdFactorChanged.emit(float(x) / 100.0)
        )
        self.link_width.valueChanged.connect(
            lambda x: self.linkWidthFactorChanged.emit(float(x) / 100.0)
        )

        # Simulation controls
        self.btn_restart.clicked.connect(self.restartRequested.emit)
        self.btn_pause.clicked.connect(self.pauseRequested.emit)
        self.btn_resume.clicked.connect(self.resumeRequested.emit)

        # Graph modification
        self.btn_add_node.clicked.connect(self.addNodeRequested.emit)
        self.btn_remove_node.clicked.connect(self.removeNodeRequested.emit)
        self.btn_add_edge.clicked.connect(self.addEdgeRequested.emit)
        self.btn_remove_edge.clicked.connect(self.removeEdgeRequested.emit)

        # Graph mode selection
        self.radio_graph_all.toggled.connect(
            lambda checked: self.graphModeChanged.emit("all") if checked else None
        )
        self.radio_graph_favorite.toggled.connect(
            lambda checked: self.graphModeChanged.emit("favorite") if checked else None
        )
        self.radio_graph_test.toggled.connect(
            lambda checked: self.graphModeChanged.emit("test") if checked else None
        )

        # Section toggle：延后一帧再读 sizeHint 并通知父级。
        # 同步读经常早于布局提交，第二次展开时累计高度误差更明显，会闪一帧。
        def on_section_toggled():
            def _defer_sync():
                content_widget = self.widget()
                if content_widget:
                    content_widget.updateGeometry()
                    lay = content_widget.layout()
                    if lay is not None:
                        lay.activate()
                self._adjust_panel_height()
                self.contentSizeChanged.emit()

            QTimer.singleShot(0, _defer_sync)

        self._effect_section.toggled.connect(lambda _: on_section_toggled())
        self._display_section.toggled.connect(lambda _: on_section_toggled())
        self._test_section.toggled.connect(lambda _: on_section_toggled())

    def _tokens(self) -> ThemeTokens:
        """当前主题令牌，无 ThemeManager 时回退到 LIGHT_TOKENS。"""
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _apply_styles(self) -> None:
        """根据主题令牌更新面板、滑块和颜色按钮的样式。"""
        t = self._tokens()
        # 面板背景与边框
        bg = t.color_bg
        border = t.color_border
        radius = t.radius_md
        self.setStyleSheet(
            f"#my_panel {{"
            f"    background-color: {bg}; "
            f"    border: 1px solid {border}; "
            f"    border-radius: {radius};"
            f"}}"
            f"TokenCollapsibleSection {{"
            f"    background-color: {bg};"
            f"}}"
            f"TokenCollapsibleSection QWidget {{"
            f"    background-color: {bg};"
            f"}}"
        )
        # 滑块样式
        for s in self._sliders:
            s.set_style_from_tokens(t)
        # 颜色按钮边框（节点颜色 257-260 不改，仅更新边框）
        for btn in self._color_buttons:
            c = getattr(btn, "_current_color", None)
            if c is not None:
                btn.setStyleSheet(
                    f"background-color: {c.name()}; border: 1px solid {t.color_border}; border-radius: 3px;"
                )

    # --- Slots for parent to push view state into labels ---

    def set_fps(self, value: float):
        """Update FPS display."""
        self.label_fps.setText(f"{value:.2f}")

    def set_tick_time(self, ms: float):
        """Update tick time display."""
        self.label_cal.setText(f"{ms:.3f}ms")

    def set_paint_time(self, ms: float):
        """Update paint time display."""
        self.label_paint.setText(f"{ms:.3f}ms")

    def set_scale(self, value: float):
        """Update scale display."""
        self.label_scale.setText(f"{value:.2f}")

    def set_alpha(self, value: float):
        """Update simulation alpha display."""
        self.label_alpha.setText(f"{value:.2f}")

    def set_maximum_panel_height(self, max_height: int):
        """设置面板的最大高度"""
        self._max_panel_height = max_height
        # 更新内容宽度
        self._update_content_width()
        # 调整面板高度
        self._adjust_panel_height()

    def _adjust_panel_height(self):
        """根据内容和最大高度更新布局与 sizeHint，不在此处 resize；由父组件统一负责面板尺寸。"""
        # 首先更新内容宽度
        self._update_content_width()

        content_widget = self.widget()
        if content_widget:
            # 强制更新布局几何，使 sizeHint() 在下一帧前就绪
            content_widget.updateGeometry()
            content_widget.layout().activate()
            h = content_widget.sizeHint().height()
            if h > 0:
                self._cached_content_height = h
                self.updateGeometry()

    def _panel_height_chrome(self):
        """面板自身占用的垂直空间（布局边距 + 少量余量），以便 sizeHint 包含后父组件分配的高度能容纳完整内容。"""
        layout = self.layout()
        extra = 0
        if layout:
            m = layout.contentsMargins()
            extra = m.top() + m.bottom()
        # 少量余量，避免 QScrollArea 边框/取整导致仍出现滚动条
        return extra + 4

    def sizeHint(self):
        """返回面板理想尺寸，高度为完整内容所需高度 + 面板边距，供父组件计算“空间够则展开”。"""
        w = self.width() if self.width() > 0 else 250
        content_h = (
            self._cached_content_height
            if getattr(self, "_cached_content_height", 0) > 0
            else 400
        )
        # 加上面板布局的上下边距，避免父组件按此高度分配后，内部视口仍小于内容而出现滚动条
        h = content_h + self._panel_height_chrome()
        return QSize(w, h)

    def minimumSizeHint(self):
        """与 sizeHint 一致，避免面板被压得比内容还小。"""
        return self.sizeHint()
