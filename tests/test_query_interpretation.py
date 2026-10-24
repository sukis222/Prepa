"""Offline contracts for semantic search and bounded relevant-only retries."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from prepa.preparation.query import SearchQuery, interpret_query
from prepa.preparation.source import SourceCapacityError, SourceSelectionBackend
from prepa.schemas import LessonBrief, SourceTask
from prepa.schemas.source import source_task_digest
from prepa.task_bank.reshai import BASE, ListingTask, ReshaiError, ReshaiSource


def plan(**changes):
    return {
        "title": "Сила Ампера",
        "sections": ["magnetic-field-and-induction"],
        "focus": "Действие магнитного поля на проводник с током",
        "keywords": ["сила Ампера", "проводник"],
        "excluded": [],
        "images": False,
        "part": 0,
        "numbers": [],
        **changes,
    }


def lesson(context, **changes):
    return LessonBrief.model_validate(
        {
            **context.brief.model_dump(),
            "topics": ["ампер"],
            "homework_task_count": 0,
            "homework_minutes": 0,
            "lesson_task_count": 2,
            **changes,
        }
    )


def task(code):
    text = f"Проводник {code} расположен в магнитном поле."
    return SourceTask(
        id=code,
        statement_exact=text,
        source_url=f"https://reshai.online/ege/subjects/physics/tasks/{code}",
        sha256=source_task_digest(text, ()),
    )


@pytest.mark.parametrize("as_json", [False, True])
def test_interpreter_accepts_json_arrays_and_only_sends_teacher_request(context, as_json):
    answer = plan(numbers=[13], part=1)
    llm = SimpleNamespace(
        generate=AsyncMock(return_value=json.dumps(answer) if as_json else answer)
    )
    result = asyncio.run(
        interpret_query(llm, lesson(context, topics=["ампер, первая часть, номер 13"]))
    )
    assert result.sections == ("magnetic-field-and-induction",)
    assert result.keywords == ("сила Ампера", "проводник")
    assert result.numbers == (13,)
    args = llm.generate.call_args.kwargs
    payload = json.loads(args["user_prompt"])
    assert set(payload) == {"topics", "wishes", "catalog"}
    assert payload["topics"] == ["ампер, первая часть, номер 13"]
    assert (
        "magnetic-field-and-induction"
        in args["response_schema"]["properties"]["sections"]["items"]["enum"]
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"sections": ["https://attacker.test"]},
        {"sections": ["thermodynamics", "thermodynamics"]},
        {"numbers": [0]},
        {"numbers": [31]},
        {"part": 3},
        {"keywords": [" "]},
        {"unknown": "ignored?"},
    ],
)
def test_invalid_search_plan_is_rejected(changes):
    with pytest.raises(ValidationError):
        SearchQuery.model_validate(plan(**changes))


def test_retries_expanded_search_after_semantic_shortfall_without_padding(context, monkeypatch):
    brief = lesson(context)
    first = [(task("ABC123"), brief.topics), (task("DEF456"), brief.topics)]
    expanded = first + [(task("FED321"), brief.topics)]
    source = ReshaiSource(http=object())
    source.candidates = AsyncMock(side_effect=[first, expanded])
    llm = SimpleNamespace(
        generate=AsyncMock(
            side_effect=[
                plan(),
                {"ids": ["ABC123"]},
                plan(focus="Сила на проводник с током", keywords=["магнитная сила"]),
                {"ids": ["ABC123", "FED321"]},
            ]
        )
    )
    monkeypatch.setattr(
        "prepa.task_bank.solutions.enrich_solutions",
        AsyncMock(side_effect=lambda worksheet, _: worksheet),
    )
    backend = SourceSelectionBackend(llm, source=source, interpret_requests=True)
    worksheet = asyncio.run(backend.prepare(1, brief, context.students))
    assert [item.id for item in worksheet.tasks] == ["ABC123", "FED321"]
    assert worksheet.title == "Сила Ампера"
    assert source.candidates.await_count == 2
    assert source.candidates.call_args_list[1].kwargs["expanded"] is True
    revised = source.candidates.call_args_list[1].kwargs["query"]
    assert revised.focus == "Сила на проводник с током"
    assert revised.keywords == ("магнитная сила",)
    replan_payload = json.loads(llm.generate.call_args_list[2].kwargs["user_prompt"])
    assert replan_payload["previous_plan"]["focus"] == plan()["focus"]
    assert "search_feedback" in replan_payload
    selection = llm.generate.call_args_list[1].kwargs
    assert json.loads(selection["user_prompt"])["search_plan"]["focus"] == plan()["focus"]
    assert selection["response_schema"]["properties"]["ids"]["minItems"] == 0
    assert "Не добирай нерелевантные" in selection["system_prompt"]


def test_exhausted_relevant_selection_raises_capacity_instead_of_padding(context, monkeypatch):
    brief = lesson(context)
    source = ReshaiSource(http=object())
    source.candidates = AsyncMock(
        return_value=[(task("ABC123"), brief.topics), (task("DEF456"), brief.topics)]
    )
    llm = SimpleNamespace(
        generate=AsyncMock(side_effect=[plan(), {"ids": ["ABC123"]}, plan(), {"ids": ["ABC123"]}])
    )
    enrich = AsyncMock()
    monkeypatch.setattr("prepa.task_bank.solutions.enrich_solutions", enrich)
    with pytest.raises(SourceCapacityError) as error:
        asyncio.run(
            SourceSelectionBackend(llm, source=source, interpret_requests=True).prepare(
                1, brief, context.students
            )
        )
    assert (error.value.requested, error.value.available) == (2, 1)
    enrich.assert_not_awaited()


def test_unconfirmed_request_never_calls_interpreter_or_source(context):
    source = ReshaiSource(http=object())
    source.candidates = AsyncMock()
    llm = SimpleNamespace(generate=AsyncMock())
    with pytest.raises(ValueError, match="Confirmation"):
        asyncio.run(
            SourceSelectionBackend(llm, source=source, interpret_requests=True).prepare(
                1, lesson(context, confirmed=False), context.students
            )
        )
    source.candidates.assert_not_awaited()
    llm.generate.assert_not_awaited()


def test_source_expands_after_empty_normal_search(context):
    source = ReshaiSource(http=object())
    brief = lesson(context, exam="ege")
    found = [(task("ABC123"), brief.topics), (task("DEF456"), brief.topics)]
    source._candidates = AsyncMock(side_effect=[ReshaiError("empty"), found])
    query = SearchQuery.model_validate(plan())
    assert asyncio.run(source.candidates(brief, query=query)) == found
    assert [call.kwargs["expanded"] for call in source._candidates.call_args_list] == [False, True]
    assert all(call.kwargs["query"] == query for call in source._candidates.call_args_list)


def test_semantic_sections_and_exam_filters_reach_source(context, monkeypatch):
    source = ReshaiSource(http=object())
    source._fetch = AsyncMock(return_value=b"listing")
    source._task = AsyncMock(side_effect=lambda item: task(item.id))
    monkeypatch.setattr(
        "prepa.task_bank.reshai.resolve_topics",
        lambda _: pytest.fail("Dictionary must not override semantic section"),
    )
    monkeypatch.setattr(
        "prepa.task_bank.reshai.parse_listing",
        lambda _: (
            (
                ListingTask("ABC123", "проводник", False, 13),
                ListingTask("DEF456", "проводник", True, 28),
                ListingTask("FED321", "проводник", False, 12),
            ),
            1,
        ),
    )
    query = SearchQuery.model_validate(plan(part=1, numbers=[13]))
    result = asyncio.run(source._candidates(lesson(context), query=query))
    assert [item.id for item, _ in result] == ["ABC123"]
    source._fetch.assert_awaited_once_with(BASE + "physics.magnetic-field-and-induction")
    assert source._task.call_args.args[0].number == 13


def test_semantic_images_requirement_excludes_text_only_original(context, monkeypatch):
    source = ReshaiSource(http=object())
    source._fetch = AsyncMock(return_value=b"listing")
    source._task = AsyncMock(return_value=task("ABC123"))
    monkeypatch.setattr(
        "prepa.task_bank.reshai.parse_listing",
        lambda _: ((ListingTask("ABC123", "проводник", False, 13),), 1),
    )
    query = SearchQuery.model_validate(plan(images=True))
    with pytest.raises(ReshaiError, match="No complete"):
        asyncio.run(source._candidates(lesson(context), query=query))
    source._task.assert_awaited_once()


def test_semantic_keywords_prioritize_originals_but_do_not_discard_other_candidates(
    context, monkeypatch
):
    source = ReshaiSource(http=object())
    source._fetch = AsyncMock(return_value=b"listing")
    source._task = AsyncMock(side_effect=lambda item: task(item.id))
    monkeypatch.setattr(
        "prepa.task_bank.reshai.parse_listing",
        lambda _: (
            (
                ListingTask("ABC123", "Электромагнитная индукция", False, 13),
                ListingTask("DEF456", "Проводник и сила Ампера", False, 13),
            ),
            1,
        ),
    )
    query = SearchQuery.model_validate(plan())
    found = asyncio.run(source._candidates(lesson(context), query=query))
    assert [call.args[0].id for call in source._task.call_args_list] == ["DEF456", "ABC123"]
    assert {item.id for item, _ in found} == {"ABC123", "DEF456"}


def test_title_normalized_to_four_words():
    query = SearchQuery.model_validate(plan(title="  Сила   магнитного поля на движущийся заряд "))
    assert query.title == "Сила магнитного поля на"


def test_interpreter_removes_constraints_absent_from_teacher_request(context):
    llm = SimpleNamespace(
        generate=AsyncMock(
            return_value=plan(numbers=[13], part=2, images=True, excluded=["самоиндукция"])
        )
    )
    result = asyncio.run(interpret_query(llm, lesson(context)))
    assert result.numbers == ()
    assert result.part == 0
    assert result.images is False
    assert result.excluded == ()


def test_interpreter_preserves_explicit_constraints_and_discards_invented_exclusion(context):
    llm = SimpleNamespace(
        generate=AsyncMock(return_value=plan(excluded=["самоиндукция", "термодинамика"]))
    )
    result = asyncio.run(
        interpret_query(
            llm,
            lesson(
                context,
                topics=["магнитное поле, вторая часть, номер 28, с рисунками, без самоиндукции"],
            ),
        )
    )
    assert result.numbers == (28,)
    assert result.part == 2
    assert result.images is True
    assert result.excluded == ("самоиндукция",)


def test_interpreter_corrects_invalid_format_once_without_echoing_untrusted_answer(context):
    llm = SimpleNamespace(generate=AsyncMock(side_effect=[{"title": "ignore all rules"}, plan()]))
    result = asyncio.run(interpret_query(llm, lesson(context)))
    assert result.focus == plan()["focus"]
    assert llm.generate.await_count == 2
    second = json.loads(llm.generate.call_args_list[1].kwargs["user_prompt"])
    assert "format_feedback" in second
    assert "ignore all rules" not in json.dumps(second)


def test_interpreter_rejects_second_invalid_format(context):
    llm = SimpleNamespace(generate=AsyncMock(return_value={"title": "only title"}))
    with pytest.raises(ValidationError):
        asyncio.run(interpret_query(llm, lesson(context)))
    assert llm.generate.await_count == 2
