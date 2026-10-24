"""Bounded, free-only OpenRouter StructuredLLM adapter; no hidden model retries."""

import json
import math
import os
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import httpx

DEFAULT_MODEL = "dots-studio/dots-3-note-preview:free"
BASE_URL = "https://openrouter.ai/api/v1"
FinishReason = Literal["stop", "length", "content_filter", "tool_calls", "error", "unknown"]


class LLMError(RuntimeError):
    """Sanitized provider failure. Never includes a key, prompt or provider response."""

    def __init__(self, code: str, *, finish_reason: object = None) -> None:
        self.code = code
        self.finish_reason: FinishReason | None = None
        if finish_reason is not None:
            # Only normalized public enums may cross the provider error boundary.
            # Never preserve native_finish_reason, response content or arbitrary strings.
            match finish_reason:
                case "stop" | "length" | "content_filter" | "tool_calls" | "error":
                    self.finish_reason = finish_reason
                case _:
                    self.finish_reason = "unknown"
        super().__init__(f"OpenRouter: {code}")


@dataclass(frozen=True)
class OpenRouterSettings:
    api_key: str = field(repr=False)
    model: str = DEFAULT_MODEL
    timeout_seconds: float = 120
    max_tokens: int = 8192
    reasoning: str = "default"

    def __post_init__(self) -> None:
        if self.reasoning not in ("default", "off"):
            raise ValueError("OPENROUTER_REASONING: default или off")
        if not self.api_key.strip():
            raise ValueError("Задайте OPENROUTER_API_KEY для PREPARATION_MODE=real")
        if not self.model.endswith(":free"):
            raise ValueError("OPENROUTER_MODEL должен быть явной бесплатной моделью (:free)")
        if not math.isfinite(self.timeout_seconds) or not 1 <= self.timeout_seconds <= 120:
            raise ValueError("OPENROUTER_TIMEOUT_SECONDS: от 1 до 120")
        if type(self.max_tokens) is not int or not 256 <= self.max_tokens <= 16384:
            raise ValueError("OPENROUTER_MAX_TOKENS: от 256 до 16384")

    @classmethod
    def from_env(cls) -> "OpenRouterSettings":
        # A fixed official origin prevents accidental forwarding of credentials to a custom URL.
        if os.environ.get("OPENROUTER_BASE_URL", BASE_URL).rstrip("/") != BASE_URL:
            raise ValueError("OPENROUTER_BASE_URL должен указывать на официальный API OpenRouter")
        try:
            timeout = float(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "120"))
            tokens = int(os.environ.get("OPENROUTER_MAX_TOKENS", "8192"))
        except ValueError:
            raise ValueError("Некорректные лимиты OpenRouter") from None
        return cls(
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            model=os.environ.get("OPENROUTER_MODEL", "").strip() or DEFAULT_MODEL,
            timeout_seconds=timeout,
            max_tokens=tokens,
            reasoning=os.environ.get("OPENROUTER_REASONING", "default").strip(),
        )


class OpenRouterLLM:
    def __init__(
        self, settings: OpenRouterSettings, *, http: httpx.AsyncClient | None = None
    ) -> None:
        self.settings = settings
        self.http = http or httpx.AsyncClient(timeout=settings.timeout_seconds)

    async def aclose(self) -> None:
        await self.http.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await self.http.request(
                method, BASE_URL + path, timeout=self.settings.timeout_seconds, **kwargs
            )
        except httpx.TimeoutException:
            raise LLMError("timeout") from None
        except httpx.HTTPError:
            raise LLMError("unavailable") from None
        if response.status_code != 200:
            code = {
                400: "invalid_request",
                401: "authentication",
                402: "quota",
                403: "access_denied",
                404: "model_unavailable",
                429: "rate_limit",
                502: "provider_unavailable",
                503: "provider_unavailable",
                504: "provider_unavailable",
            }.get(response.status_code, "unavailable")
            raise LLMError(code)
        if len(response.content) > (5_000_000 if path == "/models" else 1_000_000):
            raise LLMError("response_too_large")
        try:
            value = response.json()
        except ValueError:
            raise LLMError("invalid_response") from None
        if not isinstance(value, dict) or "error" in value:
            raise LLMError("invalid_response")
        return value

    async def check_model(self) -> None:
        """Recheck public catalog before each preparation, before sending personal context."""
        catalog = await self._request("GET", "/models")
        for model in catalog.get("data", ()):
            if isinstance(model, dict) and model.get("id") == self.settings.model:
                try:
                    prices = model["pricing"]
                    free = (
                        all(Decimal(str(prices[key])) == 0 for key in ("prompt", "completion"))
                        and Decimal(str(prices.get("request", "0"))) == 0
                    )
                except (KeyError, TypeError, InvalidOperation):
                    free = False
                supported = model.get("supported_parameters", ())
                if not free:
                    raise LLMError("model_not_free")
                if not {"response_format", "structured_outputs"} <= set(supported):
                    raise LLMError("structured_outputs_unavailable")
                if self.settings.reasoning == "off" and (
                    "reasoning" not in supported
                    or model.get("reasoning", {}).get("mandatory", False)
                ):
                    raise LLMError("reasoning_configuration_unavailable")
                return
        raise LLMError("model_unavailable")

    async def generate(
        self, *, system_prompt: str, user_prompt: str, response_schema: dict[str, Any]
    ) -> dict[str, Any]:
        # Keep the exact contract visible to the model as well as the native provider.
        # strict=False endpoints can return valid JSON with an incorrect object shape.
        # This schema is trusted application data, never a pupil/material instruction.
        schema_text = json.dumps(response_schema, ensure_ascii=False)
        instruction = (
            system_prompt
            + "\nТочная JSON Schema результата (объект без Markdown и обёрток):\n"
            + schema_text
        )
        if len(instruction) + len(user_prompt) > 300_000:
            raise LLMError("input_too_large")
        result = await self._request(
            "POST",
            "/chat/completions",
            headers={"Authorization": f"Bearer {self.settings.api_key}"},
            json={
                "model": self.settings.model,
                "messages": [
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": self.settings.max_tokens,
                "temperature": 0.2,
                **({"reasoning": {"enabled": False}} if self.settings.reasoning == "off" else {}),
                "provider": {
                    "require_parameters": True,
                    "max_price": {"prompt": 0, "completion": 0},
                },
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_schema.get("title", "PrepaResponse"),
                        # Existing schemas contain unions/defaults. Local Pydantic validation
                        # remains mandatory; don't rewrite the shared schema to fit strict mode.
                        "strict": False,
                        "schema": response_schema,
                    },
                },
            },
        )
        try:
            choice = result["choices"][0]
            if choice["finish_reason"] != "stop":
                raise LLMError("incomplete_response", finish_reason=choice["finish_reason"])
            content = choice["message"]["content"]
            if not isinstance(content, str) or len(content) > 200_000:
                raise LLMError("invalid_response")
            value = json.loads(content)
            if not isinstance(value, dict):
                raise LLMError("invalid_response")
            return value
        except (KeyError, IndexError, TypeError, ValueError):
            raise LLMError("invalid_response") from None
