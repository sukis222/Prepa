"""Explicit rate-limit fallback from the primary provider to a local adapter."""

import time
from collections.abc import Callable
from typing import Any, Protocol

from prepa.agents.contracts import StructuredLLM

from .openrouter import LLMError


class ManagedStructuredLLM(StructuredLLM, Protocol):
    async def check_model(self) -> None: ...

    async def aclose(self) -> None: ...


class RateLimitFallbackLLM:
    """Use the injected local fallback for 60 seconds only after a rate limit.

    Both dependencies must be configured by the application. This adapter creates
    no clients, changes no models and never retries authentication/response errors.
    """

    def __init__(
        self,
        primary: ManagedStructuredLLM,
        fallback: ManagedStructuredLLM,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self._clock = clock
        self._fallback_until = 0.0

    def _cooldown_active(self) -> bool:
        return self._clock() < self._fallback_until

    async def _activate_fallback(self) -> None:
        # Do not send a prompt until the explicitly configured local model is available.
        await self.fallback.check_model()
        self._fallback_until = self._clock() + 60.0

    async def check_model(self) -> None:
        if self._cooldown_active():
            await self.fallback.check_model()
            return
        try:
            await self.primary.check_model()
        except LLMError as error:
            if error.code != "rate_limit":
                raise
            await self._activate_fallback()

    async def generate(
        self, *, system_prompt: str, user_prompt: str, response_schema: dict[str, Any]
    ) -> str | dict[str, Any]:
        if self._cooldown_active():
            return await self.fallback.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_schema=response_schema,
            )
        try:
            return await self.primary.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_schema=response_schema,
            )
        except LLMError as error:
            if error.code != "rate_limit":
                raise
            await self._activate_fallback()
            return await self.fallback.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_schema=response_schema,
            )

    async def aclose(self) -> None:
        try:
            await self.primary.aclose()
        finally:
            await self.fallback.aclose()
