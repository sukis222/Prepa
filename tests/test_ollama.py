"""Local Ollama wire contract and sanitized failures without a running server."""

import asyncio
import json

import httpx
import pytest

from prepa.llm import LLMError
from prepa.llm.ollama import OllamaLLM, OllamaSettings


def run(coro):
    return asyncio.run(coro)


def client(handler):
    return OllamaLLM(
        OllamaSettings(), http=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )


def reply(**updates):
    return {
        "done": True,
        "done_reason": "stop",
        "message": {"role": "assistant", "content": '{"task_ids":["a"]}'},
        **updates,
    }


def test_local_wire_contract_and_close():
    paths = []
    schema = {"type": "object", "properties": {"task_ids": {"type": "array"}}}

    def handler(request):
        assert str(request.url).startswith("http://127.0.0.1:11434/api/")
        assert "authorization" not in request.headers
        paths.append(request.url.path)
        body = json.loads(request.content)
        if request.url.path == "/api/show":
            assert body == {"model": "qwen3:8b"}
            return httpx.Response(200, json={"capabilities": ["completion", "thinking"]})
        assert body["format"] == schema
        assert body["think"] is False
        assert body["stream"] is False
        assert body["options"] == {"temperature": 0.2, "num_predict": 4096, "num_ctx": 16384}
        assert body["messages"][0]["content"].startswith("s\n")
        assert body["messages"][1] == {"role": "user", "content": "u"}
        return httpx.Response(200, json=reply())

    llm = client(handler)
    run(llm.check_model())
    assert run(llm.generate(system_prompt="s", user_prompt="u", response_schema=schema)) == {
        "task_ids": ["a"]
    }
    run(llm.aclose())
    assert paths == ["/api/show", "/api/chat"]
    assert llm.http.is_closed


@pytest.mark.parametrize(
    "updates,code",
    [
        ({"done": False}, "incomplete_response"),
        ({"done_reason": "length"}, "incomplete_response"),
        ({"message": {"role": "assistant", "content": "bad"}}, "invalid_response"),
        ({"message": {"role": "assistant", "content": "[]"}}, "invalid_response"),
        ({"message": {"role": "assistant", "content": "x" * 200001}}, "invalid_response"),
        ({"message": {"role": "user", "content": "{}"}}, "invalid_response"),
        ({"message": None}, "invalid_response"),
        ({"message": {}}, "invalid_response"),
    ],
)
def test_invalid_generation(updates, code):
    llm = client(lambda _: httpx.Response(200, json=reply(**updates)))
    with pytest.raises(LLMError, match=code):
        run(llm.generate(system_prompt="s", user_prompt="u", response_schema={}))


@pytest.mark.parametrize(
    "response,code",
    [
        (httpx.Response(404), "model_unavailable"),
        (httpx.Response(400), "invalid_request"),
        (httpx.Response(429), "rate_limit"),
        (httpx.Response(500, text="private prompt"), "provider_unavailable"),
        (httpx.Response(307, headers={"location": "https://example.com"}), "provider_unavailable"),
        (httpx.Response(200, content=b"x" * 1000001), "response_too_large"),
        (httpx.Response(200, text="not json"), "invalid_response"),
        (httpx.Response(200, json=[]), "invalid_response"),
        (httpx.Response(200, json={"error": "private prompt"}), "invalid_response"),
        (httpx.Response(200, json={"capabilities": []}), "structured_outputs_unavailable"),
    ],
)
def test_provider_errors(response, code):
    llm = client(lambda _: response)
    with pytest.raises(LLMError, match=code) as error:
        run(llm.check_model())
    assert "private prompt" not in str(error.value)


@pytest.mark.parametrize(
    "error,code",
    [(httpx.ReadTimeout("secret"), "timeout"), (httpx.ConnectError("secret"), "unavailable")],
)
def test_transport_errors(error, code):
    def handler(request):
        raise error

    with pytest.raises(LLMError, match=code):
        run(client(handler).check_model())


def test_input_limit_has_no_request():
    def handler(request):
        pytest.fail("oversized input must not reach the server")

    with pytest.raises(LLMError, match="input_too_large"):
        run(
            client(handler).generate(
                system_prompt="s", user_prompt="x" * 300001, response_schema={}
            )
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"model": ""},
        {"model": "two words"},
        {"model": "x" * 201},
        {"timeout_seconds": float("nan")},
        {"timeout_seconds": 121},
        {"context_tokens": True},
        {"context_tokens": 1000},
    ],
)
def test_invalid_settings(kwargs):
    with pytest.raises(ValueError):
        OllamaSettings(**kwargs)


def test_env_settings(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("OLLAMA_TIMEOUT", "90")
    monkeypatch.setenv("OLLAMA_CONTEXT", "8192")
    assert OllamaSettings.from_env() == OllamaSettings("qwen3:4b", 90, 8192)
    monkeypatch.setenv("OLLAMA_CONTEXT", "bad")
    with pytest.raises(ValueError, match="Некорректные"):
        OllamaSettings.from_env()


def test_default_http_client_ignores_proxy_environment(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "https://example.com")
    llm = OllamaLLM(OllamaSettings())
    assert llm.http.follow_redirects is False
    assert llm.http._trust_env is False
    run(llm.aclose())
