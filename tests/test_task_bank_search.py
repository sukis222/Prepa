"""Topic resolution, search filters and paging against an in-memory bank."""

import asyncio
from collections.abc import Iterable

import pytest

from prepa.task_bank import (
    AnswerKind,
    BankTask,
    KesTopic,
    TaskSearch,
    UnknownTopicError,
    match_topics,
)
from prepa.task_bank.fipi.client import MAX_PAGE_SIZE, Page
from prepa.task_bank.models import Exam
from prepa.task_bank.search import without_nested

CATALOG = (
    KesTopic(code="1", title="Механика"),
    KesTopic(code="1.1", title="Кинематика"),
    KesTopic(code="1.1.5", title="Равномерное прямолинейное движение"),
    KesTopic(code="1.1.6", title="Равноускоренное прямолинейное движение"),
    KesTopic(code="1.2", title="Динамика"),
    KesTopic(code="1.5.1", title="Гармонические колебания. Кинематическое описание"),
    KesTopic(code="4", title="Квантовая физика"),
)


def task(number: int, *, images: bool = False) -> BankTask:
    return BankTask(
        exam="ege",
        task_id=f"T{number:04d}",
        url=f"https://bank.test/T{number:04d}",
        kes=(CATALOG[2],),
        answer_kind=AnswerKind.SHORT,
        statement=f"Условие задачи {number}",
        images=("https://bank.test/picture.png",) if images else (),
    )


class FakeBank:
    def __init__(self, tasks: list[BankTask]) -> None:
        self.tasks = tasks
        self.requests: list[tuple[str, tuple[str, ...], tuple[AnswerKind, ...], int]] = []

    async def topics(self, exam: Exam) -> tuple[KesTopic, ...]:
        return CATALOG

    async def page(
        self,
        exam: Exam,
        codes: Iterable[str],
        *,
        kinds: Iterable[AnswerKind] = (),
        page: int = 0,
        page_size: int = MAX_PAGE_SIZE,
    ) -> Page:
        self.requests.append((exam, tuple(codes), tuple(kinds), page))
        start = page * page_size
        return Page(total=len(self.tasks), tasks=tuple(self.tasks[start : start + page_size]))


def ids(tasks: Iterable[BankTask]) -> list[str]:
    return [item.task_id for item in tasks]


@pytest.mark.parametrize(
    ("query", "codes"),
    [
        ("1.1.5", ["1.1.5"]),
        ("9.9", []),
        ("Кинематика", ["1.1"]),
        ("равномерное прямолинейное движение", ["1.1.5"]),
        ("прямолинейное движение", ["1.1.5", "1.1.6"]),
        ("равномерного движения", ["1.1.5"]),
        ("квантовая гравитация", []),
        ("и", []),
        ("кинематическое", ["1.5.1"]),
    ],
)
def test_match_topics(query: str, codes: list[str]) -> None:
    assert [topic.code for topic in match_topics(CATALOG, query)] == codes


def test_nested_codes_are_covered_by_their_parent() -> None:
    topics = without_nested([CATALOG[2], CATALOG[1], CATALOG[1], CATALOG[4]])
    assert [topic.code for topic in topics] == ["1.1", "1.2"]


def test_search_resolves_topics_and_stops_after_enough_tasks() -> None:
    bank = FakeBank([task(n) for n in range(120)])
    result = asyncio.run(
        TaskSearch(bank).search("ege", ["кинематика", "1.1.5"], limit=60, kinds=[AnswerKind.SHORT])
    )
    assert [topic.code for topic in result.topics] == ["1.1"]
    assert result.total_available == 120
    assert ids(result.tasks) == [f"T{n:04d}" for n in range(60)]
    assert bank.requests == [
        ("ege", ("1.1",), (AnswerKind.SHORT,), 0),
        ("ege", ("1.1",), (AnswerKind.SHORT,), 1),
    ]


def test_search_filters_pictures_and_already_given_tasks_across_pages() -> None:
    bank = FakeBank([task(n, images=n % 2 == 0) for n in range(110)])
    result = asyncio.run(
        TaskSearch(bank).search(
            "ege", ["1.1.5"], limit=30, with_images=False, exclude_ids=["T0001", "T0003"]
        )
    )
    assert ids(result.tasks)[:3] == ["T0005", "T0007", "T0009"]
    assert len(result.tasks) == 30
    assert all(not item.has_images for item in result.tasks)
    assert [request[3] for request in bank.requests] == [0, 1]


def test_search_respects_page_budget_and_returns_what_it_found() -> None:
    bank = FakeBank([task(n, images=True) for n in range(500)])
    result = asyncio.run(
        TaskSearch(bank, max_pages=2).search("ege", ["1.1.5"], limit=5, with_images=False)
    )
    assert result.tasks == ()
    assert result.total_available == 500
    assert len(bank.requests) == 2


def test_seeded_search_is_shuffled_but_reproducible() -> None:
    def run(seed: int) -> list[str]:
        bank = FakeBank([task(n) for n in range(200)])
        return ids(
            asyncio.run(TaskSearch(bank).search("ege", ["1.1.5"], limit=10, seed=seed)).tasks
        )

    assert run(1) == run(1)
    assert run(1) != run(2)
    assert run(1) != [f"T{n:04d}" for n in range(10)]
    assert len(set(run(3))) == 10


def test_search_and_topic_errors() -> None:
    search = TaskSearch(FakeBank([]))
    with pytest.raises(UnknownTopicError, match="EGE") as error:
        asyncio.run(search.search("ege", ["квантовая гравитация"]))
    assert error.value.query == "квантовая гравитация"
    with pytest.raises(ValueError, match="topic"):
        asyncio.run(search.search("ege", []))
    with pytest.raises(ValueError, match="limit"):
        asyncio.run(search.search("ege", ["1.1"], limit=0))
    with pytest.raises(ValueError, match="max_pages"):
        TaskSearch(FakeBank([]), max_pages=0)


def test_topics_lists_catalog_or_matches_query() -> None:
    search = TaskSearch(FakeBank([]))
    assert asyncio.run(search.topics("ege")) == CATALOG
    assert asyncio.run(search.topics("ege", "динамика")) == (CATALOG[4],)


def test_empty_topic_result_is_reported_without_tasks() -> None:
    result = asyncio.run(TaskSearch(FakeBank([])).search("ege", ["4"]))
    assert result.total_available == 0
    assert result.tasks == ()
