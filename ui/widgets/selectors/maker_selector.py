from __future__ import annotations

from PySide6.QtCore import Qt, QStringListModel, Slot
from PySide6.QtWidgets import QCompleter, QSizePolicy

from darkeye_ui.components.combo_box import ComboBox


class MakerSelector(ComboBox):
    """片商选择器：支持 cn/jp/aliases 多字段过滤，显示主名。"""

    def __init__(self, makers: list[dict] | None = None, parent=None):
        super().__init__(parent)
        self._maker_records: list[dict] = []
        self._selected_maker_id: int | None = None

        self.setEditable(True)
        self.setInsertPolicy(ComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(15)
        # 避免按超长片商名扩张控件宽度
        self.setSizeAdjustPolicy(
            ComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.setMinimumContentsLength(8)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.lineEdit().setFrame(False)

        self._completion_model = QStringListModel([], self)
        self._completer = QCompleter(self._completion_model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        # 过滤由 _on_text_edited 手动完成，这里用 Unfiltered 避免再次按主名文本过滤。
        self._completer.setCompletionMode(
            QCompleter.CompletionMode.UnfilteredPopupCompletion
        )
        # 复用 ComboBox 下拉列表的设计系统样式，保证输入联想弹层与下拉弹层视觉一致。
        self._completer.popup().setObjectName("DesignComboBoxPopup")
        self.setCompleter(self._completer)

        self.lineEdit().textEdited.connect(self._on_text_edited)
        self.currentTextChanged.connect(self._sync_selected_from_text)
        self._completer.activated[str].connect(self._sync_selected_from_text)

        if makers:
            self.set_makers(makers)

    def set_makers(self, makers: list[dict]) -> None:
        """设置片商候选，maker 结构需包含 maker_id/cn_name/jp_name/aliases。"""
        normalized: list[dict] = [
            {
                "maker_id": None,
                "display_name": "",
                "search_text": "",
            }
        ]
        for maker in makers:
            cn_name = str(maker.get("cn_name") or "").strip()
            jp_name = str(maker.get("jp_name") or "").strip()
            aliases = str(maker.get("aliases") or "").strip()
            maker_id = maker.get("maker_id")
            if maker_id is not None:
                maker_id = int(maker_id)

            display_name = cn_name or jp_name
            if not display_name:
                continue

            alias_parts = [a.strip() for a in aliases.split(",") if a and a.strip()]
            search_parts = [cn_name, jp_name, *alias_parts]
            normalized.append(
                {
                    "maker_id": maker_id,
                    "display_name": display_name,
                    "search_text": " ".join([p for p in search_parts if p]).lower(),
                }
            )

        self._maker_records = normalized
        self.clear()
        for rec in self._maker_records:
            self.addItem(rec["display_name"], rec["maker_id"])
        self._completion_model.setStringList(
            [rec["display_name"] for rec in self._maker_records]
        )
        self.setCurrentIndex(0)
        self._selected_maker_id = None

    def set_maker(self, maker_id: int | None) -> None:
        """按 maker_id 设置当前片商；None 表示清空。"""
        if maker_id is None:
            self.setEditText("")
            self._selected_maker_id = None
            return

        target_record = None
        for rec in self._maker_records:
            if rec["maker_id"] == int(maker_id):
                target_record = rec
                break

        if target_record is None:
            self.setEditText("")
            self._selected_maker_id = None
            return

        self.setEditText(target_record["display_name"])
        self._selected_maker_id = target_record["maker_id"]

    def get_maker(self) -> int | None:
        """获取当前片商的 maker_id（未命中返回 None）。"""
        return self._selected_maker_id

    @Slot()
    def reload_makers(self) -> None:
        """从数据库重新加载片商列表，并尽量保留当前选择。"""
        from core.database.query import get_maker_name

        current_maker_id = self.get_maker()
        current_text = self.currentText()

        self.set_makers(get_maker_name())

        if current_maker_id:
            self.set_maker(current_maker_id)
        elif current_text:
            # 未命中 maker_id 时，尽量保留用户当前输入/显示文本
            self.setEditText(current_text)

    def _on_text_edited(self, text: str) -> None:
        keyword = (text or "").strip().lower()
        if not keyword:
            matched = [rec["display_name"] for rec in self._maker_records]
        else:
            matched = [
                rec["display_name"]
                for rec in self._maker_records
                if keyword in rec["search_text"]
            ]
        self._completion_model.setStringList(matched)
        if self.hasFocus():
            self._completer.setCompletionPrefix("")
            self._completer.complete()

    def _sync_selected_from_text(self, text: str) -> None:
        key = (text or "").strip()
        self._selected_maker_id = None
        for rec in self._maker_records:
            if rec["display_name"] == key:
                self._selected_maker_id = rec["maker_id"]
                break
