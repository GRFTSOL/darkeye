from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QButtonGroup,
                             QHBoxLayout, QPushButton, QScrollArea, QFrame, QLabel)
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Qt

class ModernScrollMenu(QMainWindow):
    def __init__(self, content_dict):
        super().__init__()
        self.resize(700, 800)
        self.setStyleSheet("background-color: #FFFFFF;")
        
        # 【新增】：用于存储 标题 -> 按钮 的映射，方便反向查找
        self.nav_buttons = {} 
        # 【新增】：用于存储 内容区块 -> 对应按钮 的映射，用于滚动判断
        self.section_widgets = []

        # 主布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 1. 顶部导航栏 ---
        self.nav_container = QWidget()
        self.btn_layout = QHBoxLayout(self.nav_container)
        self.btn_layout.setContentsMargins(20, 10, 20, 0)
        
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True) 
        self.nav_container.setStyleSheet("""
            QPushButton {
                border: none; background-color: transparent; color: #888888;
                padding: 10px 15px; font-size: 15px; border-bottom: 2px solid transparent; 
                border-radius:0px;
            }
            QPushButton:hover { color: #444444; }
            QPushButton:checked { color: #000000; font-weight: bold; border-bottom: 2px solid #000000; }
        """)
        main_layout.addWidget(self.nav_container)

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
            title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;qproperty-alignment: 'AlignLeft | AlignTop';")
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
        line.setStyleSheet("background-color: #F5F5F5; min-height: 1px; max-height: 1px; margin: 10px 0px;")
        return line

    def scroll_to_widget(self, widget, btn):
        """点击按钮跳转"""
        self.is_animating = True # 标记动画开始，暂时停止滚动监听
        bar = self.scroll.verticalScrollBar()
        target_y = widget.pos().y()
        
        self.anim = QPropertyAnimation(bar, b"value")
        self.anim.setDuration(400)
        self.anim.setEndValue(target_y)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        
        # 动画结束后恢复监听
        self.anim.finished.connect(lambda: self.set_animating_false())
        self.anim.start()

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