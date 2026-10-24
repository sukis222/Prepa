"""Rate-limit-only local fallback and recovery with a deterministic clock."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from prepa.llm import LLMError
from prepa.llm.fallback import RateLimitFallbackLLM


def run(coro):
    return asyncio.run(coro)


@dataclass
class Provider:
    name: str
    check_error: Exception | None = None
    generate_error: Exception | None = None
    close_error: Exception | None = None
    checks: int = 0
    closes: int = 0
    prompts: list[dict[str, Any]] = field(default_factory=list)

    async def check_model(self) -> None:
        self.checks += 1
        if self.check_error:
            raise self.check_error

    async def generate(self, **kwargs: Any) -> dict[str, Any]:
        self.prompts.append(kwargs)
        if self.generate_error:
            raise self.generate_error
        return {"provider": self.name}

    async def aclose(self) -> None:
        self.closes += 1
        if self.close_error:
            raise self.close_error


def generate(llm):
    return run(
        llm.generate(system_prompt="system", user_prompt="user", response_schema={"type": "object"})
    )


def test_primary_used_normally():
    primary, local = Provider("primary"), Provider("local")
    llm = RateLimitFallbackLLM(primary, local)
    run(llm.check_model())
    assert generate(llm) == {"provider": "primary"}
    assert primary.checks == 1
    assert local.checks == 0
    assert local.prompts == []


def test_generation_rate_limit_activates_local_then_recovers():
    now = [100.0]
    primary, local = Provider("primary", generate_error=LLMError("rate_limit")), Provider("local")
    llm = RateLimitFallbackLLM(primary, local, clock=lambda: now[0])
    assert generate(llm) == {"provider": "local"}
    assert local.checks == 1
    assert local.prompts[0] == primary.prompts[0]
    now[0] = 159.0
    assert generate(llm) == {"provider": "local"}
    run(llm.check_model())
    assert primary.checks == 0
    assert len(primary.prompts) == 1
    assert local.checks == 2
    now[0] = 160.0
    primary.generate_error = None
    run(llm.check_model())
    assert generate(llm) == {"provider": "primary"}
    assert primary.checks == 1


def test_catalog_rate_limit_checks_local_before_generation():
    primary, local = Provider("primary", check_error=LLMError("rate_limit")), Provider("local")
    llm = RateLimitFallbackLLM(primary, local, clock=lambda: 100.0)
    run(llm.check_model())
    assert local.checks == 1
    assert generate(llm) == {"provider": "local"}
    assert primary.prompts == []


@pytest.mark.parametrize(
    "code", ["authentication", "invalid_response", "timeout", "quota", "unavailable"]
)
@pytest.mark.parametrize("operation", ["check", "generate"])
def test_other_failures_do_not_fallback(code, operation):
    error = LLMError(code)
    primary, local = Provider("primary"), Provider("local")
    if operation == "check":
        primary.check_error = error
    else:
        primary.generate_error = error
    llm = RateLimitFallbackLLM(primary, local)
    with pytest.raises(LLMError) as caught:
        if operation == "check":
            run(llm.check_model())
        else:
            generate(llm)
    assert caught.value is error
    assert local.checks == 0
    assert local.prompts == []


def test_local_unavailable_prevents_sending_prompt():
    error = LLMError("model_unavailable")
    primary = Provider("primary", generate_error=LLMError("rate_limit"))
    local = Provider("local", check_error=error)
    llm = RateLimitFallbackLLM(primary, local)
    with pytest.raises(LLMError) as caught:
        generate(llm)
    assert caught.value is error
    assert local.prompts == []


def test_local_generation_error_is_visible():
    error = LLMError("incomplete_response")
    primary = Provider("primary", generate_error=LLMError("rate_limit"))
    local = Provider("local", generate_error=error)
    llm = RateLimitFallbackLLM(primary, local)
    with pytest.raises(LLMError) as caught:
        generate(llm)
    assert caught.value is error


@pytest.mark.parametrize("fails", ["none", "primary", "local", "both"])
def test_close_always_closes_both(fails):
    primary, local = Provider("primary"), Provider("local")
    if fails in ("primary", "both"):
        primary.close_error = RuntimeError("primary")
    if fails in ("local", "both"):
        local.close_error = RuntimeError("local")
    llm = RateLimitFallbackLLM(primary, local)
    if fails == "none":
        run(llm.aclose())
    else:
        with pytest.raises(RuntimeError):
            run(llm.aclose())
    assert primary.closes == local.closes == 1
