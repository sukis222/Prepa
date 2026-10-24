"""Optional local-only Ollama implementation of StructuredLLM."""

import json
import math
import os
from dataclasses import dataclass
from typing import Any

import httpx

from .openrouter import LLMError

BASE_URL = "http://127.0.0.1:11434"


@dataclass(frozen=True)
class OllamaSettings:
    model: str = "qwen3:8b"
    timeout_seconds: float = 120
    context_tokens: int = 16384

    def __post_init__(self) -> None:
        if not self.model.strip() or len(self.model) > 200 or any(c.isspace() for c in self.model):
            raise ValueError("OLLAMA_MODEL: требуется локальное имя модели")
        if not math.isfinite(self.timeout_seconds) or not 1 <= self.timeout_seconds <= 120:
            raise ValueError("OLLAMA_TIMEOUT: от 1 до 120 секунд")
        if type(self.context_tokens) is not int or not 8192 <= self.context_tokens <= 65536:
            raise ValueError("OLLAMA_CONTEXT: от 8192 до 65536 токенов")

    @classmethod
    def from_env(cls) -> "OllamaSettings":
        try:
            timeout = float(os.environ.get("OLLAMA_TIMEOUT", "120"))
            context = int(os.environ.get("OLLAMA_CONTEXT", "16384"))
        except ValueError:
            raise ValueError("Некорректные лимиты Ollama") from None
        return cls(
            model=os.environ.get("OLLAMA_MODEL", "qwen3:8b"),
            timeout_seconds=timeout,
            context_tokens=context,
        )


class OllamaLLM:
    def __init__(self, settings: OllamaSettings, *, http: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.http = http or httpx.AsyncClient(
            timeout=settings.timeout_seconds, trust_env=False, follow_redirects=False
        )

    async def aclose(self) -> None:
        await self.http.aclose()

    async def _request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self.http.post(
                BASE_URL + path,
                json=payload,
                timeout=self.settings.timeout_seconds,
                follow_redirects=False,
            )
        except httpx.TimeoutException:
            raise LLMError("timeout") from None
        except httpx.HTTPError:
            raise LLMError("unavailable") from None
        if response.status_code != 200:
            raise LLMError(
                {400: "invalid_request", 404: "model_unavailable", 429: "rate_limit"}.get(
                    response.status_code, "provider_unavailable"
                )
            )
        if len(response.content) > 1_000_000:
            raise LLMError("response_too_large")
        try:
            value = response.json()
        except ValueError:
            raise LLMError("invalid_response") from None
        if not isinstance(value, dict) or "error" in value:
            raise LLMError("invalid_response")
        return value

    async def check_model(self) -> None:
        """Check that the explicitly chosen model is already installed; never pull it."""
        result = await self._request("/api/show", {"model": self.settings.model})
        capabilities = result.get("capabilities", [])
        if not isinstance(capabilities, list) or "completion" not in capabilities:
            raise LLMError("structured_outputs_unavailable")

    async def generate(
        self, *, system_prompt: str, user_prompt: str, response_schema: dict[str, Any]
    ) -> dict[str, Any]:
        schema_text = json.dumps(response_schema, ensure_ascii=False)
        instruction = (
            system_prompt
            + "\nТочная JSON Schema результата (объект без Markdown и обёрток):\n"
            + schema_text
        )
        if len(instruction) + len(user_prompt) > 300_000:
            raise LLMError("input_too_large")
        result = await self._request(
            "/api/chat",
            {
                "model": self.settings.model,
                "messages": [
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": user_prompt},
                ],
                "format": response_schema,
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 4096,
                    "num_ctx": self.settings.context_tokens,
                },
            },
        )
        if result.get("done") is not True:
            raise LLMError("incomplete_response")
        if result.get("done_reason") != "stop":
            raise LLMError(
                "incomplete_response", finish_reason=result.get("done_reason", "unknown")
            )
        try:
            message = result["message"]
            if message.get("role") != "assistant":
                raise LLMError("invalid_response")
            content = message["content"]
            if not isinstance(content, str) or len(content) > 200_000:
                raise LLMError("invalid_response")
            value = json.loads(content)
            if not isinstance(value, dict):
                raise LLMError("invalid_response")
            return value
        except (KeyError, TypeError, AttributeError, ValueError):
            raise LLMError("invalid_response") from None
