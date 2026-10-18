"""Topic resolution and task search on top of a bank client."""

import math
import random
import re
from collections.abc import Callable, Iterable, Sequence
from typing import Protocol

from .fipi.client import MAX_PAGE_SIZE, Page
from .models import AnswerKind, BankTask, Exam, KesTopic, SearchResult

CODE = re.compile(r"^\d+(\.\d+){0,2}$")
WORD = re.compile(r"[0-9a-zа-я]+")
STEM_LENGTH = 6


class TaskBank(Protocol):
    async def topics(self, exam: Exam) -> tuple[KesTopic, ...]: ...

    async def page(
        self,
        exam: Exam,
        codes: Iterable[str],
        *,
        kinds: Iterable[AnswerKind] = (),
        page: int = 0,
        page_size: int = MAX_PAGE_SIZE,
    ) -> Page: ...


class UnknownTopicError(LookupError):
    def __init__(self, exam: Exam, query: str) -> None:
        self.exam = exam
        self.query = query
        super().__init__(f"no {exam.upper()} КЭС topic matches {query!r}")


def words(text: str) -> list[str]:
    found = WORD.findall(text.lower().replace("ё", "е"))
    return [word for word in found if len(word) > 2 or word.isdigit()]


def stems(text: str) -> set[str]:
    return {word[:STEM_LENGTH] for word in words(text)}


def match_topics(catalog: Sequence[KesTopic], query: str) -> tuple[KesTopic, ...]:
    """A code selects itself; text is matched in tiers and the first non-empty tier wins:
    the whole title, all query words as words, all query word stems (crude prefixes).

    Every query word must be found: "квантовая гравитация" matches nothing rather than
    all of quantum physics, and "кинематика" stays 1.1 instead of also pulling
    oscillation topics that mention "кинематическое описание".
    """

    query = query.strip()
    if CODE.match(query):
        return tuple(topic for topic in catalog if topic.code == query)
    wanted = words(query)
    if not wanted:
        return ()
    tiers: tuple[Callable[[KesTopic], bool], ...] = (
        lambda topic: words(topic.title) == wanted,
        lambda topic: set(wanted) <= set(words(topic.title)),
        lambda topic: stems(query) <= stems(topic.title),
    )
    for matches in tiers:
        found = tuple(topic for topic in catalog if matches(topic))
        if found:
            return found
    return ()


def without_nested(topics: Iterable[KesTopic]) -> tuple[KesTopic, ...]:
    """Parent codes already include child tasks in the bank; keep the outermost ones."""

    unique = {topic.code: topic for topic in topics}
    return tuple(
        topic
        for code, topic in unique.items()
        if not any(code.startswith(other + ".") for other in unique if other != code)
    )


class TaskSearch:
    def __init__(self, bank: TaskBank, *, max_pages: int = 4) -> None:
        if max_pages < 1:
            raise ValueError("max_pages must be positive")
        self.bank = bank
        self.max_pages = max_pages

    async def topics(self, exam: Exam, query: str | None = None) -> tuple[KesTopic, ...]:
        catalog = await self.bank.topics(exam)
        return catalog if query is None else match_topics(catalog, query)

    async def resolve(self, exam: Exam, queries: Sequence[str]) -> tuple[KesTopic, ...]:
        catalog = await self.bank.topics(exam)
        found: list[KesTopic] = []
        for query in queries:
            matches = match_topics(catalog, query)
            if not matches:
                raise UnknownTopicError(exam, query)
            found.extend(matches)
        return without_nested(found)

    async def search(
        self,
        exam: Exam,
        topics: Sequence[str],
        *,
        limit: int = 10,
        kinds: Sequence[AnswerKind] = (),
        with_images: bool = True,
        exclude_ids: Iterable[str] = (),
        seed: int | None = None,
    ) -> SearchResult:
        """Up to limit tasks for КЭС codes or topic names, filtered on our side.

        Without seed the bank order is kept (stable, reproducible). With seed, pages and
        tasks are shuffled so repeated lessons on one topic do not reuse the same start.
        """

        if not topics:
            raise ValueError("at least one topic is required")
        if limit < 1:
            raise ValueError("limit must be positive")
        resolved = await self.resolve(exam, topics)
        codes = [topic.code for topic in resolved]
        excluded = set(exclude_ids)
        rng = random.Random(seed) if seed is not None else None

        first = await self.bank.page(exam, codes, kinds=kinds, page=0)
        pages = list(range(1, math.ceil(first.total / MAX_PAGE_SIZE)))
        if rng:
            rng.shuffle(pages)
        collected: dict[str, BankTask] = {}

        def take(page: Page) -> None:
            for task in page.tasks:
                if task.task_id in excluded or (task.has_images and not with_images):
                    continue
                collected.setdefault(task.task_id, task)

        take(first)
        for number in pages[: self.max_pages - 1]:
            # A shuffled pick needs a wider pool than the number of tasks returned.
            if len(collected) >= (limit if rng is None else 2 * limit):
                break
            take(await self.bank.page(exam, codes, kinds=kinds, page=number))

        tasks = list(collected.values())
        if rng:
            rng.shuffle(tasks)
        return SearchResult(
            exam=exam, topics=resolved, total_available=first.total, tasks=tuple(tasks[:limit])
        )
