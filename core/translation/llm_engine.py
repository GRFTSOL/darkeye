from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import requests

from .base import TranslationEngineConfig, TranslationRuntimeConfig, TranslatorEngine

_SYSTEM_PROMPT = (
    "你是专业的日文到中文翻译引擎。"
    "只输出译文，不添加任何解释、前后缀、引号或注释。"
    "保留番号、系列名、人名、专有名词。"
    "若输入为空，返回空字符串。"
    "将淫荡的用语翻译到位"
)


class LlmTranslatorEngine(TranslatorEngine):
    def __init__(self, config: TranslationEngineConfig):
        self._model = (config.model or "").strip()
        self._base_url = (config.base_url or "").strip().rstrip("/")
        self._api_key = (config.api_key or "").strip()

    async def translate(
        self,
        text: str,
        dest: str,
        runtime: TranslationRuntimeConfig,
    ) -> str:
        src = (text or "").strip()
        if not src:
            return ""
        if not self._model or not self._base_url or not self._api_key:
            logging.warning("LLM翻译配置不完整，返回空字符串")
            return ""

        max_retries = max(0, int(runtime.retries))
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                out = await asyncio.to_thread(
                    self._request_translation,
                    src,
                    dest,
                    float(runtime.timeout_s),
                )
                if out:
                    return out
                last_exc = RuntimeError("Empty llm translation result")
            except Exception as e:
                last_exc = e
                logging.warning(
                    "LLM翻译失败 attempt=%s/%s model=%s err=%s",
                    attempt + 1,
                    max_retries + 1,
                    self._model,
                    repr(e),
                )
            if attempt < max_retries:
                await asyncio.sleep(
                    float(runtime.backoff_base_s) * (2**attempt)
                    + random.uniform(0.0, 0.2)
                )

        if last_exc is not None:
            logging.warning("LLM翻译最终失败，返回空字符串: %s", repr(last_exc))
        return ""

    def _request_translation(self, src: str, dest: str, timeout_s: float) -> str:
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self._model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"将以下文本翻译为 {dest}，只输出译文：\n\n"
                        f"{src}"
                    ),
                },
            ],
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return ""
        msg = choices[0].get("message") or {}
        content = (msg.get("content") or "").strip()
        if not content:
            return ""
        return content.strip(" \n\r\t\"'")
