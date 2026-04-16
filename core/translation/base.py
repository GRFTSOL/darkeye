from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TranslationRuntimeConfig:
    timeout_s: float = 12.0
    retries: int = 2
    backoff_base_s: float = 0.6
    fallback: str = "empty"
    translation_variant: str = "default"


@dataclass(frozen=True)
class TranslationEngineConfig:
    engine: str
    model: str
    base_url: str
    api_key: str


class TranslatorEngine(Protocol):
    async def translate(
        self,
        text: str,
        dest: str,
        runtime: TranslationRuntimeConfig,
    ) -> str: ...
