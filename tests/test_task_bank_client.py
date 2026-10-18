"""FIPI client requests, decoding and errors through httpx.MockTransport (no network)."""

import asyncio
import ssl
from collections.abc import Callable
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from prepa.task_bank import AnswerKind, FipiClient, KesTopic, TaskSourceError
from prepa.task_bank.fipi.client import PHYSICS, Page, ssl_context

FIXTURES = Path(__file__).parent / "fixtures"
Handler = Callable[[httpx.Request], httpx.Response]


def cp1251(name: str, *, charset: bool = True) -> httpx.Response:
    body = (FIXTURES / name).read_text(encoding="utf-8").encode("cp1251", errors="replace")
    content_type = "text/html; charset=windows-1251" if charset else "text/html"
    return httpx.Response(200, content=body, headers={"content-type": content_type})


def client(handler: Handler) -> FipiClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return FipiClient(http, delay_seconds=0)


def test_page_posts_bank_filter_and_decodes_windows_1251() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return cp1251("fipi_questions.html")

    async def run() -> Page:
        async with client(handler) as bank:
            return await bank.page(
                "oge",
                ["1.3", "1.4"],
                kinds=[AnswerKind.SHORT, AnswerKind.OTHER, AnswerKind.MATCHING],
                page=2,
                page_size=20,
            )

    page = asyncio.run(run())
    (request,) = seen
    assert request.method == "POST"
    assert str(request.url) == "https://oge.fipi.ru/bank/questions.php"
    form = {key: value[0] for key, value in parse_qs(request.content.decode()).items()}
    assert form == {
        "search": "1",
        "proj": PHYSICS["oge"].project,
        "theme": "1.3,1.4",
        "qkind": "ILI_STD_SHORT,ILI_EXT_ACCORD",
        "pagesize": "20",
        "page": "2",
    }
    assert page.total == 57
    first = page.tasks[0]
    assert first.exam == "oge"
    assert "Велосипедист" in first.statement
    assert first.images[0].startswith("https://oge.fipi.ru/docs/")
    assert first.url == (
        f"https://oge.fipi.ru/bank/questions.php?search=1&proj={PHYSICS['oge'].project}&qid=1A2B3C"
    )


def test_topics_are_fetched_once_per_exam_and_default_to_cp1251() -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return cp1251("fipi_index.html", charset=False)

    async def run() -> tuple[tuple[KesTopic, ...], tuple[KesTopic, ...]]:
        async with client(handler) as bank:
            first = await bank.topics("ege")
            return first, await bank.topics("ege")

    first, second = asyncio.run(run())
    assert first is second
    assert urls == [f"https://ege.fipi.ru/bank/index.php?proj={PHYSICS['ege'].project}"]
    assert first[3].title == "Равномерное прямолинейное движение"


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(503, text="maintenance"),
        lambda request: (_ for _ in ()).throw(httpx.ConnectError("offline", request=request)),
    ],
)
def test_transport_and_http_failures_become_task_source_errors(handler: Handler) -> None:
    async def run() -> None:
        async with client(handler) as bank:
            await bank.page("ege", ["1.1"])

    with pytest.raises(TaskSourceError, match="FIPI"):
        asyncio.run(run())


@pytest.mark.parametrize(("page", "size"), [(-1, 10), (0, 0), (0, 51)])
def test_page_arguments_are_validated_before_any_request(page: int, size: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    async def run() -> None:
        async with client(handler) as bank:
            await bank.page("ege", ["1.1"], page=page, page_size=size)

    with pytest.raises(ValueError, match="page"):
        asyncio.run(run())


def test_default_client_verifies_tls_with_the_bundled_intermediate() -> None:
    context = ssl_context()
    assert context.verify_mode is ssl.CERT_REQUIRED
    assert context.check_hostname
    names = [dict(item[0] for item in cert["subject"]) for cert in context.get_ca_certs()]
    assert any(name.get("commonName") == "GlobalSign GCC R3 DV TLS CA 2020" for name in names)

    async def run() -> None:
        bank = FipiClient()
        assert bank.http.headers["user-agent"].startswith("Prepa/")
        await bank.aclose()

    asyncio.run(run())
