from __future__ import annotations

from PySide6.QtCore import Qt, QStringListModel, Slot
from PySide6.QtWidgets import QCompleter, QSizePolicy

from darkeye_ui.components.combo_box import ComboBox


class SeriesSelector(ComboBox):
    """系列选择器：支持 cn/jp/aliases 多字段过滤，显示主名。"""

    def __init__(self, series_list: list[dict] | None = None, parent=None):
        super().__init__(parent)
        self._series_records: list[dict] = []
        self._selected_series_id: int | None = None

        self.setEditable(True)
        self.setInsertPolicy(ComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(15)
        self.setSizeAdjustPolicy(
            ComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.setMinimumContentsLength(8)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.lineEdit().setFrame(False)

        self._completion_model = QStringListModel([], self)
        self._completer = QCompleter(self._completion_model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setCompletionMode(
            QCompleter.CompletionMode.UnfilteredPopupCompletion
        )
        self._completer.popup().setObjectName("DesignComboBoxPopup")
        self.setCompleter(self._completer)

        self.lineEdit().textEdited.connect(self._on_text_edited)
        self.currentTextChanged.connect(self._sync_selected_from_text)
        self._completer.activated[str].connect(self._sync_selected_from_text)

        if series_list:
            self.set_series(series_list)

    def set_series(self, series_list: list[dict]) -> None:
        """设置系列候选，series 结构需包含 series_id/cn_name/jp_name/aliases。"""
        normalized: list[dict] = [
            {
                "series_id": None,
                "display_name": "",
                "search_text": "",
            }
        ]
        for series in series_list:
            cn_name = str(series.get("cn_name") or "").strip()
            jp_name = str(series.get("jp_name") or "").strip()
            aliases = str(series.get("aliases") or "").strip()
            series_id = series.get("series_id")
            if series_id is not None:
                series_id = int(series_id)

            display_name = cn_name or jp_name
            if not display_name:
                continue

            alias_parts = [a.strip() for a in aliases.split(",") if a and a.strip()]
            search_parts = [cn_name, jp_name, *alias_parts]
            normalized.append(
                {
                    "series_id": series_id,
                    "display_name": display_name,
                    "search_text": " ".join([p for p in search_parts if p]).lower(),
                }
            )

        self._series_records = normalized
        self.clear()
        for rec in self._series_records:
            self.addItem(rec["display_name"], rec["series_id"])
        self._completion_model.setStringList(
            [rec["display_name"] for rec in self._series_records]
        )
        self.setCurrentIndex(0)
        self._selected_series_id = None

    def set_series_id(self, series_id: int | None) -> None:
        """按 series_id 设置当前系列；None 表示清空。"""
        if series_id is None:
            self.setEditText("")
            self._selected_series_id = None
            return

        target_record = None
        for rec in self._series_records:
            if rec["series_id"] == int(series_id):
                target_record = rec
                break

        if target_record is None:
            self.setEditText("")
            self._selected_series_id = None
            return

        self.setEditText(target_record["display_name"])
        self._selected_series_id = target_record["series_id"]

    def get_series_id(self) -> int | None:
        """获取当前系列的 series_id（未命中返回 None）。"""
        return self._selected_series_id

    @Slot()
    def reload_series(self) -> None:
        """从数据库重新加载系列列表，并尽量保留当前选择。"""
        from core.database.query import get_series_name

        current_series_id = self.get_series_id()
        current_text = self.currentText()

        self.set_series(get_series_name())

        if current_series_id:
            self.set_series_id(current_series_id)
        elif current_text:
            self.setEditText(current_text)

    def _on_text_edited(self, text: str) -> None:
        keyword = (text or "").strip().lower()
        if not keyword:
            matched = [rec["display_name"] for rec in self._series_records]
        else:
            matched = [
                rec["display_name"]
                for rec in self._series_records
                if keyword in rec["search_text"]
            ]
        self._completion_model.setStringList(matched)
        if self.hasFocus():
            self._completer.setCompletionPrefix("")
            self._completer.complete()

    def _sync_selected_from_text(self, text: str) -> None:
        key = (text or "").strip()
        self._selected_series_id = None
        for rec in self._series_records:
            if rec["display_name"] == key:
                self._selected_series_id = rec["series_id"]
                break
