"""Official FIPI source selection, provenance and fail-closed PDF checks; no network."""

import asyncio
import hashlib
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from prepa.agents.runtime import InsufficientMaterialsError
from prepa.preparation.real import FipiMaterials
from prepa.schemas import LessonBrief
from prepa.task_bank import TaskSourceError
from prepa.task_bank.official import (
    DOCUMENTS,
    MAX_PDF_BYTES,
    MaintenanceNotice,
    OfficialDocument,
    OfficialNavigatorMaterials,
    extract_verified,
    maintenance_for_exam,
    parse_maintenance,
    supported_topic,
)


def run(coro):
    return asyncio.run(coro)


def brief(context, exam="ege", topic="Равномерное прямолинейное движение"):
    return LessonBrief.model_validate(
        {
            **context.brief.model_dump(),
            "exam": exam,
            "topics": [topic],
        }
    )


def notice():
    return MaintenanceNotice(date(2026, 10, 22), date(2026, 10, 27), "https://fipi.ru")


def test_current_announcement_parser():
    html = (
        "<p>Сообщаем, что с <b>22.10.2026</b> по 27.10.2026 будут проводиться "
        "профилактические работы.</p><p>Открытые банки в данный период "
        "времени будут недоступны.</p>"
    )
    parsed = parse_maintenance(html, "ege")
    assert parsed and parsed.start == date(2026, 10, 22)
    assert parsed.end == date(2026, 10, 27)
    assert parsed.active(date(2026, 10, 22))
    assert parsed.active(date(2026, 10, 27))
    assert not parsed.active(date(2026, 10, 28))
    assert not parsed.active(date(2026, 10, 21))
    assert parsed.page_url.startswith("https://fipi.ru/ege/")
    for invalid in [
        "",
        "Сайт работает",
        html.replace("27.10.2026", "01.10.2026"),
        html.replace("22.10.2026", "32.10.2026"),
        html.replace("22.10.2026", "22/10/2026"),
    ]:
        assert parse_maintenance(invalid, "ege") is None


def test_topics_are_narrow_exam_specific():
    for exam, code in [("ege", "1.1.5"), ("oge", "1.3")]:
        assert supported_topic(exam, code)
        assert supported_topic(exam, " Равномерное   ПРЯМОЛИНЕЙНОЕ движение ")
        assert supported_topic(exam, "Равномерное движение")
    assert not supported_topic("oge", "1.1.5")
    for topic in ["Кинематика", "Ядерные реакции", "Равномерное движение по окружности", "1.1.6"]:
        assert not supported_topic("ege", topic)


@pytest.mark.parametrize("exam", ["oge", "ege"])
def test_downloaded_source_is_cited_and_never_bank_or_demo(context, monkeypatch, exam):
    calls = []
    document = DOCUMENTS[exam]

    def handler(request):
        calls.append(request)
        assert str(request.url) == document.url
        assert request.url.host == "doc.fipi.ru"
        assert "authorization" not in request.headers
        return httpx.Response(
            200, content=b"verified-original", headers={"content-type": "application/pdf"}
        )

    def extract(data, spec):
        assert data == b"verified-original" and spec == document
        return "Проверенная расшифровка реального навигатора"

    monkeypatch.setattr("prepa.task_bank.official.extract_verified", extract)
    source = OfficialNavigatorMaterials(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    materials = run(source.materials(brief(context, exam)))
    assert len(materials) == 1
    material = materials[0]
    assert material.source == f"{document.url}#page={document.page}"
    assert material.exam == exam
    assert material.material_id.startswith("fipi-navigator-")
    assert "навигатор" in material.title
    assert "demo" not in material.material_id
    assert len(calls) == 1


def test_unsupported_query_does_not_download(context):
    source = OfficialNavigatorMaterials(
        httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: pytest.fail("No download for unrelated topic"))
        )
    )
    with pytest.raises(InsufficientMaterialsError) as error:
        run(source.materials(brief(context, topic="Квантовая физика")))
    assert error.value.failure.missing_topics == ("Квантовая физика",)


def test_pdf_hash_topic_and_parser_fail_closed(monkeypatch):
    data = b"controlled-pdf-bytes"
    spec = OfficialDocument(
        "https://doc.fipi.ru/example.pdf", hashlib.sha256(data).hexdigest(), 1, "x(t)=x0+v*t"
    )
    page = SimpleNamespace(
        extract_text=lambda: "Равномерное прямолинейное движение: formula\n1 На сайте"
    )
    monkeypatch.setattr(
        "prepa.task_bank.official.PdfReader", lambda *args, **kwargs: SimpleNamespace(pages=[page])
    )
    result = extract_verified(data, spec)
    assert "x(t)=x0+v*t" in result and "Страница PDF: 1" in result
    with pytest.raises(TaskSourceError, match="changed"):
        extract_verified(b"different-pdf", spec)
    with pytest.raises(TaskSourceError, match="changed"):
        extract_verified(b"x" * (MAX_PDF_BYTES + 1), spec)
    page.extract_text = lambda: "Wrong topic"
    with pytest.raises(TaskSourceError, match="missing"):
        extract_verified(data, spec)
    page.extract_text = lambda: "Равномерное прямолинейное движение" + "x" * 3000
    with pytest.raises(TaskSourceError, match="layout"):
        extract_verified(data, spec)
    monkeypatch.setattr(
        "prepa.task_bank.official.PdfReader",
        lambda *a, **kw: (_ for _ in ()).throw(ValueError("private")),
    )
    with pytest.raises(TaskSourceError, match="cannot be read"):
        extract_verified(data, spec)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503),
        httpx.Response(302, headers={"location": "https://unrelated.example"}),
        httpx.Response(200, content=b"Not PDF", headers={"content-type": "text/html"}),
        httpx.Response(
            200, content=b"x" * (MAX_PDF_BYTES + 1), headers={"content-type": "application/pdf"}
        ),
    ],
)
def test_bad_downloads_not_sent_to_model(context, response):
    source = OfficialNavigatorMaterials(
        httpx.AsyncClient(transport=httpx.MockTransport(lambda _: response))
    )
    with pytest.raises(TaskSourceError):
        run(source.materials(brief(context)))


