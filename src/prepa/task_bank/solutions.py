"""Copy published Reshai explanations; missing or mismatched solutions stay missing."""

import asyncio
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from prepa.schemas.source import SourceSolution, SourceTask, TaskWorksheet, source_task_digest
from prepa.task_bank.fipi.parser import flatten
from prepa.task_bank.reshai import BASE, ORIGIN, ReshaiError, ReshaiSource


def _numbers(text: str) -> set[str]:
    text = re.sub(r"\[рисунок\s+\d+\]", "", text, flags=re.I)
    text = re.sub(r"\[рисунок \d+\]", "", text)
    text = text.replace("{,}", ",").replace("{.}", ".")
    return set(re.findall(r"\d+(?:[.,]\d+)?", text.replace(",", ".")))


def parse_solution(html: str, task: SourceTask) -> tuple[str, tuple[str, ...]] | None:
    """Only the explicit worked steps, never hints, advertising, or answer alone.

    Numeric correspondence is a conservative mismatch guard, not a physics review.
    The site's explanation is distinct from the original FIPI condition.
    """
    soup = BeautifulSoup(html, "html.parser")
    recap = soup.select_one(".recap .statement")
    steps = soup.select_one(".steps")
    if recap is None or steps is None or not steps.select(".step"):
        return None
    canonical = soup.select_one('link[rel="canonical"][href]')
    if canonical is not None and str(canonical["href"]).rstrip("/") != (
        task.source_url.rstrip("/") + "/solution"
    ):
        return None
    for hidden in soup.select("script, style, .wmk, .dot"):
        hidden.decompose()
    recap_text = flatten(recap, task.source_url, [])
    if not _numbers(task.statement_exact).issubset(_numbers(recap_text)):
        return None
    # Preserve the source's steps and optional final answer, excluding surrounding UI.
    images: list[str] = []
    text = flatten(steps, task.source_url, images)
    if not text.strip():
        return None
    answer = soup.select_one(".answer-final .long")
    if answer is not None:
        text += "\nОтвет: " + flatten(answer, task.source_url, images)
    if not text.strip() or len(text) > 30_000 or len(set(images)) > 8:
        return None
    return text, tuple(dict.fromkeys(images))


async def fetch_solution(task: SourceTask, source: ReshaiSource) -> SourceTask:
    """Enrich one selected task, retaining an explicit empty solution on source failure."""
    parsed = urlparse(task.source_url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "reshai.online"
        or not re.fullmatch(re.escape(BASE) + r"[A-Fa-f0-9]{6}", parsed.path)
        or parsed.query
        or parsed.fragment
    ):
        return task
    url = ORIGIN + parsed.path + "/solution"
    try:
        html = (await source._fetch(url)).decode("utf-8")
        extracted = parse_solution(html, task)
        if extracted is None:
            return task
        text, urls = extracted
        images = tuple(await asyncio.gather(*(source._image(u) for u in urls)))
        solution = SourceSolution(
            text=text, source_url=url, images=images, sha256=source_task_digest(text)
        )
        return SourceTask.model_validate({**task.model_dump(), "solution": solution})
    except (ReshaiError, ValueError):
        return task


async def enrich_solutions(
    worksheet: TaskWorksheet, source: ReshaiSource, *, budget_seconds: float = 25
) -> TaskWorksheet:
    """Bounded optional enrichment of selected tasks only; completed results survive timeout."""
    if source.http is None:
        async with httpx.AsyncClient(
            headers={"User-Agent": "Prepa/0.1 educational worksheet"}
        ) as http:
            return await enrich_solutions(
                worksheet,
                ReshaiSource(
                    cache_dir=source.cache_dir,
                    http=http,
                    cache_seconds=source.cache_seconds,
                    request_interval=source.interval,
                ),
                budget_seconds=budget_seconds,
            )
    pending = [asyncio.create_task(fetch_solution(t, source)) for t in worksheet.tasks]
    try:
        await asyncio.wait(pending, timeout=budget_seconds)
    finally:
        unfinished = [job for job in pending if not job.done()]
        for job in unfinished:
            job.cancel()
        await asyncio.gather(*unfinished, return_exceptions=True)
    tasks = [
        original if job.cancelled() else job.result()
        for original, job in zip(worksheet.tasks, pending, strict=True)
    ]
    return TaskWorksheet.model_validate({**worksheet.model_dump(), "tasks": tasks})
