"""翻译相关设置页面。"""

import asyncio
import logging

from PySide6.QtCore import Slot, QThreadPool
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QWidget

from config import (
    get_translation_api_key,
    get_translation_base_url,
    get_translation_engine,
    get_translation_fallback,
    get_translation_model,
    get_translation_retries,
    get_translation_timeout_s,
    set_translation_api_key,
    set_translation_base_url,
    set_translation_engine,
    set_translation_fallback,
    set_translation_model,
    set_translation_retries,
    set_translation_timeout_s,
)
from controller.message_service import MessageBoxService
from core.crawler.worker import Worker, wire_worker_finished
from core.translation.base import TranslationEngineConfig, TranslationRuntimeConfig
from core.translation.google_engine import GoogleTranslatorEngine
from core.translation.llm_engine import LlmTranslatorEngine
from darkeye_ui.components import Button, ComboBox, Label, TokenSpinBox
from darkeye_ui.components.input import LineEdit, PlainTextEdit


class TranslationSettingPage(QWidget):
    def __init__(self):
        super().__init__()
        self.msg = MessageBoxService(self)
        self._loading_settings = False
        self._build_ui()
        self._load_settings()
        self._install_auto_save()
        self._refresh_llm_fields_enabled()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)

        self.engine_combo = ComboBox(self)
        self.engine_combo.addItem("Google", "google")
        self.engine_combo.addItem("LLM(OpenAI兼容)", "llm")
        self.engine_combo.currentIndexChanged.connect(self._refresh_llm_fields_enabled)

        self.model_edit = LineEdit(self)
        self.model_edit.setPlaceholderText("例如: deepseek-chat / gpt-4.1-mini")
        self.base_url_edit = LineEdit(self)
        self.base_url_edit.setPlaceholderText("例如: https://api.openai.com/v1")
        self.api_key_edit = LineEdit(self)
        self.api_key_edit.setPlaceholderText("输入 API Key")

        self.timeout_spin = TokenSpinBox(self)
        self.timeout_spin.setRange(1, 120)
        self.timeout_spin.setSingleStep(1)

        self.retries_spin = TokenSpinBox(self)
        self.retries_spin.setRange(0, 10)

        self.fallback_combo = ComboBox(self)
        self.fallback_combo.addItem("失败返回空字符串", "empty")
        self.fallback_combo.addItem("失败返回原文", "source")

        self.preview_input = PlainTextEdit(self)
        self.preview_input.setPlaceholderText("输入要测试翻译的文本（日文）")
        self.preview_input.setFixedHeight(96)
        self.preview_output = PlainTextEdit(self)
        self.preview_output.setReadOnly(True)
        self.preview_output.setFixedHeight(96)

        self.btn_test = Button("测试翻译")
        self.btn_test.clicked.connect(self._on_test_clicked)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_test)

        layout.addRow(Label("翻译引擎"), self.engine_combo)
        layout.addRow(Label("模型"), self.model_edit)
        layout.addRow(Label("Base URL"), self.base_url_edit)
        layout.addRow(Label("API Key"), self.api_key_edit)
        layout.addRow(Label("超时(秒)"), self.timeout_spin)
        layout.addRow(Label("重试次数"), self.retries_spin)
        layout.addRow(Label("失败回退"), self.fallback_combo)
        layout.addRow(Label("测试输入"), self.preview_input)
        layout.addRow(Label("测试输出"), self.preview_output)
        layout.addRow(btn_row)

    def _load_settings(self) -> None:
        self._loading_settings = True
        self._set_combo_by_data(self.engine_combo, get_translation_engine())
        self.model_edit.setText(get_translation_model())
        self.base_url_edit.setText(get_translation_base_url())
        self.api_key_edit.setText(get_translation_api_key())
        self.timeout_spin.setValue(get_translation_timeout_s())
        self.retries_spin.setValue(get_translation_retries())
        self._set_combo_by_data(self.fallback_combo, get_translation_fallback())
        self._loading_settings = False

    def _install_auto_save(self) -> None:
        self.engine_combo.currentIndexChanged.connect(self._on_setting_changed)
        self.model_edit.editingFinished.connect(self._on_setting_changed)
        self.base_url_edit.editingFinished.connect(self._on_setting_changed)
        self.api_key_edit.editingFinished.connect(self._on_setting_changed)
        self.timeout_spin.valueChanged.connect(self._on_setting_changed)
        self.retries_spin.valueChanged.connect(self._on_setting_changed)
        self.fallback_combo.currentIndexChanged.connect(self._on_setting_changed)

    @staticmethod
    def _set_combo_by_data(combo: ComboBox, value: str) -> None:
        for i in range(combo.count()):
            if (combo.itemData(i) or "").strip().lower() == value.strip().lower():
                combo.setCurrentIndex(i)
                return

    @Slot()
    def _refresh_llm_fields_enabled(self) -> None:
        is_llm = self._current_engine() == "llm"
        self.model_edit.setEnabled(is_llm)
        self.base_url_edit.setEnabled(is_llm)
        self.api_key_edit.setEnabled(is_llm)

    @Slot()
    def _on_setting_changed(self, *_args) -> None:
        if self._loading_settings:
            return
        self._persist_settings(show_message=False)

    def _current_engine(self) -> str:
        return (self.engine_combo.currentData() or "google").strip().lower()

    def _current_runtime(self) -> TranslationRuntimeConfig:
        fallback = (self.fallback_combo.currentData() or "empty").strip().lower()
        return TranslationRuntimeConfig(
            timeout_s=float(self.timeout_spin.value()),
            retries=int(self.retries_spin.value()),
            fallback=fallback if fallback in {"empty", "source"} else "empty",
        )

    def _persist_settings(self, show_message: bool) -> None:
        set_translation_engine(self._current_engine())
        set_translation_model(self.model_edit.text())
        set_translation_base_url(self.base_url_edit.text())
        set_translation_api_key(self.api_key_edit.text())
        set_translation_timeout_s(float(self.timeout_spin.value()))
        set_translation_retries(int(self.retries_spin.value()))
        set_translation_fallback(self.fallback_combo.currentData() or "empty")
        logging.info(
            "翻译设置已保存 engine=%s model=%s base_url_set=%s api_key_set=%s",
            self._current_engine(),
            (self.model_edit.text() or "").strip(),
            bool((self.base_url_edit.text() or "").strip()),
            bool((self.api_key_edit.text() or "").strip()),
        )
        if show_message:
            self.msg.show_info("完成", "翻译配置已保存")

    @Slot()
    def _on_test_clicked(self) -> None:
        text = (self.preview_input.toPlainText() or "").strip()
        if not text:
            self.msg.show_info("提示", "请先输入测试文本")
            return
        # 让“测试翻译”和业务翻译读取同一份配置，避免测试通过但业务按钮失败
        self._persist_settings(show_message=False)
        worker = Worker(lambda: self._run_test_translate(text))
        wire_worker_finished(worker, self._on_test_finished)
        QThreadPool.globalInstance().start(worker)

    def _run_test_translate(self, text: str) -> str:
        runtime = self._current_runtime()
        engine_name = self._current_engine()
        if engine_name == "llm":
            cfg = TranslationEngineConfig(
                engine="llm",
                model=(self.model_edit.text() or "").strip(),
                base_url=(self.base_url_edit.text() or "").strip(),
                api_key=(self.api_key_edit.text() or "").strip(),
            )
            engine = LlmTranslatorEngine(cfg)
        else:
            engine = GoogleTranslatorEngine()
        return asyncio.run(engine.translate(text, "zh-CN", runtime))

    @Slot(object)
    def _on_test_finished(self, result: object) -> None:
        out = (result or "").strip() if isinstance(result, str) else ""
        if out:
            self.preview_output.setPlainText(out)
            return
        self.preview_output.setPlainText("")
        self.msg.show_warning("翻译失败", "请检查网络、模型配置或 API Key 后重试。")
