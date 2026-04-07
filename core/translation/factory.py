from __future__ import annotations

import logging

from config import get_translation_engine_settings

from .base import TranslationEngineConfig, TranslatorEngine
from .google_engine import GoogleTranslatorEngine
from .llm_engine import LlmTranslatorEngine


def get_translator_engine() -> tuple[TranslatorEngine, TranslationEngineConfig]:
    cfg = get_translation_engine_settings()
    engine_name = (cfg.engine or "google").strip().lower()
    if engine_name == "llm":
        if not cfg.model or not cfg.base_url or not cfg.api_key:
            logging.warning("翻译引擎=llm 但配置不完整，已降级到 google")
            return GoogleTranslatorEngine(), cfg
        return LlmTranslatorEngine(cfg), cfg
    return GoogleTranslatorEngine(), cfg
