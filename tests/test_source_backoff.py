"""Source backoff is bounded, independent of network and real waiting."""

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from prepa.task_bank.reshai import BASE, ReshaiError, ReshaiSource


@pytest.mark.parametrize("status", [429, 502, 503])
def test_temporary_response_retries_then_caches(tmp_path, monkeypatch, status):
    sleep = AsyncMock()
    monkeypatch.setattr("prepa.task_bank.reshai.asyncio.sleep", sleep)
    replies = iter([status, 200])
    calls = []

    def handle(request):
        calls.append(request.url)
        code = next(replies)
        return httpx.Response(
            code,
            headers={"content-type": "text/html", "retry-after": "99"},
            content=b"<html>source</html>",
        )

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            source = ReshaiSource(http=http, cache_dir=tmp_path, request_interval=0)
            assert await source._fetch(BASE + "physics.kinematics") == b"<html>source</html>"
            assert await source._fetch(BASE + "physics.kinematics") == b"<html>source</html>"
            assert source._calls == 2

    asyncio.run(check())
    assert len(calls) == 2
    assert [call.args[0] for call in sleep.await_args_list] == [0, 5, 0]


@pytest.mark.parametrize(
    "retry_after, expected",
    [("0", 0), ("2.5", 2.5), ("bad", 1), ("nan", 1), ("inf", 1), ("-1", 1)],
)
def test_retry_after_values(tmp_path, monkeypatch, retry_after, expected):
    sleep = AsyncMock()
    monkeypatch.setattr("prepa.task_bank.reshai.asyncio.sleep", sleep)
    replies = iter([429, 200])

    def handle(request):
        return httpx.Response(
            next(replies),
            headers={"content-type": "text/html", "retry-after": retry_after},
            content=b"ok",
        )

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            source = ReshaiSource(http=http, cache_dir=tmp_path, request_interval=0)
            assert await source._fetch(BASE + "physics.kinematics") == b"ok"

    asyncio.run(check())
    assert [call.args[0] for call in sleep.await_args_list] == [0, expected, 0]


def test_http_date_is_clamped(tmp_path, monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr("prepa.task_bank.reshai.asyncio.sleep", sleep)
    replies = iter([503, 200])

    def handle(request):
        return httpx.Response(
            next(replies),
            headers={
                "content-type": "text/html",
                "retry-after": "Wed, 21 Oct 2099 07:28:00 GMT",
            },
            content=b"ok",
        )

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            await ReshaiSource(http=http, cache_dir=tmp_path, request_interval=0)._fetch(
                BASE + "physics.kinematics"
            )

    asyncio.run(check())
    assert [call.args[0] for call in sleep.await_args_list] == [0, 5, 0]


@pytest.mark.parametrize("status, expected_calls", [(429, 3), (502, 3), (503, 3), (404, 1)])
def test_retry_limit_and_permanent_failure(tmp_path, monkeypatch, status, expected_calls):
    sleep = AsyncMock()
    monkeypatch.setattr("prepa.task_bank.reshai.asyncio.sleep", sleep)
    calls = []

    def handle(request):
        calls.append(request.url)
        return httpx.Response(status)

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            source = ReshaiSource(http=http, cache_dir=tmp_path, request_interval=0)
            with pytest.raises(ReshaiError, match="unavailable"):
                await source._fetch(BASE + "physics.kinematics")
            assert source._calls == expected_calls

    asyncio.run(check())
    assert len(calls) == expected_calls
    assert not list(tmp_path.glob("*.bin"))
    pauses = [call.args[0] for call in sleep.await_args_list if call.args[0] > 0]
    assert pauses == ([1, 2] if expected_calls == 3 else [])


def test_retries_obey_total_call_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("prepa.task_bank.reshai.asyncio.sleep", AsyncMock())
    calls = []

    def handle(request):
        calls.append(request.url)
        return httpx.Response(429)

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            source = ReshaiSource(http=http, cache_dir=tmp_path, request_interval=0)
            source._calls = 219
            with pytest.raises(ReshaiError, match="request limit"):
                await source._fetch(BASE + "physics.kinematics")
            assert source._calls == 220

    asyncio.run(check())
    assert len(calls) == 1


def test_different_temporary_errors_then_success(tmp_path, monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr("prepa.task_bank.reshai.asyncio.sleep", sleep)
    statuses = iter([429, 503, 200])

    def handle(request):
        return httpx.Response(next(statuses), headers={"content-type": "text/html"}, content=b"ok")

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            source = ReshaiSource(http=http, cache_dir=tmp_path, request_interval=0)
            assert await source._fetch(BASE + "physics.kinematics") == b"ok"
            assert source._calls == 3

    asyncio.run(check())
    assert [call.args[0] for call in sleep.await_args_list] == [0, 1, 0, 2, 0]
