"""翻译相关设置页面。"""

import asyncio
import logging
import os
import subprocess

from PySide6.QtCore import QThreadPool, QUrl, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QFormLayout, QHBoxLayout, QWidget

from config import (
    get_llama_auto_sync_translation,
    get_llama_auto_start,
    get_llama_batch_size,
    get_llama_ctx_size,
    get_llama_gpu_layers,
    get_llama_host,
    get_llama_mlock,
    get_llama_mode,
    get_llama_model_path,
    get_llama_port,
    get_llama_server_exe_path,
    get_llama_threads,
    get_llama_threads_batch,
    get_llama_ubatch_size,
    get_translation_api_key,
    get_translation_base_url,
    get_translation_engine,
    get_translation_fallback,
    get_translation_model,
    get_translation_retries,
    get_translation_timeout_s,
    set_llama_auto_sync_translation,
    set_llama_auto_start,
    set_llama_batch_size,
    set_llama_ctx_size,
    set_llama_gpu_layers,
    set_llama_host,
    set_llama_mlock,
    set_llama_mode,
    set_llama_model_path,
    set_llama_port,
    set_llama_server_exe_path,
    set_llama_threads,
    set_llama_threads_batch,
    set_llama_ubatch_size,
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
from core.translation.llama_runtime import LlamaLaunchConfig, get_llama_runtime
from core.translation.base import TranslationEngineConfig, TranslationRuntimeConfig
from core.translation.google_engine import GoogleTranslatorEngine
from core.translation.llm_engine import LlmTranslatorEngine
from darkeye_ui.components import Button, ComboBox, Label, TokenSpinBox, ToggleSwitch
from darkeye_ui.components.input import LineEdit, PlainTextEdit

LLAMA_RELEASE_URL = "https://github.com/ggml-org/llama.cpp/releases"
LLAMA_MODEL_7B_URL = (
    "https://huggingface.co/SakuraLLM/Sakura-7B-Qwen2.5-v1.0-GGUF/tree/main"
)
LLAMA_MODEL_14B_URL = (
    "https://huggingface.co/SakuraLLM/Sakura-14B-Qwen3-v1.5-GGUF/tree/main"
)
LLAMA_TUTORIAL_URL = "https://de4321.github.io/darkeye/usage/#llamacpp"


class TranslationSettingPage(QWidget):
    def __init__(self):
        super().__init__()
        self.msg = MessageBoxService(self)
        self._loading_settings = False
        self._llama_runtime = get_llama_runtime()
        self._llama_runtime.set_observers(
            status_cb=self._set_status,
            log_cb=self._append_status,
            running_cb=self._update_run_buttons,
        )
        self._build_ui()
        self._load_settings()
        self._install_auto_save()
        self._refresh_llm_fields_enabled()
        self._refresh_mode_fields()
        self._update_command_preview()
        self._update_run_buttons()

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

        self.btn_open_llama_release = Button("打开 llama.cpp Releases")
        self.btn_open_llama_release.clicked.connect(
            lambda: self._open_url(LLAMA_RELEASE_URL)
        )
        self.btn_open_model_7b = Button("打开 7B 模型页")
        self.btn_open_model_7b.clicked.connect(lambda: self._open_url(LLAMA_MODEL_7B_URL))
        self.btn_open_model_14b = Button("打开 14B 模型页")
        self.btn_open_model_14b.clicked.connect(
            lambda: self._open_url(LLAMA_MODEL_14B_URL)
        )
        self.btn_open_llama_tutorial = Button("打开教程")
        self.btn_open_llama_tutorial.clicked.connect(
            lambda: self._open_url(LLAMA_TUTORIAL_URL)
        )

        self.llama_server_edit = LineEdit(self)
        self.llama_server_edit.setPlaceholderText("llama-server.exe 的绝对路径")
        self.btn_browse_llama_server = Button("浏览")
        self.btn_browse_llama_server.clicked.connect(self._browse_llama_server)
        llama_server_row = self._with_trailing_button(
            self.llama_server_edit, self.btn_browse_llama_server
        )

        self.llama_model_edit = LineEdit(self)
        self.llama_model_edit.setPlaceholderText("GGUF 模型文件路径")
        self.btn_browse_llama_model = Button("浏览")
        self.btn_browse_llama_model.clicked.connect(self._browse_llama_model)
        llama_model_row = self._with_trailing_button(
            self.llama_model_edit, self.btn_browse_llama_model
        )

        self.llama_host_edit = LineEdit(self)
        self.llama_host_edit.setPlaceholderText("127.0.0.1")
        self.llama_port_spin = TokenSpinBox(self)
        self.llama_port_spin.setRange(1, 65535)
        host_port_row = QWidget(self)
        host_port_layout = QHBoxLayout(host_port_row)
        host_port_layout.setContentsMargins(0, 0, 0, 0)
        host_port_layout.addWidget(Label("host"))
        host_port_layout.addWidget(self.llama_host_edit, 1)
        host_port_layout.addWidget(Label("port"))
        host_port_layout.addWidget(self.llama_port_spin)

        self.llama_mode_combo = ComboBox(self)
        self.llama_mode_combo.addItem("GPU", "gpu")
        self.llama_mode_combo.addItem("CPU", "cpu")

        self.llama_preset_combo = ComboBox(self)
        self.llama_preset_combo.addItem("不应用预设", "none")
        self.llama_preset_combo.addItem("8G 显卡预设", "gpu_8g")
        self.llama_preset_combo.addItem("低显存预设", "gpu_low")
        self.llama_preset_combo.addItem("8核CPU预设", "cpu_8")
        self.llama_preset_combo.addItem("16核CPU预设", "cpu_16")

        self.llama_ctx_spin = TokenSpinBox(self)
        self.llama_ctx_spin.setRange(256, 32768)
        self.llama_gpu_layers_spin = TokenSpinBox(self)
        self.llama_gpu_layers_spin.setRange(0, 200)
        self.llama_threads_spin = TokenSpinBox(self)
        self.llama_threads_spin.setRange(1, max(1, (os.cpu_count() or 8) * 2))
        self.llama_threads_batch_spin = TokenSpinBox(self)
        self.llama_threads_batch_spin.setRange(1, max(1, (os.cpu_count() or 8) * 4))
        self.llama_batch_spin = TokenSpinBox(self)
        self.llama_batch_spin.setRange(1, 8192)
        self.llama_ubatch_spin = TokenSpinBox(self)
        self.llama_ubatch_spin.setRange(1, 4096)

        self.llama_mlock_toggle = ToggleSwitch()
        self.llama_auto_sync_toggle = ToggleSwitch()
        self.llama_auto_start_toggle = ToggleSwitch()

        self.llama_cmd_preview = PlainTextEdit(self)
        self.llama_cmd_preview.setReadOnly(True)
        self.llama_cmd_preview.setFixedHeight(72)

        self.llama_status_output = PlainTextEdit(self)
        self.llama_status_output.setReadOnly(True)
        self.llama_status_output.setFixedHeight(96)
        self.llama_status_label = Label("状态：未启动")

        self.btn_llama_start = Button("启动 llama-server")
        self.btn_llama_start.clicked.connect(self._on_start_llama_clicked)
        self.btn_llama_stop = Button("停止")
        self.btn_llama_stop.clicked.connect(self._on_stop_llama_clicked)
        self.btn_llama_probe = Button("测试 /v1/models")
        self.btn_llama_probe.clicked.connect(self._on_probe_models_clicked)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_test)

        llama_link_row = QHBoxLayout()
        llama_link_row.addWidget(self.btn_open_llama_release)
        llama_link_row.addWidget(self.btn_open_model_7b)
        llama_link_row.addWidget(self.btn_open_model_14b)
        llama_link_row.addWidget(self.btn_open_llama_tutorial)

        llama_control_row = QHBoxLayout()
        llama_control_row.addWidget(self.btn_llama_start)
        llama_control_row.addWidget(self.btn_llama_stop)
        llama_control_row.addWidget(self.btn_llama_probe)

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
        layout.addRow(Label(""), Label(""))

        layout.addRow(Label("llama.cpp 辅助"), Label("下载 -> 配置 -> 启动 -> 回填"))
        layout.addRow(Label("快速下载"), llama_link_row)
        layout.addRow(Label("llama-server.exe"), llama_server_row)
        layout.addRow(Label("GGUF 模型"), llama_model_row)
        layout.addRow(Label("监听地址"), host_port_row)
        layout.addRow(Label("运行模式"), self.llama_mode_combo)
        layout.addRow(Label("参数预设"), self.llama_preset_combo)
        layout.addRow(Label("上下文大小"), self.llama_ctx_spin)
        layout.addRow(Label("GPU layers"), self.llama_gpu_layers_spin)
        layout.addRow(Label("threads"), self.llama_threads_spin)
        layout.addRow(Label("threads-batch"), self.llama_threads_batch_spin)
        layout.addRow(Label("batch-size"), self.llama_batch_spin)
        layout.addRow(Label("ubatch-size"), self.llama_ubatch_spin)
        layout.addRow(Label("mlock"), self.llama_mlock_toggle)
        layout.addRow(Label("自动回填翻译配置"), self.llama_auto_sync_toggle)
        layout.addRow(Label("命令预览"), self.llama_cmd_preview)
        layout.addRow(Label("控制"), llama_control_row)
        layout.addRow(Label("打开软件自动启动"), self.llama_auto_start_toggle)
        layout.addRow(Label("运行状态"), self.llama_status_label)
        layout.addRow(Label("日志输出"), self.llama_status_output)
        layout.addRow(
            Label("提示"),
            Label("显存不足请先降 gpu-layers；启动后可点 /v1/models 检查。"),
        )

    def _load_settings(self) -> None:
        self._loading_settings = True
        self._set_combo_by_data(self.engine_combo, get_translation_engine())
        self.model_edit.setText(get_translation_model())
        self.base_url_edit.setText(get_translation_base_url())
        self.api_key_edit.setText(get_translation_api_key())
        self.timeout_spin.setValue(get_translation_timeout_s())
        self.retries_spin.setValue(get_translation_retries())
        self._set_combo_by_data(self.fallback_combo, get_translation_fallback())
        self.llama_server_edit.setText(get_llama_server_exe_path())
        self.llama_model_edit.setText(get_llama_model_path())
        self.llama_host_edit.setText(get_llama_host())
        self.llama_port_spin.setValue(get_llama_port())
        self._set_combo_by_data(self.llama_mode_combo, get_llama_mode())
        self.llama_ctx_spin.setValue(get_llama_ctx_size())
        self.llama_gpu_layers_spin.setValue(get_llama_gpu_layers())
        self.llama_threads_spin.setValue(get_llama_threads())
        self.llama_threads_batch_spin.setValue(get_llama_threads_batch())
        self.llama_batch_spin.setValue(get_llama_batch_size())
        self.llama_ubatch_spin.setValue(get_llama_ubatch_size())
        self.llama_mlock_toggle.setChecked(get_llama_mlock())
        self.llama_auto_sync_toggle.setChecked(get_llama_auto_sync_translation())
        self.llama_auto_start_toggle.setChecked(get_llama_auto_start())
        self._loading_settings = False

    def _install_auto_save(self) -> None:
        self.engine_combo.currentIndexChanged.connect(self._on_setting_changed)
        self.model_edit.editingFinished.connect(self._on_setting_changed)
        self.base_url_edit.editingFinished.connect(self._on_setting_changed)
        self.api_key_edit.editingFinished.connect(self._on_setting_changed)
        self.timeout_spin.valueChanged.connect(self._on_setting_changed)
        self.retries_spin.valueChanged.connect(self._on_setting_changed)
        self.fallback_combo.currentIndexChanged.connect(self._on_setting_changed)
        self.llama_server_edit.editingFinished.connect(self._on_setting_changed)
        self.llama_model_edit.editingFinished.connect(self._on_setting_changed)
        self.llama_host_edit.editingFinished.connect(self._on_setting_changed)
        self.llama_port_spin.valueChanged.connect(self._on_setting_changed)
        self.llama_mode_combo.currentIndexChanged.connect(self._on_llama_mode_changed)
        self.llama_preset_combo.currentIndexChanged.connect(self._on_llama_preset_changed)
        self.llama_ctx_spin.valueChanged.connect(self._on_setting_changed)
        self.llama_gpu_layers_spin.valueChanged.connect(self._on_setting_changed)
        self.llama_threads_spin.valueChanged.connect(self._on_setting_changed)
        self.llama_threads_batch_spin.valueChanged.connect(self._on_setting_changed)
        self.llama_batch_spin.valueChanged.connect(self._on_setting_changed)
        self.llama_ubatch_spin.valueChanged.connect(self._on_setting_changed)
        self.llama_mlock_toggle.toggled.connect(self._on_setting_changed)
        self.llama_auto_sync_toggle.toggled.connect(self._on_setting_changed)
        self.llama_auto_start_toggle.toggled.connect(self._on_setting_changed)

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
        self._update_command_preview()

    def _current_engine(self) -> str:
        return (self.engine_combo.currentData() or "google").strip().lower()

    def _current_llama_mode(self) -> str:
        mode = (self.llama_mode_combo.currentData() or "cpu").strip().lower()
        return mode if mode in {"gpu", "cpu"} else "cpu"

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
        set_llama_server_exe_path(self.llama_server_edit.text())
        set_llama_model_path(self.llama_model_edit.text())
        set_llama_host(self.llama_host_edit.text())
        set_llama_port(int(self.llama_port_spin.value()))
        set_llama_mode(self._current_llama_mode())
        set_llama_ctx_size(int(self.llama_ctx_spin.value()))
        set_llama_gpu_layers(int(self.llama_gpu_layers_spin.value()))
        set_llama_threads(int(self.llama_threads_spin.value()))
        set_llama_threads_batch(int(self.llama_threads_batch_spin.value()))
        set_llama_batch_size(int(self.llama_batch_spin.value()))
        set_llama_ubatch_size(int(self.llama_ubatch_spin.value()))
        set_llama_mlock(self.llama_mlock_toggle.isChecked())
        set_llama_auto_sync_translation(self.llama_auto_sync_toggle.isChecked())
        set_llama_auto_start(self.llama_auto_start_toggle.isChecked())
        logging.info(
            "翻译设置已保存 engine=%s model=%s base_url_set=%s api_key_set=%s",
            self._current_engine(),
            (self.model_edit.text() or "").strip(),
            bool((self.base_url_edit.text() or "").strip()),
            bool((self.api_key_edit.text() or "").strip()),
        )
        if show_message:
            self.msg.show_info("完成", "翻译配置已保存")

    @staticmethod
    def _with_trailing_button(field: QWidget, button: QWidget) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(field, 1)
        row_layout.addWidget(button)
        return row

    def _open_url(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    @Slot()
    def _browse_llama_server(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 llama-server.exe", "", "Executable (*.exe);;All Files (*)"
        )
        if path:
            self.llama_server_edit.setText(path)
            self._on_setting_changed()

    @Slot()
    def _browse_llama_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 GGUF 模型文件", "", "GGUF (*.gguf);;All Files (*)"
        )
        if path:
            self.llama_model_edit.setText(path)
            self._on_setting_changed()

    @Slot()
    def _on_llama_mode_changed(self, *_args) -> None:
        if self._loading_settings:
            return
        self._refresh_mode_fields()
        self._on_setting_changed()

    @Slot()
    def _on_llama_preset_changed(self, *_args) -> None:
        if self._loading_settings:
            return
        preset = (self.llama_preset_combo.currentData() or "none").strip().lower()
        if preset == "gpu_8g":
            self._set_combo_by_data(self.llama_mode_combo, "gpu")
            self.llama_gpu_layers_spin.setValue(99)
            self.llama_batch_spin.setValue(512)
            self.llama_ubatch_spin.setValue(256)
            self.llama_ctx_spin.setValue(1024)
        elif preset == "gpu_low":
            self._set_combo_by_data(self.llama_mode_combo, "gpu")
            self.llama_gpu_layers_spin.setValue(30)
            self.llama_batch_spin.setValue(128)
            self.llama_ubatch_spin.setValue(64)
            self.llama_ctx_spin.setValue(1024)
        elif preset == "cpu_8":
            self._set_combo_by_data(self.llama_mode_combo, "cpu")
            self.llama_gpu_layers_spin.setValue(0)
            self.llama_threads_spin.setValue(8)
            self.llama_threads_batch_spin.setValue(8)
            self.llama_batch_spin.setValue(128)
            self.llama_ubatch_spin.setValue(128)
            self.llama_ctx_spin.setValue(1024)
        elif preset == "cpu_16":
            self._set_combo_by_data(self.llama_mode_combo, "cpu")
            self.llama_gpu_layers_spin.setValue(0)
            self.llama_threads_spin.setValue(16)
            self.llama_threads_batch_spin.setValue(16)
            self.llama_batch_spin.setValue(128)
            self.llama_ubatch_spin.setValue(128)
            self.llama_ctx_spin.setValue(1024)
        self._refresh_mode_fields()
        self._on_setting_changed()

    def _refresh_mode_fields(self) -> None:
        mode = self._current_llama_mode()
        gpu_enabled = mode == "gpu"
        self.llama_gpu_layers_spin.setEnabled(gpu_enabled)
        self.llama_ubatch_spin.setEnabled(True)

    def _collect_llama_launch_config(self) -> LlamaLaunchConfig:
        return LlamaLaunchConfig(
            exe_path=(self.llama_server_edit.text() or "").strip(),
            model_path=(self.llama_model_edit.text() or "").strip(),
            host=(self.llama_host_edit.text() or "127.0.0.1").strip(),
            port=int(self.llama_port_spin.value()),
            mode=self._current_llama_mode(),
            ctx_size=int(self.llama_ctx_spin.value()),
            threads=int(self.llama_threads_spin.value()),
            threads_batch=int(self.llama_threads_batch_spin.value()),
            batch_size=int(self.llama_batch_spin.value()),
            ubatch_size=int(self.llama_ubatch_spin.value()),
            gpu_layers=int(self.llama_gpu_layers_spin.value()),
            mlock=self.llama_mlock_toggle.isChecked(),
        )

    def _update_command_preview(self) -> None:
        cfg = self._collect_llama_launch_config()
        if not cfg.exe_path:
            self.llama_cmd_preview.setPlainText("请先选择 llama-server.exe 路径。")
            return
        args = self._llama_runtime.build_args(cfg)
        self.llama_cmd_preview.setPlainText(
            subprocess.list2cmdline([cfg.exe_path, *args])
        )

    def _set_status(self, text: str) -> None:
        self.llama_status_label.setText(f"状态：{text}")

    def _append_status(self, line: str) -> None:
        current = self.llama_status_output.toPlainText().splitlines()
        current.append(line.strip())
        self.llama_status_output.setPlainText("\n".join(current[-120:]))

    def _update_run_buttons(self, running: bool | None = None) -> None:
        if running is None:
            running = self._llama_runtime.is_running()
        self.btn_llama_start.setEnabled(not running)
        self.btn_llama_stop.setEnabled(running)

    @Slot()
    def _on_start_llama_clicked(self) -> None:
        self._persist_settings(show_message=False)
        self._update_command_preview()
        cfg = self._collect_llama_launch_config()
        err = self._llama_runtime.start(
            cfg,
            auto_sync_translation=self.llama_auto_sync_toggle.isChecked(),
        )
        if err:
            self.msg.show_warning("无法启动", err)
            self._set_status(f"失败（{err}）")
            return
        self._update_run_buttons()

    @Slot()
    def _on_stop_llama_clicked(self) -> None:
        self._llama_runtime.stop()
        self._update_run_buttons()

    @Slot()
    def _on_probe_models_clicked(self) -> None:
        cfg = self._collect_llama_launch_config()
        self._llama_runtime.probe_models(cfg, trigger_sync=False)

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
