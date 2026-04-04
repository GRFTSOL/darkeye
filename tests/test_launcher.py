"""ServerLauncher：线程启动方式与默认参数（stub bridge，无需 GUI）。"""

import importlib.util
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

_LAUNCHER = "server.launcher"


def _get_server_launcher_module():
    if _LAUNCHER in sys.modules:
        return sys.modules[_LAUNCHER]

    pkg = sys.modules.setdefault("server", types.ModuleType("server"))
    pkg.__path__ = [str(_ROOT / "server")]

    br = types.ModuleType("server.bridge")

    def _noop_bridge():
        return None

    br.get_bridge = _noop_bridge
    sys.modules["server.bridge"] = br

    spec = importlib.util.spec_from_file_location(
        _LAUNCHER,
        _ROOT / "server" / "launcher.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_LAUNCHER] = mod
    spec.loader.exec_module(mod)
    return mod


def test_server_launcher_defaults():
    mod = _get_server_launcher_module()
    sl = mod.ServerLauncher()
    assert sl.host == "127.0.0.1"
    assert sl.port == 56789
    assert sl.server_thread is None


def test_server_launcher_custom_host_port():
    mod = _get_server_launcher_module()
    sl = mod.ServerLauncher(host="0.0.0.0", port=12345)
    assert sl.host == "0.0.0.0"
    assert sl.port == 12345


@patch("threading.Thread")
def test_start_creates_daemon_thread(mock_thread_class):
    mod = _get_server_launcher_module()
    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = False
    mock_thread_class.return_value = mock_thread

    sl = mod.ServerLauncher()
    sl.start()

    mock_thread_class.assert_called_once()
    _, kwargs = mock_thread_class.call_args
    assert kwargs["daemon"] is True
    assert kwargs["target"] == sl._run_fastapi
    mock_thread.start.assert_called_once()


@patch("threading.Thread")
def test_start_skips_when_thread_alive(mock_thread_class):
    mod = _get_server_launcher_module()
    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = True
    mock_thread_class.return_value = mock_thread

    sl = mod.ServerLauncher()
    sl.server_thread = mock_thread
    sl.start()

    mock_thread_class.assert_not_called()
