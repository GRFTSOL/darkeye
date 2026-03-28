"""快捷键设置页面。"""

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget
from PySide6.QtGui import QKeySequence
from darkeye_ui.components import Label, Button
from darkeye_ui.components.token_key_sequence_edit import TokenKeySequenceEdit
from controller.ShortcutRegistry import ShortcutRegistry


class ShortcutSettingRow(QWidget):
    def __init__(self, action_id, registry, action_obj, parent=None):
        super().__init__(parent)
        self.action_id = action_id
        self.registry = registry
        self.action_obj = action_obj

        layout = QHBoxLayout(self)

        name = self.registry.defaults[action_id]["name"]
        self.label = Label(name)
        self.label.setFixedWidth(100)

        current_key = self.registry.get_shortcut(action_id)
        self.key_edit = TokenKeySequenceEdit()
        self.key_edit.setFixedWidth(150)
        self.key_edit.setKeySequence(QKeySequence(current_key))

        self.reset_btn = Button("恢复")
        self.reset_btn.setFixedWidth(50)
        self.reset_btn.clicked.connect(self.reset_default)

        layout.addWidget(self.label)
        layout.addWidget(self.key_edit)
        layout.addWidget(self.reset_btn)
        layout.addStretch()

        self.key_edit.editingFinished.connect(self.apply_change)

    def apply_change(self):
        new_key_str = self.key_edit.keySequence().toString()
        self.registry.update_shortcut(self.action_id, new_key_str)
        self.action_obj.setShortcut(QKeySequence(new_key_str))

    def reset_default(self):
        self.registry.reset_to_default(self.action_id)
        default_key = self.registry.get_shortcut(self.action_id)
        self.key_edit.setKeySequence(QKeySequence(default_key))
        self.action_obj.setShortcut(QKeySequence(default_key))


class ShortCutSettingPage(QWidget):
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout(self)
        self.registry = ShortcutRegistry()

        for action_id in self.registry.defaults.keys():
            action_obj = self.registry.actions_map[action_id]
            row = ShortcutSettingRow(action_id, self.registry, action_obj)
            main_layout.addWidget(row)

        main_layout.addStretch()
        main_layout.addWidget(
            Label("<small>配置将自动保存到 data/shortcuts_config.json</small>")
        )
