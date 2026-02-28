from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QButtonGroup,
                             QHBoxLayout, QPushButton, QScrollArea, QFrame, QLabel)
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Qt

if TYPE_CHECKING:
    from darkeye_ui.design.theme_manager import ThemeManager

from darkeye_ui.design.tokens import LIGHT_TOKENS, ThemeTokens


class ModernScrollMenu(QWidget):
    def __init__(self, content_dict, theme_manager: Optional["ThemeManager"] = None):
        super().__init__()
        if theme_manager is None:
            try:
                from app_context import get_theme_manager
                theme_manager = get_theme_manager()
            except Exception:
                theme_manager = None
        self._theme_manager = theme_manager

        # 用于存储 标题 -> 按钮 的映射，方便反向查找
        self.nav_buttons = {}
        # 用于存储 内容区块 -> 对应按钮 的映射，用于滚动判断
        self.section_widgets = []
        # 用于主题切换时更新样式的子控件引用
        self._title_labels: list[QLabel] = []
        self._separators: list[QFrame] = []

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 1. 顶部导航栏 ---
        self.nav_container = QWidget()
        self.btn_layout = QHBoxLayout(self.nav_container)
        self.btn_layout.setContentsMargins(20, 10, 20, 0)

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        main_layout.addWidget(self.nav_container)

        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._apply_token_styles)

        # --- 2. 滚动区域 ---
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll_content = QWidget()
        self.content_layout = QVBoxLayout(self.scroll_content)
        self.content_layout.setContentsMargins(40, 20, 40, 20)
        self.scroll.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll)

        # --- 3. 构建内容 ---
        self.build_from_dict(content_dict)
        self._apply_token_styles()  # 构建内容后再应用一次，以样式化标题与分隔线
        self.btn_layout.addStretch()

        # 【核心新增】：连接滚动条信号
        self.scroll.verticalScrollBar().valueChanged.connect(self.on_scroll_update_nav)
        
        # 标记位：防止点击跳转时的动画与滚动监听冲突
        self.is_animating = False

    def build_from_dict(self, content_dict):
        for i, (title_text, widget_instance) in enumerate(content_dict.items()):
            btn = QPushButton(title_text)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            if i == 0: btn.setChecked(True)
            
            self.btn_group.addButton(btn)
            self.btn_layout.addWidget(btn)
            self.nav_buttons[title_text] = btn

            section_wrapper = QWidget()
            sec_layout = QHBoxLayout(section_wrapper)
            sec_layout.setContentsMargins(0, 10, 0, 10) # 压缩间距
            
            title_label = QLabel(title_text)
            title_label.setFixedWidth(100)
            self._title_labels.append(title_label)
            sec_layout.addWidget(title_label)
            sec_layout.addSpacing(100)
            sec_layout.addWidget(widget_instance)
            
            self.content_layout.addWidget(section_wrapper)
            
            # 【记录】：将包装容器和对应的按钮存入列表
            self.section_widgets.append((section_wrapper, btn))

            btn.clicked.connect(lambda chk, w=section_wrapper, b=btn: self.scroll_to_widget(w, b))

            if i < len(content_dict) - 1:
                self.content_layout.addWidget(self.create_separator())
        
        self.content_layout.addStretch(1)

    def create_separator(self):
        line = QFrame()
        self._separators.append(line)
        return line

    def _tokens(self) -> ThemeTokens:
        if self._theme_manager is not None:
            return self._theme_manager.tokens()
        return LIGHT_TOKENS

    def _apply_token_styles(self) -> None:
        """根据当前主题令牌应用样式。"""
        t = self._tokens()
        self.setStyleSheet(f"background-color: {t.color_bg};")

        self.nav_container.setStyleSheet(f"""
            QPushButton {{
                border: none; background-color: transparent; color: {t.color_text_placeholder};
                padding: 10px 15px; font-size: 15px; border-bottom: {t.border_width} solid transparent;
                border-radius: 0px;
            }}
            QPushButton:hover {{ color: {t.color_text}; }}
            QPushButton:checked {{ color: {t.color_primary}; font-weight: bold; border-bottom: {t.border_width} solid {t.color_primary}; }}
        """)

        for lbl in self._title_labels:
            lbl.setStyleSheet(
                f"font-size: 18px; font-weight: bold; color: {t.color_text}; "
                "qproperty-alignment: 'AlignLeft | AlignTop';"
            )

        for sep in self._separators:
            sep.setStyleSheet(
                f"background-color: {t.color_bg_page}; min-height: 1px; max-height: 1px; margin: 10px 0px;"
            )

    def set_animating_false(self):
        self.is_animating = False

    def on_scroll_update_nav(self, value):
        """核心逻辑：滚动时更新导航栏选中状态"""
        if self.is_animating:
            return

        # 增加一个偏移量（阈值），比如当区块距离顶部还有 50px 时就触发切换
        threshold = 50 
        
        current_active_btn = None
        
        for widget, btn in self.section_widgets:
            # 获取 widget 相对于滚动区域内容的位置
            # 如果 widget 的顶部已经滚过（或接近）视口顶部
            if widget.pos().y() <= value + threshold:
                current_active_btn = btn
            else:
                break # 因为是垂直布局，下方的肯定还没到，直接跳出循环
        
        if current_active_btn:
            # 阻止信号循环触发，只更新 UI 状态
            current_active_btn.blockSignals(True)
            current_active_btn.setChecked(True)
            current_active_btn.blockSignals(False)

    def scroll_to_widget(self, widget, btn):
        """点击按钮跳转"""
        self.is_animating = True
        bar = self.scroll.verticalScrollBar()
        # 偏移 2 像素避免边界判断问题
        target_y = widget.pos().y()
        
        self.anim = QPropertyAnimation(bar, b"value")
        self.anim.setDuration(500)
        self.anim.setEndValue(target_y)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.finished.connect(self.set_animating_false)
        self.anim.start()