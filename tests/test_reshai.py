"""Offline checks for bounded original-condition retrieval and source identity."""

import asyncio
import base64
import io
import json
from unittest.mock import AsyncMock

import httpx
import pytest
from PIL import Image

from prepa.preparation.source import SourceCorpusError, SourceSelectionBackend
from prepa.schemas import LessonBrief
from prepa.task_bank.reshai import (
    BASE,
    ListingTask,
    ReshaiError,
    ReshaiSource,
    image_snapshot,
    original_condition,
    parse_listing,
    resolve_topics,
)


def run(coro):
    return asyncio.run(coro)


def card(code="ABC123", text="Газ совершает цикл", extended=True):
    mark = "Развёрнутое решение" if extended else "Ответ"
    return (
        f'<article class="tk"><span class="tk-code">ФИПИ {code}</span>'
        '<div class="tk-top"><a href="/numbers/24">№ 24</a></div>'
        f'<div class="tk-text">{text}</div><p>{mark}</p></article>'
    )


def condition(text="Газ совершает цикл", image=False):
    asset = '<img src="/media/task/test/original/0.gif">' if image else ""
    return (
        '<p>SECRET ANSWER</p><details class="origin-task"><div class="o-body">'
        f"<p>{text}</p><math><mi>p</mi><mo>=</mo><mn>2</mn></math>"
        f"{asset}<script>bad</script></div></details>"
    )


def picture(format="GIF"):
    b = io.BytesIO()
    Image.new("RGB", (20, 12), "green").save(b, format=format)
    return b.getvalue()


def brief(context, **changes):
    return LessonBrief.model_validate(
        {
            **context.brief.model_dump(),
            "topics": ["Термодинамика"],
            "lesson_task_count": 1,
            "homework_task_count": 0,
            "homework_minutes": 0,
            **changes,
        }
    )


@pytest.mark.parametrize(
    "topic,slug",
    [
        ("Кинетическая энергия", "energy-and-momentum"),
        ("Гидростатика", "fluids-and-pressure"),
        ("Звук", "oscillations-and-waves"),
        ("Электрическое поле", "electrostatics-and-capacitors"),
        ("Температура", "molecular-physics"),
        ("Теплопередача", "phase-transitions-and-heat-engines"),
        ("Статика", "dynamics-and-gravitation"),
    ],
)
def test_topic_aliases(topic, slug):
    assert slug in resolve_topics(topic)
    assert resolve_topics("Термодинамика") == ("thermodynamics",)
    assert resolve_topics("Внутренняя энергия") == ("thermodynamics",)
    assert resolve_topics("Кинетическая энергия молекул") == ("molecular-physics",)


def test_parse_only_original_and_math_images():
    text, urls = original_condition(
        condition(image=True), "https://reshai.online/ege/subjects/physics/tasks/ABC123"
    )
    assert "SECRET" not in text and "bad" not in text
    assert "$p=2$" in text and "[рисунок 1]" in text
    assert urls == ("https://reshai.online/media/task/test/original/0.gif",)
    tasks, pages = parse_listing(card() + '<a href="?page=4">4</a>')
    assert tasks == (ListingTask("ABC123", "Газ совершает цикл", True, 24),)
    assert pages == 4
    with pytest.raises(ReshaiError):
        parse_listing("login")
    with pytest.raises(ReshaiError):
        original_condition("<p>answer</p>", "https://reshai.online")
    with pytest.raises(ReshaiError):
        resolve_topics("Неизвестная тема")


def test_png_pixel_identity_and_invalid_images():
    original = picture()
    snap = image_snapshot(original)
    with (
        Image.open(io.BytesIO(original)) as a,
        Image.open(io.BytesIO(base64.b64decode(snap.data_base64))) as b,
    ):
        assert a.convert("RGB").tobytes() == b.convert("RGB").tobytes()
        assert b.format == "PNG" and b.size == (20, 12)
    for data in (b"", b"notimage", b"a" * 3_000_001):
        with pytest.raises(ReshaiError):
            image_snapshot(data)


