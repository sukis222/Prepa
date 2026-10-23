"""Provider wire contract and failures, offline; no paid/free API requests."""

import asyncio
import json

import httpx
import pytest

from prepa.llm import LLMError, OpenRouterLLM, OpenRouterSettings
from prepa.llm.openrouter import DEFAULT_MODEL


def run(coro):
    return asyncio.run(coro)


def client(handler, **kwargs):
    return OpenRouterLLM(
        OpenRouterSettings("test-secret", **kwargs),
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def catalog(**updates):
    return {
        "data": [
            {
                "id": DEFAULT_MODEL,
                "pricing": {"prompt": "0", "completion": "0"},
                "supported_parameters": ["structured_outputs", "response_format"],
                **updates,
            }
        ]
    }


def test_free_wire_contract():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/models"):
            assert "authorization" not in request.headers
            return httpx.Response(200, json=catalog())
        body = json.loads(request.content)
        assert body["model"] == DEFAULT_MODEL
        assert body["messages"][0]["content"].startswith("s\n")
        assert json.dumps({"type": "object"}) in body["messages"][0]["content"]
        assert body["messages"][1] == {"role": "user", "content": "u"}
        assert "models" not in body
        assert body["provider"] == {
            "require_parameters": True,
            "max_price": {"prompt": 0, "completion": 0},
        }
        assert body["max_tokens"] == 8192
        assert body["response_format"]["json_schema"]["schema"] == {"type": "object"}
        assert request.headers["authorization"] == "Bearer test-secret"
        return httpx.Response(
            200,
            json={"choices": [{"finish_reason": "stop", "message": {"content": '{"ok":true}'}}]},
        )

    llm = client(handler)
    run(llm.check_model())
    assert run(
        llm.generate(system_prompt="s", user_prompt="u", response_schema={"type": "object"})
    ) == {"ok": True}
    run(llm.aclose())
    assert len(requests) == 2
    assert "test-secret" not in repr(llm.settings)


@pytest.mark.parametrize(
    "updates,code",
    [
        ({"id": "removed:free"}, "model_unavailable"),
        ({"pricing": {"prompt": ".1", "completion": "0"}}, "model_not_free"),
        ({"pricing": {"prompt": "0", "completion": "0", "request": "1"}}, "model_not_free"),
        ({"pricing": {}}, "model_not_free"),
        ({"pricing": {"prompt": "NaN", "completion": "0"}}, "model_not_free"),
        ({"supported_parameters": ["response_format"]}, "structured_outputs_unavailable"),
    ],
)
def test_catalog_rejects_unavailable_paid_or_unstructured(updates, code):
    llm = client(lambda _: httpx.Response(200, json=catalog(**updates)))
    with pytest.raises(LLMError, match=code):
        run(llm.check_model())


@pytest.mark.parametrize(
    "status,code",
    [
        (400, "invalid_request"),
        (401, "authentication"),
        (402, "quota"),
        (403, "access_denied"),
        (404, "model_unavailable"),
        (429, "rate_limit"),
        (500, "unavailable"),
        (502, "provider_unavailable"),
        (503, "provider_unavailable"),
        (504, "provider_unavailable"),
    ],
)
def test_provider_errors_are_safe_no_retries(status, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="test-secret student personal text")

    llm = client(handler)
    with pytest.raises(LLMError) as error:
        run(llm.generate(system_prompt="s", user_prompt="u", response_schema={}))
    assert str(error.value) == "OpenRouter: " + code
    assert error.value.__cause__ is None
    assert len(calls) == 1


@pytest.mark.parametrize(
    "response,code",
    [
        ({"error": {"message": "secret"}}, "invalid_response"),
        ({}, "invalid_response"),
        ({"choices": []}, "invalid_response"),
        (
            {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]},
            "incomplete_response",
        ),
        (
            {"choices": [{"finish_reason": "stop", "message": {"content": "```json\n{}\n```"}}]},
            "invalid_response",
        ),
        (
            {"choices": [{"finish_reason": "stop", "message": {"content": "[]"}}]},
            "invalid_response",
        ),
        (
            {"choices": [{"finish_reason": "stop", "message": {"content": None}}]},
            "invalid_response",
        ),
    ],
)
def test_invalid_output_not_presented_as_success(response, code):
    llm = client(lambda _: httpx.Response(200, json=response))
    with pytest.raises(LLMError, match=code):
        run(llm.generate(system_prompt="s", user_prompt="u", response_schema={}))