def test_network_error_sanitized(context):
    def handler(_):
        raise httpx.ConnectTimeout("hidden network detail")

    source = OfficialNavigatorMaterials(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with pytest.raises(TaskSourceError) as error:
        run(source.materials(brief(context)))
    assert "hidden" not in str(error.value)


def test_maintenance_skips_bank_and_uses_real_official_source(context, monkeypatch):
    official = AsyncMock(return_value=context.materials)
    monkeypatch.setattr(
        "prepa.preparation.real.maintenance_for_exam", AsyncMock(return_value=notice())
    )
    monkeypatch.setattr(
        "prepa.preparation.real.OfficialNavigatorMaterials",
        lambda: SimpleNamespace(materials=official),
    )

    class Today:
        @staticmethod
        def today():
            return date(2026, 10, 23)

    monkeypatch.setattr("prepa.preparation.real.date", Today)
    source = FipiMaterials()
    bank = AsyncMock()
    monkeypatch.setattr(source, "_bank_materials", bank)
    assert run(source.materials(context.brief)) == context.materials
    bank.assert_not_awaited()
    official.assert_awaited_once_with(context.brief)


def test_network_failure_falls_back_but_empty_bank_does_not(context, monkeypatch):
    monkeypatch.setattr("prepa.preparation.real.maintenance_for_exam", AsyncMock(return_value=None))
    official = AsyncMock(return_value=context.materials)
    monkeypatch.setattr(
        "prepa.preparation.real.OfficialNavigatorMaterials",
        lambda: SimpleNamespace(materials=official),
    )
    source = FipiMaterials()
    monkeypatch.setattr(
        source, "_bank_materials", AsyncMock(side_effect=TaskSourceError("offline"))
    )
    assert run(source.materials(context.brief)) == context.materials
    official.assert_awaited_once()
    official.reset_mock()
    monkeypatch.setattr(source, "_bank_materials", AsyncMock(return_value=context.materials))
    assert run(source.materials(context.brief)) == context.materials
    official.assert_not_awaited()


def test_announcement_http_nonfatal(monkeypatch):
    real_client = httpx.AsyncClient
    responses = [
        httpx.Response(503),
        httpx.Response(200, text="Ready"),
        httpx.Response(200, text="x" * 2_000_001),
    ]

    def handler(_):
        return responses.pop(0)

    monkeypatch.setattr(
        "prepa.task_bank.official.httpx.AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler)),
    )
    for _ in range(3):
        assert run(maintenance_for_exam("ege")) is None


def test_thermodynamics_request_selects_complete_verified_basis():
    from prepa.task_bank.official import THERMO_DOCUMENTS, documents_for_topic

    topic = "Термодинамика, 2 часть егэ, циклы"
    assert documents_for_topic("ege", topic) == THERMO_DOCUMENTS
    assert supported_topic("ege", "Изопроцессы и графики")
    assert supported_topic("ege", "Цикл Карно")
    assert not supported_topic("oge", topic)
    assert not supported_topic("ege", "Циклы и графики")
    assert not supported_topic("ege", "Квантовая термодинамика")
    assert {d.page for d in THERMO_DOCUMENTS} == {1, 2}
    assert len({d.url for d in THERMO_DOCUMENTS}) == 1
    assert "одноатомного" in THERMO_DOCUMENTS[0].formula
    assert "Q_12 = DeltaU_12 + A_12" in THERMO_DOCUMENTS[1].formula
    assert "abs(Q_cold)" in THERMO_DOCUMENTS[1].formula


def test_thermo_pdf_downloaded_once_and_exact_topics_kept(context, monkeypatch):
    from prepa.task_bank.official import THERMO_URL

    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(
            200, content=b"verified-pdf", headers={"content-type": "application/pdf"}
        )

    monkeypatch.setattr(
        "prepa.task_bank.official.extract_verified", lambda data, spec: spec.formula
    )
    source = OfficialNavigatorMaterials(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    topic = "Термодинамика, 2 часть егэ, циклы"
    materials = run(source.materials(brief(context, topic=topic)))
    assert calls == [THERMO_URL]
    assert len(materials) == 2
    assert len({m.material_id for m in materials}) == 2
    assert all(m.topics == (topic,) for m in materials)
    assert [m.source for m in materials] == [THERMO_URL + "#page=1", THERMO_URL + "#page=2"]


def test_mixed_motion_and_thermodynamics_do_not_misattribute_topics(context, monkeypatch):
    def handler(request):
        return httpx.Response(
            200, content=b"verified-pdf", headers={"content-type": "application/pdf"}
        )

    monkeypatch.setattr(
        "prepa.task_bank.official.extract_verified", lambda data, spec: spec.formula
    )
    source = OfficialNavigatorMaterials(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    topics = ("Равномерное движение", "Термодинамика, 2 часть егэ, циклы")
    query = LessonBrief.model_validate(
        {**context.brief.model_dump(), "exam": "ege", "topics": topics}
    )
    materials = run(source.materials(query))
    assert len(materials) == 3
    assert materials[0].topics == topics[:1]
    assert all(m.topics == topics[1:] for m in materials[1:])