def test_fetch_cache_integrity_expiry_and_url_guard(tmp_path):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, text=card(), headers={"content-type": "text/html"})

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            s = ReshaiSource(http=http, cache_dir=tmp_path, request_interval=0)
            assert await s._fetch(BASE + "physics.thermodynamics") == await s._fetch(
                BASE + "physics.thermodynamics"
            )
            assert len(calls) == 1
            next(tmp_path.glob("*.bin")).write_bytes(b"corrupt")
            await s._fetch(BASE + "physics.thermodynamics")
            assert len(calls) == 2
            meta = next(tmp_path.glob("*.json"))
            obj = json.loads(meta.read_text())
            obj["stored_at"] = 0
            meta.write_text(json.dumps(obj))
            await s._fetch(BASE + "physics.thermodynamics")
            assert len(calls) == 3
            for url in (
                "https://evil.test/x",
                "http://reshai.online" + BASE + "ABC123",
                "https://reshai.online/search",
            ):
                with pytest.raises(ReshaiError):
                    await s._fetch(url)
            s._calls = 220
            with pytest.raises(ReshaiError):
                await s._fetch(BASE + "ABC999")

    run(check())


@pytest.mark.parametrize(
    "status,mime,data",
    [
        (503, "text/html", b"error"),
        (200, "application/json", b"{}"),
        (200, "text/html", b"a" * 2_000_001),
    ],
)
def test_fetch_rejects_http_mime_and_size(tmp_path, status, mime, data):
    async def check():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(status, content=data, headers={"content-type": mime})
            )
        ) as http:
            with pytest.raises(ReshaiError):
                await ReshaiSource(http=http, cache_dir=tmp_path, request_interval=0)._fetch(
                    BASE + "ABC123"
                )

    run(check())


def test_source_filters_cycles_part_two_and_duplicates(tmp_path, context):
    cards = (
        card()
        + card("ABC124", extended=False)
        + card("ABC125", text="Нагрев газа")
        + card("ABC126")
    )

    def handler(request):
        path = request.url.path
        if path.startswith("/media/"):
            return httpx.Response(200, content=picture(), headers={"content-type": "image/gif"})
        if path.endswith(("ABC123", "ABC126")):
            html = condition(image=True)
        else:
            html = cards
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            source = ReshaiSource(http=http, cache_dir=tmp_path, request_interval=0)
            result = await source.candidates(
                brief(context, exam="ege", topics=["Термодинамика, 2 часть ЕГЭ, циклы"])
            )
            assert len(result) == 1 and result[0][0].id == "reshai-ABC123"
            assert result[0][0].statement_math_exact == () and len(result[0][0].images) == 1
            with pytest.raises(ReshaiError):
                await source.candidates(brief(context, exam="oge"))

    run(check())


def test_source_failures_and_backend_no_fallback(tmp_path, context):
    async def check():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: (_ for _ in ()).throw(httpx.ConnectError("unsafe"))
            )
        ) as http:
            with pytest.raises(ReshaiError, match="unavailable"):
                await ReshaiSource(http=http, cache_dir=tmp_path, request_interval=0)._fetch(
                    BASE + "ABC123"
                )
        source = ReshaiSource(cache_dir=tmp_path)
        source.candidates = AsyncMock(side_effect=ReshaiError("outside data"))
        llm = AsyncMock()
        backend = SourceSelectionBackend(llm, source=source)
        with pytest.raises(SourceCorpusError, match="Remote source"):
            await backend.prepare(1, brief(context), context.students)
        llm.generate.assert_not_awaited()

    run(check())


def test_preserve_sub_sup_as_math_and_reject_tables():
    text, _ = original_condition(condition("V<sub>1</sub>, м<sup>3</sup>"), "https://reshai.online")
    assert "V${}_{1}$" in text and "м${}^{3}$" in text
    with pytest.raises(ReshaiError, match="table"):
        original_condition(
            condition("<table><tr><td>a</td><td>b</td></tr></table>"),
            "https://reshai.online",
        )


def test_cycle_ranking_before_detail_limit_and_unmentioned_preview_fallback(tmp_path, context):
    cards = "".join(card(f"{i:06X}", text="Нагрев газа") for i in range(71))
    cards += card("FFFFFE", text="Газ совершает цикл")
    fetched = []

    def handler(request):
        code = request.url.path.rsplit("/", 1)[-1]
        if code.startswith("physics."):
            html = cards + '<a href="?page=2">2</a>'
            if request.url.params.get("page") == "2":
                html = "<p>Outdated empty page</p>"
        else:
            fetched.append(code)
            text = "Газ совершает цикл " + code if code in ("FFFFFE", "000000") else "Нагрев газа"
            html = condition(text)
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            source = ReshaiSource(http=http, cache_dir=tmp_path, request_interval=0)
            result = await source.candidates(
                brief(context, exam="ege", topics=["Циклы, 2 часть ЕГЭ"])
            )
        assert fetched[0] == "FFFFFE"
        assert {task.id for task, _ in result} == {"reshai-FFFFFE", "reshai-000000"}
        assert len(fetched) <= 70

    run(check())
