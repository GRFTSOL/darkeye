"""常规设置页面：主题、主色、绿色模式等。"""

import logging

from PySide6.QtWidgets import QHBoxLayout, QFormLayout, QWidget
from PySide6.QtGui import QColor
from darkeye_ui.components import Label, Button, ComboBox, ColorPicker, ToggleSwitch
from darkeye_ui.design import ThemeId
from config import get_theme_id, set_theme_id, get_custom_primary, set_custom_primary
from app_context import get_theme_manager
from main import apply_theme
from controller.GlobalSignalBus import global_signals

# 主题下拉选项与 ThemeId 顺序一致
THEME_OPTIONS = [
    (ThemeId.LIGHT, "亮色主题"),
    (ThemeId.DARK, "暗色主题"),
    (ThemeId.RED, "红色"),
    (ThemeId.YELLOW, "黄色"),
    (ThemeId.GREEN, "绿色"),
    (ThemeId.BLUE, "蓝色"),
    (ThemeId.PURPLE, "紫色"),
]


class CommonPage(QWidget):
    def __init__(self):
        super().__init__()
        main_layout = QFormLayout(self)
        self.theme_choose = ComboBox()
        for _, label in THEME_OPTIONS:
            self.theme_choose.addItem(label)
        saved_theme = get_theme_id()
        try:
            idx = next(
                i for i, (tid, _) in enumerate(THEME_OPTIONS) if tid.name == saved_theme
            )
            self.theme_choose.setCurrentIndex(idx)
        except StopIteration:
            theme_mgr = get_theme_manager()
            if theme_mgr is not None:
                try:
                    idx = next(
                        i
                        for i, (tid, _) in enumerate(THEME_OPTIONS)
                        if tid == theme_mgr.current()
                    )
                    self.theme_choose.setCurrentIndex(idx)
                except StopIteration:
                    logging.debug(
                        "常规设置: theme_mgr.current() 未匹配 THEME_OPTIONS，保持下拉默认选中项"
                    )
        self.theme_choose.currentIndexChanged.connect(self._on_theme_changed)

        # 主色选择器（置于主题行上方，仅亮色/暗色主题可调）
        theme_mgr = get_theme_manager()
        self.primary_color_row = QWidget()
        primary_color_layout = QHBoxLayout(self.primary_color_row)
        primary_color_layout.setContentsMargins(0, 0, 0, 0)
        initial_primary = (
            get_custom_primary()
            or (theme_mgr.custom_primary() if theme_mgr else None)
            or (theme_mgr.tokens().color_primary if theme_mgr else "#2563eb")
        )
        self.color_picker = ColorPicker(
            QColor(initial_primary), shape=ColorPicker.ShapeCircle
        )
        primary_color_layout.addWidget(self.color_picker)

        self.color_picker.colorConfirmed.connect(self._on_primary_color_changed)
        self._update_primary_picker_state()
        self.greenmode = ToggleSwitch()

        main_layout.addRow(Label("主色"), self.primary_color_row)
        main_layout.addRow(Label("主题"), self.theme_choose)
        main_layout.addRow(Label("绿色模式"), self.greenmode)
        self.greenmode.toggled.connect(global_signals.greenModeChanged.emit)

    def _update_primary_picker_state(self):
        theme_mgr = get_theme_manager()
        tid = theme_mgr.current() if theme_mgr else ThemeId.LIGHT
        is_light_or_dark = tid in (ThemeId.LIGHT, ThemeId.DARK)
        self.primary_color_row.setEnabled(is_light_or_dark)
        if not is_light_or_dark:
            if theme_mgr:
                theme_mgr.set_custom_primary(None)
            set_custom_primary(None)
        else:
            self.color_picker.blockSignals(True)
            self.color_picker.set_color(
                get_custom_primary()
                or (theme_mgr.custom_primary() if theme_mgr else None)
                or (theme_mgr.tokens().color_primary if theme_mgr else "#2563eb")
            )
            self.color_picker.blockSignals(False)

    def _on_primary_color_changed(self, hex_color: str):
        theme_mgr = get_theme_manager()
        if theme_mgr:
            theme_mgr.set_custom_primary(hex_color)
        set_custom_primary(hex_color)
        apply_theme(theme_mgr.current() if theme_mgr else ThemeId.LIGHT)

    def _on_theme_changed(self, index: int):
        if 0 <= index < len(THEME_OPTIONS):
            theme_id = THEME_OPTIONS[index][0]
            theme_mgr = get_theme_manager()
            if theme_id not in (ThemeId.LIGHT, ThemeId.DARK):
                if theme_mgr:
                    theme_mgr.set_custom_primary(None)
                set_custom_primary(None)
            else:
                saved = get_custom_primary()
                if theme_mgr and saved:
                    theme_mgr.set_custom_primary(saved)
            set_theme_id(theme_id)
            apply_theme(theme_id)
            self._update_primary_picker_state()
