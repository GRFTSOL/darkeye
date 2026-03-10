from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QIcon
from ui.basic import IconPushButton
from config import ICONS_PATH


class MenuButton(QWidget):
    clicked = Signal()
    def __init__(self, text, icon_name, expanded_width=240, collapsed_width=60):
        super().__init__()
        self.setFixedHeight(50)
        self.setFixedWidth(expanded_width)
        self.setAttribute(Qt.WA_StyledBackground)# type: ignore[arg-type]
        self._is_selected = False
        self.mainlayout = QHBoxLayout(self)
        self.mainlayout.setContentsMargins(0, 0, 0, 0)
        self.mainlayout.setSpacing(0)
        self.icon_label = IconPushButton(str(ICONS_PATH / icon_name), color="#8a8e99")
        self.icon_label.setFixedSize(collapsed_width, 50)
        self.text_label = QLabel(text)
        self.text_label.setStyleSheet("color: #8a8e99; font-size: 13px; border: none;")
        self.icon_label.setAttribute(Qt.WA_TransparentForMouseEvents)# type: ignore[arg-type]
        self.text_label.setAttribute(Qt.WA_TransparentForMouseEvents)# type: ignore[arg-type]
        self.mainlayout.addWidget(self.icon_label)
        self.mainlayout.addWidget(self.text_label)
        self.mainlayout.addStretch()
        self._update_style()

    def _update_style(self):
        if self._is_selected:
            style = """
                MenuButton {
                    background-color: #F7E6B0;
                    border-left: 3px solid #DBCA97;
                }
                MenuButton:hover {
                    background-color: #F7E6B0;
                }
                QLabel {
                    color: white;
                    font-size: 13px;
                    background: transparent;
                }
                MenuButton:hover QLabel {
                    color: white;
                }
            """
        else:
            style = """
                MenuButton {
                    background-color: transparent;
                    border-left: 3px solid transparent;
                }
                MenuButton:hover {
                    background-color: #F7E6B0;
                }
                QLabel {
                    color: #8a8e99;
                    font-size: 13px;
                    background: transparent;
                }
                MenuButton:hover QLabel {
                    color: white;
                }
            """
        self.setStyleSheet(style)

    def set_selected(self, selected: bool):
        if self._is_selected != selected:
            self._is_selected = selected
            self._update_style()

    def is_selected(self):
        return self._is_selected

    def mousePressEvent(self, event):
        self.clicked.emit()


class Sidebar(QWidget):
    itemClicked = Signal(str)
    selectedChanged = Signal(str)
    def __init__(self, menu_defs=None, parent=None):
        super().__init__(parent)
        self.expanded_width = 240
        self.collapsed_width = 60
        self.setMinimumWidth(self.collapsed_width)
        self.setMaximumWidth(self.collapsed_width)
        self._is_expanded = False
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.toggle_btn = self._create_menu_btn("隐藏菜单", "menu.svg")
        self.toggle_btn.clicked.connect(self.toggle_menu)
        self.main_layout.addWidget(self.toggle_btn)
        self.menu_container = QWidget()
        self.menu_layout = QVBoxLayout(self.menu_container)
        self.menu_layout.setContentsMargins(0, 0, 0, 0)
        self.menu_layout.setSpacing(0)
        
        if menu_defs is None:
            self.menu_defs = []
        else:
            self.menu_defs = menu_defs

        self.buttons = {}
        for mid, text, icon in self.menu_defs:
            btn = self._create_menu_btn(text, icon)
            btn.clicked.connect(lambda m=mid: self._on_menu_item_clicked(m))
            self.menu_layout.addWidget(btn)
            self.buttons[mid] = btn
            
        self.menu_layout.addStretch()
        self.main_layout.addWidget(self.menu_container)
        
        if self.menu_defs:
            self._current_id = self.menu_defs[0][0]
            if self._current_id in self.buttons:
                self.buttons[self._current_id].set_selected(True)
        else:
            self._current_id = None

        self.anim = QPropertyAnimation(self, b"minimumWidth")
        self.anim.setDuration(500)
        self.anim.setEasingCurve(QEasingCurve.InOutQuint)# type: ignore[arg-type]
        self.anim.valueChanged.connect(lambda v: self.setMaximumWidth(v))
        self.anim.setStartValue(self.collapsed_width)
        self.anim.setEndValue(self.expanded_width)

    def _create_menu_btn(self, text, icon_type):
        btn = MenuButton(text, icon_type, self.expanded_width, self.collapsed_width)
        return btn

    def _on_menu_item_clicked(self, menu_id: str):
        if self._current_id == menu_id:
            btn = self.buttons.get(menu_id)
            if btn:
                btn.set_selected(False)
            self._current_id = None
            self.selectedChanged.emit("")
        else:
            prev_btn = self.buttons.get(self._current_id)
            if prev_btn:
                prev_btn.set_selected(False)
            new_btn = self.buttons.get(menu_id)
            if new_btn:
                new_btn.set_selected(True)
            self._current_id = menu_id
            self.selectedChanged.emit(menu_id)
        self.itemClicked.emit(menu_id)

    def get_selected_id(self):
        return self._current_id

    def clear_selection(self):
        if self._current_id is None:
            return
        btn = self.buttons.get(self._current_id)
        if btn:
            btn.set_selected(False)
        self._current_id = None
        self.selectedChanged.emit("")

    def select(self, menu_id: str):
        if self._current_id != menu_id:
            prev_btn = self.buttons.get(self._current_id)
            if prev_btn:
                prev_btn.set_selected(False)
            new_btn = self.buttons.get(menu_id)
            if new_btn:
                new_btn.set_selected(True)
            self._current_id = menu_id
            self.selectedChanged.emit(menu_id)

    def toggle_menu(self):
        if self._is_expanded:
            self.anim.setDirection(QPropertyAnimation.Direction.Backward)
        else:
            self.anim.setDirection(QPropertyAnimation.Direction.Forward)
        self.anim.start()
        self._is_expanded = not self._is_expanded
