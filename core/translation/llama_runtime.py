"""llama.cpp 运行时管理：启动、停止、健康检查与可选翻译回填。"""

from __future__ import annotations

import json
import logging
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request

from PySide6.QtCore import QObject, QProcess, QTimer

from config import (
    get_llama_auto_start,
    get_translation_api_key,
    set_translation_api_key,
    set_translation_base_url,
    set_translation_engine,
    set_translation_model,
    set_translation_retries,
    set_translation_timeout_s,
)
from core.crawler.worker import Worker, wire_worker_finished


@dataclass
class LlamaLaunchConfig:
    exe_path: str
    model_path: str
    host: str
    port: int
    mode: str
    ctx_size: int
    threads: int
    threads_batch: int
    batch_size: int
    ubatch_size: int
    gpu_layers: int
    mlock: bool


class LlamaRuntime(QObject):
    """单例运行时，供设置页和开机自启共用。"""

    def __init__(self) -> None:
        super().__init__()
        self._process: QProcess | None = None
        self._health_attempts = 0
        self._health_timer = QTimer(self)
        self._health_timer.setSingleShot(True)
        self._health_timer.timeout.connect(self._on_health_timer)
        self._pending_cfg: LlamaLaunchConfig | None = None
        self._auto_sync_translation = True
        self._status_cb: callable | None = None
        self._log_cb: callable | None = None
        self._running_cb: callable | None = None

    def set_observers(
        self,
        *,
        status_cb: callable | None = None,
        log_cb: callable | None = None,
        running_cb: callable | None = None,
    ) -> None:
        self._status_cb = status_cb
        self._log_cb = log_cb
        self._running_cb = running_cb

    def is_running(self) -> bool:
        return (
            self._process is not None
            and self._process.state() != QProcess.ProcessState.NotRunning
        )

    @staticmethod
    def build_args(cfg: LlamaLaunchConfig) -> list[str]:
        args = [
            "--host",
            cfg.host.strip() or "127.0.0.1",
            "--port",
            str(int(cfg.port)),
            "--model",
            cfg.model_path.strip(),
            "-c",
            str(int(cfg.ctx_size)),
            "-n",
            "512",
            "--threads",
            str(int(cfg.threads)),
            "--threads-batch",
            str(int(cfg.threads_batch)),
            "--batch-size",
            str(int(cfg.batch_size)),
            "--ubatch-size",
            str(int(cfg.ubatch_size)),
        ]
        if (cfg.mode or "cpu").strip().lower() == "cpu":
            args.extend(["--gpu-layers", "0"])
        else:
            args.extend(["--gpu-layers", str(max(0, int(cfg.gpu_layers)))])
        if bool(cfg.mlock):
            args.append("--mlock")
        return args

    @staticmethod
    def validate(cfg: LlamaLaunchConfig) -> str | None:
        exe = (cfg.exe_path or "").strip()
        if not exe:
            return "请先选择 llama-server.exe 路径。"
        if not Path(exe).is_file():
            return "llama-server.exe 路径无效。"
        model = (cfg.model_path or "").strip()
        if not model:
            return "请先选择 GGUF 模型路径。"
        if not Path(model).is_file():
            return "GGUF 模型路径无效。"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            if sock.connect_ex((cfg.host.strip() or "127.0.0.1", int(cfg.port))) == 0:
                return f"{cfg.host}:{cfg.port} 端口已占用。"
        return None

    def start(self, cfg: LlamaLaunchConfig, *, auto_sync_translation: bool) -> str | None:
        err = self.validate(cfg)
        if err:
            self._emit_status(f"失败（{err}）")
            return err
        if self._process is not None and self.is_running():
            self.stop()
        self._pending_cfg = cfg
        self._auto_sync_translation = auto_sync_translation
        process = QProcess(self)
        process.setProgram(cfg.exe_path)
        process.setArguments(self.build_args(cfg))
        process.setWorkingDirectory(str(Path(cfg.exe_path).parent))
        process.readyReadStandardOutput.connect(self._on_stdout)
        process.readyReadStandardError.connect(self._on_stderr)
        process.errorOccurred.connect(self._on_error)
        process.finished.connect(self._on_finished)
        self._process = process
        self._emit_status("启动中")
        self._emit_log("正在启动 llama-server ...")
        process.start()
        if not process.waitForStarted(2000):
            self._emit_status("失败（启动进程失败）")
            return "无法拉起 llama-server.exe，请检查路径或权限。"
        self._emit_running(True)
        self._health_attempts = 0
        self._health_timer.start(1000)
        return None

    def stop(self) -> None:
        if self._process is None:
            return
        if self._process.state() == QProcess.ProcessState.NotRunning:
            self._emit_status("未启动")
            self._emit_running(False)
            return
        self._process.terminate()
        if not self._process.waitForFinished(2000):
            self._process.kill()
            self._process.waitForFinished(1000)
        self._emit_status("已停止")
        self._emit_log("已停止 llama-server。")
        self._emit_running(False)

    def probe_models(self, cfg: LlamaLaunchConfig, *, trigger_sync: bool) -> None:
        worker = Worker(lambda: self._request_models(cfg))
        if trigger_sync:
            wire_worker_finished(worker, self._on_probe_for_health_finished)
        else:
            wire_worker_finished(worker, self._on_probe_manual_finished)
        from PySide6.QtCore import QThreadPool

        QThreadPool.globalInstance().start(worker)

    def maybe_auto_start(self, cfg: LlamaLaunchConfig, *, auto_sync_translation: bool) -> None:
        if not get_llama_auto_start():
            return
        err = self.start(cfg, auto_sync_translation=auto_sync_translation)
        if err:
            logging.warning("llama 自启失败: %s", err)

    def _on_health_timer(self) -> None:
        if self._pending_cfg is None:
            return
        self.probe_models(self._pending_cfg, trigger_sync=True)

    def _request_models(self, cfg: LlamaLaunchConfig) -> dict[str, object]:
        url = f"http://{cfg.host}:{int(cfg.port)}/v1/models"
        req = request.Request(url=url, method="GET")
        try:
            with request.urlopen(req, timeout=3.0) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            data = payload.get("data") if isinstance(payload, dict) else None
            model_name = ""
            if isinstance(data, list) and data:
                first = data[0]
                model_name = (first.get("id") or "").strip() if isinstance(first, dict) else str(first).strip()
            return {"ok": True, "model": model_name}
        except (error.URLError, TimeoutError, ValueError, OSError) as exc:
            return {"ok": False, "error": str(exc)}

    def _on_probe_manual_finished(self, result: object) -> None:
        if isinstance(result, dict) and result.get("ok"):
            model_name = str(result.get("model") or "").strip()
            self._emit_log(f"/v1/models 可用，模型：{model_name or '未知'}")
            return
        self._emit_log(f"/v1/models 检测失败：{(result or {}).get('error') if isinstance(result, dict) else '未知错误'}")

    def _on_probe_for_health_finished(self, result: object) -> None:
        if not isinstance(result, dict):
            self._retry_health()
            return
        if result.get("ok"):
            model_name = str(result.get("model") or "").strip()
            self._emit_status("运行中")
            if self._pending_cfg is not None:
                self._emit_log(
                    f"服务就绪：http://{self._pending_cfg.host}:{int(self._pending_cfg.port)}/v1/models"
                )
            if self._auto_sync_translation and self._pending_cfg is not None:
                self._sync_translation(model_name, self._pending_cfg)
            return
        self._emit_log(
            f"健康检查失败({self._health_attempts + 1}/10)：{result.get('error') or '未知错误'}"
        )
        self._retry_health()

    def _retry_health(self) -> None:
        self._health_attempts += 1
        if self._health_attempts >= 10:
            self._emit_status("失败（/v1/models 未就绪）")
            return
        self._health_timer.start(1000)

    def _sync_translation(self, model_name: str, cfg: LlamaLaunchConfig) -> None:
        set_translation_engine("llm")
        set_translation_base_url(f"http://{cfg.host}:{int(cfg.port)}/v1")
        if model_name:
            set_translation_model(model_name)
        if (cfg.mode or "cpu").strip().lower() == "cpu":
            set_translation_timeout_s(40)
            set_translation_retries(0)
        if not (get_translation_api_key() or "").strip():
            set_translation_api_key("local")
        self._emit_log("已自动回填翻译配置（引擎、Base URL、模型）。")

    def _on_stdout(self) -> None:
        if self._process is None:
            return
        text = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="ignore")
        for line in text.splitlines():
            self._emit_log(line)

    def _on_stderr(self) -> None:
        if self._process is None:
            return
        text = bytes(self._process.readAllStandardError()).decode("utf-8", errors="ignore")
        for line in text.splitlines():
            self._emit_log(line)

    def _on_error(self, process_error: QProcess.ProcessError) -> None:
        self._emit_status(f"失败（进程错误：{int(process_error)}）")
        self._emit_running(False)

    def _on_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._emit_log(f"llama-server 已退出，exit_code={exit_code}")
        self._emit_status("已停止")
        self._emit_running(False)

    def _emit_status(self, text: str) -> None:
        if self._status_cb:
            self._status_cb(text)

    def _emit_log(self, line: str) -> None:
        if self._log_cb:
            self._log_cb(line)

    def _emit_running(self, running: bool) -> None:
        if self._running_cb:
            self._running_cb(running)


_RUNTIME: LlamaRuntime | None = None


def get_llama_runtime() -> LlamaRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = LlamaRuntime()
    return _RUNTIME

