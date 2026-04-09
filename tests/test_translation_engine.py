import asyncio
import sys
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
core_pkg = types.ModuleType("core")
core_pkg.__path__ = [str(_ROOT / "core")]
sys.modules.setdefault("core", core_pkg)

if "PySide6" not in sys.modules:
    pyside6 = types.ModuleType("PySide6")
    qtgui = types.ModuleType("PySide6.QtGui")
    qtwidgets = types.ModuleType("PySide6.QtWidgets")

    class _Dummy:
        pass

    qtgui.QImage = _Dummy
    qtgui.QPixmap = _Dummy
    qtgui.QColor = _Dummy
    qtwidgets.QWidget = _Dummy
    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtGui"] = qtgui
    sys.modules["PySide6.QtWidgets"] = qtwidgets

if "config" not in sys.modules:
    cfg = types.ModuleType("config")
    cfg.DATABASE = "test.db"
    cfg.get_translation_runtime_settings = (
        lambda: types.SimpleNamespace(
            timeout_s=12.0,
            retries=2,
            backoff_base_s=0.6,
            fallback="empty",
        )
    )
    cfg.get_translation_engine_settings = (
        lambda: types.SimpleNamespace(
            engine="google",
            model="",
            base_url="",
            api_key="",
        )
    )
    sys.modules["config"] = cfg

if "googletrans" not in sys.modules:
    googletrans = types.ModuleType("googletrans")

    class _Translator:
        async def translate(self, src, dest="zh-CN"):
            return types.SimpleNamespace(text=src)

    googletrans.Translator = _Translator
    sys.modules["googletrans"] = googletrans

from core.translation.base import (
    TranslationEngineConfig,
    TranslationRuntimeConfig,
)
from core.translation.factory import get_translator_engine
from core.translation.google_engine import GoogleTranslatorEngine
from core.translation.llm_engine import LlmTranslatorEngine


def test_factory_fallback_to_google_when_llm_config_incomplete(monkeypatch):
    cfg = TranslationEngineConfig(
        engine="llm",
        model="",
        base_url="https://example.com/v1",
        api_key="",
    )
    monkeypatch.setattr("core.translation.factory.get_translation_engine_settings", lambda: cfg)
    engine, _ = get_translator_engine()
    assert isinstance(engine, GoogleTranslatorEngine)


def test_factory_selects_llm_when_config_complete(monkeypatch):
    cfg = TranslationEngineConfig(
        engine="llm",
        model="deepseek-chat",
        base_url="https://example.com/v1",
        api_key="sk-xx",
    )
    monkeypatch.setattr("core.translation.factory.get_translation_engine_settings", lambda: cfg)
    engine, out_cfg = get_translator_engine()
    assert isinstance(engine, LlmTranslatorEngine)
    assert out_cfg.model == "deepseek-chat"


def test_llm_engine_returns_empty_on_invalid_config():
    engine = LlmTranslatorEngine(
        TranslationEngineConfig(
            engine="llm",
            model="",
            base_url="",
            api_key="",
        )
    )
    out = asyncio.run(
        engine.translate(
            "テスト",
            "zh-CN",
            TranslationRuntimeConfig(fallback="source"),
        )
    )
    assert out == ""

