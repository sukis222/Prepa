"""Published explanations are optional, bounded, and never manufactured from answers."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from prepa.schemas.source import SourceTask, TaskWorksheet, source_task_digest
from prepa.task_bank.reshai import ReshaiError, ReshaiSource
from prepa.task_bank.solutions import enrich_solutions, fetch_solution, parse_solution


def task(text="Газ при 80 градусах", url="https://reshai.online/ege/subjects/physics/tasks/ABC123"):
    return SourceTask(
        id="abc", statement_exact=text, source_url=url, sha256=source_task_digest(text)
    )


def html(recap="Газ при 80 градусах", step="Применим закон $Q=A+U$", extra=""):
    return (
        f'<div class="recap"><div class="statement">{recap}</div></div>'
        '<div class="steps"><section class="step"><div class="dot">1</div>'
        f'<p>{step}</p><span class="wmk">HIDDEN</span></section></div>'
        f'<div class="answer-final"><div class="long">10</div></div>{extra}'
    )


def sheet():
    return TaskWorksheet(
        preparation_id="test",
        version=1,
        student_ids=("student",),
        exam="ege",
        topics=("Газ",),
        title="Газ",
        tasks=(task(),),
    )


def test_parser_keeps_steps_and_math_only():
    result = parse_solution(html(extra='<div class="hint">SECRET HINT</div>'), task())
    assert result == ("Применим закон $Q=A+U$\nОтвет: 10", ())


@pytest.mark.parametrize(
    "body",
    [
        "<div class='answer-final'>10</div>",
        html(recap="Газ при 90 градусах"),
        html(extra='<link rel="canonical" href="https://evil.test">'),
        html(step=""),
    ],
)
def test_incomplete_or_mismatched_solution_rejected(body):
    assert parse_solution(body, task()) is None


def test_decimal_latex_correspondence_and_image():
    body = html(recap="Газ $8{,}31$", step='<img src="/media/task/x/0.png"> Закон')
    result = parse_solution(body, task("Газ 8,31"))
    assert result and result[1] == ("https://reshai.online/media/task/x/0.png",)


def test_fetch_and_untrusted_url():
    source = ReshaiSource()
    source._fetch = AsyncMock(return_value=html().encode())
    result = asyncio.run(fetch_solution(task(), source))
    assert result.solution and result.solution.sha256 == source_task_digest(result.solution.text)
    source._fetch.assert_awaited_once()
    source._fetch.reset_mock()
    assert (
        asyncio.run(fetch_solution(task(url="https://evil.test/ABC123"), source)).solution is None
    )
    source._fetch.assert_not_awaited()


@pytest.mark.parametrize(
    "response", [b"\xff", b"<html>no solution</html>", ReshaiError("Unavailable")]
)
def test_fetch_failure_optional(response):
    source = ReshaiSource()
    source._fetch = AsyncMock(
        **(
            {"side_effect": response}
            if isinstance(response, Exception)
            else {"return_value": response}
        )
    )
    assert asyncio.run(fetch_solution(task(), source)).solution is None


def test_enrichment_and_timeout():
    source = ReshaiSource(http=AsyncMock())
    source._fetch = AsyncMock(return_value=html().encode())
    enriched = asyncio.run(enrich_solutions(sheet(), source))
    assert enriched.tasks[0].solution

    async def slow(*args):
        await asyncio.sleep(1)
        return html().encode()

    source._fetch = slow
    unchanged = asyncio.run(enrich_solutions(sheet(), source, budget_seconds=0.001))
    assert unchanged.tasks[0].solution is None


def test_figure_placeholder_not_a_physical_number():
    assert parse_solution(html(), task("[рисунок 1] Газ при 80 градусах"))


def test_enrichment_creates_http_client_when_missing(monkeypatch):
    from unittest.mock import patch

    import httpx

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, text=html(), headers={"content-type": "text/html"})
        )
    )
    with patch("prepa.task_bank.solutions.httpx.AsyncClient", return_value=client):
        enriched = asyncio.run(enrich_solutions(sheet(), ReshaiSource(cache_seconds=0)))
    assert enriched.tasks[0].solution
