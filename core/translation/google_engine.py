from __future__ import annotations

import asyncio
import logging
import random

from googletrans import Translator

from .base import TranslationRuntimeConfig, TranslatorEngine


class GoogleTranslatorEngine(TranslatorEngine):
    async def translate(
        self,
        text: str,
        dest: str,
        runtime: TranslationRuntimeConfig,
    ) -> str:
        src = (text or "").strip()
        if not src:
            return ""

        last_exc: Exception | None = None
        max_retries = max(0, int(runtime.retries))
        for attempt in range(max_retries + 1):
            try:
                translator = Translator()
                coro = translator.translate(src, dest=dest)
                result = await asyncio.wait_for(coro, timeout=float(runtime.timeout_s))
                out = (getattr(result, "text", "") or "").strip()
                if out:
                    return out
                last_exc = RuntimeError("Empty translate result")
            except Exception as e:
                last_exc = e
                logging.warning(
                    "google翻译失败 attempt=%s/%s dest=%s err=%s",
                    attempt + 1,
                    max_retries + 1,
                    dest,
                    repr(e),
                )
            if attempt < max_retries:
                await asyncio.sleep(
                    float(runtime.backoff_base_s) * (2**attempt)
                    + random.uniform(0.0, 0.2)
                )

        if last_exc is not None:
            logging.warning("google翻译最终失败，返回空字符串: %s", repr(last_exc))
        return ""
