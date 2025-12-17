from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    api_base: str
    api_key: str
    model: str
    timeout_s: int


class LlmClient:
    def __init__(self, config: LlmConfig) -> None:
        self._config = config

    def enabled(self) -> bool:
        return bool(self._config.api_key) and self._config.provider.lower() != "none"

    def chat_json(self, messages: list[dict[str, str]], temperature: float = 0.0) -> dict[str, Any]:
        provider = self._config.provider.lower()
        if provider in ("openai_compatible", "openai-compatible", "openai"):
            return self._chat_openai_compatible(messages=messages, temperature=temperature)
        raise ValueError(f"Unsupported AI_PROVIDER: {self._config.provider}")

    def _chat_openai_compatible(
        self, messages: list[dict[str, str]], temperature: float
    ) -> dict[str, Any]:
        url = self._config.api_base.rstrip("/") + "/v1/chat/completions"
        payload = {
            "model": self._config.model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self._config.api_key}")

        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self._config.timeout_s) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            raise RuntimeError(f"LLM HTTPError {exc.code}: {raw[:500]!r}") from exc
        except Exception as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc

        try:
            parsed: dict[str, Any] = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"LLM returned non-JSON: {raw[:500]!r}") from exc

        content = (
            (((parsed.get("choices") or [None])[0]) or {}).get("message") or {}
        ).get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(f"LLM missing content: {parsed}")

        try:
            obj: dict[str, Any] = json.loads(content)
        except Exception:
            obj = {"raw": content}

        obj["_meta"] = {
            "provider": self._config.provider,
            "model": self._config.model,
            "latency_ms": int((time.time() - start) * 1000),
        }
        return obj


def load_llm_config_from_env() -> LlmConfig:
    return LlmConfig(
        provider=os.getenv("AI_PROVIDER", "none"),
        api_base=os.getenv("AI_API_BASE", "http://localhost:11434"),
        api_key=os.getenv("AI_API_KEY", ""),
        model=os.getenv("AI_MODEL", "gpt-4o-mini"),
        timeout_s=int(os.getenv("AI_TIMEOUT_S", "30")),
    )