@pytest.mark.parametrize(
    "reason,expected",
    [
        ("length", "length"),
        ("content_filter", "content_filter"),
        ("tool_calls", "tool_calls"),
        ("error", "error"),
        ("test-secret student personal text", "unknown"),
        (["test-secret"], "unknown"),
    ],
)
def test_incomplete_finish_reason_is_allowlisted_without_retry(reason, expected):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": reason,
                        "native_finish_reason": "test-secret student personal text",
                        "message": {"content": "test-secret student personal text"},
                    }
                ]
            },
        )

    with pytest.raises(LLMError) as error:
        run(client(handler).generate(system_prompt="s", user_prompt="u", response_schema={}))
    assert error.value.code == "incomplete_response"
    assert error.value.finish_reason == expected
    assert str(error.value) == "OpenRouter: incomplete_response"
    assert "test-secret" not in repr(vars(error.value))
    assert len(calls) == 1


def test_non_completion_error_has_no_finish_reason():
    assert LLMError("timeout").finish_reason is None


@pytest.mark.parametrize(
    "error,code",
    [(httpx.ReadTimeout("secret"), "timeout"), (httpx.ConnectError("secret"), "unavailable")],
)
def test_network_error_sanitized(error, code):
    def handler(_):
        raise error

    with pytest.raises(LLMError, match=code):
        run(client(handler).check_model())


def test_size_and_json_limits():
    for response, code in [
        (httpx.Response(200, text="x" * 1_000_001), "response_too_large"),
        (httpx.Response(200, text="secret"), "invalid_response"),
        (httpx.Response(200, json=[]), "invalid_response"),
    ]:
        with pytest.raises(LLMError, match=code):
            run(
                client(lambda _, r=response: r).generate(
                    system_prompt="s", user_prompt="u", response_schema={}
                )
            )
    llm = client(lambda _: pytest.fail("HTTP must not be called"))
    with pytest.raises(LLMError, match="input_too_large"):
        run(llm.generate(system_prompt="x" * 300_001, user_prompt="", response_schema={}))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"api_key": ""},
        {"model": "paid/model"},
        {"timeout_seconds": 0},
        {"timeout_seconds": float("nan")},
        {"timeout_seconds": 120.01},
        {"max_tokens": 0},
        {"max_tokens": 1.5},
    ],
)
def test_bad_configuration(kwargs):
    with pytest.raises(ValueError):
        OpenRouterSettings(**{"api_key": "hidden", **kwargs})


def test_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "hidden")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_MODEL", "")
    assert OpenRouterSettings.from_env().model == DEFAULT_MODEL
    monkeypatch.setenv("OPENROUTER_TIMEOUT_SECONDS", "120")
    assert OpenRouterSettings.from_env().timeout_seconds == 120
    monkeypatch.setenv("OPENROUTER_TIMEOUT_SECONDS", "bad")
    with pytest.raises(ValueError, match="лимиты"):
        OpenRouterSettings.from_env()
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://other.example/api/v1")
    with pytest.raises(ValueError, match="официальный"):
        OpenRouterSettings.from_env()


def test_120_second_timeout_reaches_http_transport():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.extensions["timeout"]["read"] == 120
        return httpx.Response(200, json=catalog())

    llm = client(handler, timeout_seconds=120)
    run(llm.check_model())
    assert len(calls) == 1


def test_default_http_timeout_is_120_seconds(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "hidden")
    monkeypatch.delenv("OPENROUTER_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    assert OpenRouterSettings("hidden").timeout_seconds == 120
    assert OpenRouterSettings.from_env().timeout_seconds == 120


def test_reasoning_off_is_explicit_and_supported(monkeypatch):
    body = {}

    def handler(request):
        nonlocal body
        if request.url.path.endswith("/models"):
            return httpx.Response(
                200,
                json=catalog(
                    supported_parameters=["reasoning", "structured_outputs", "response_format"],
                    reasoning={"mandatory": False},
                ),
            )
        body = json.loads(request.content)
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}
        )

    llm = client(handler, reasoning="off")
    run(llm.check_model())
    run(llm.generate(system_prompt="s", user_prompt="u", response_schema={}))
    assert body["reasoning"] == {"enabled": False}
    for updates in [
        {},
        {
            "supported_parameters": ["reasoning", "structured_outputs", "response_format"],
            "reasoning": {"mandatory": True},
        },
    ]:
        with pytest.raises(LLMError, match="reasoning_configuration_unavailable"):
            run(
                client(
                    lambda _, u=updates: httpx.Response(200, json=catalog(**u)), reasoning="off"
                ).check_model()
            )
    with pytest.raises(ValueError, match="REASONING"):
        OpenRouterSettings("hidden", reasoning="invented")
    monkeypatch.setenv("OPENROUTER_API_KEY", "hidden")
    monkeypatch.setenv("OPENROUTER_REASONING", "off")
    assert OpenRouterSettings.from_env().reasoning == "off"
