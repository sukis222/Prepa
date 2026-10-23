"""Real backend sequence exercised with scripted model/HTTP, not physics evaluation."""

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from prepa.agents.runtime import InsufficientMaterialsError
from prepa.documents.delivery import JsonDocuments
from prepa.llm import LLMError
from prepa.preparation.real import FipiMaterials, RealBackend, ReviewRejectedError
from prepa.preparation.worker import failure_message
from prepa.schemas import LessonBrief
from prepa.task_bank import BankTask, SearchResult, TaskSourceError, UnknownTopicError


def run(coro):
    return asyncio.run(coro)


class SequenceLLM:
    def __init__(self, demo, errors=0):
        self.demo, self.errors, self.calls = demo, errors, []

    async def generate(self, *, system_prompt, user_prompt, response_schema):
        role = response_schema["title"]
        self.calls.append((role, json.loads(user_prompt)))
        key = {"Theory": "theory", "AssignmentSet": "assignments", "ReviewReport": "review"}[role]
        result = copy.deepcopy(self.demo[key])
        if key == "review" and self.errors:
            self.errors -= 1
            result["issues"] = [
                {
                    "author": "assignments",
                    "target_id": self.demo["assignments"]["lesson_assignments"][0]["assignment_id"],
                    "severity": "error",
                    "category": "answer",
                    "message": "Check answer",
                    "suggestion": "Recompute",
                }
            ]
        return result


def backend(context, demo, errors=0, **kwargs):
    llm = SequenceLLM(demo, errors)
    source = SimpleNamespace(materials=AsyncMock(return_value=context.materials))
    check = AsyncMock()
    return RealBackend(llm, source=source, check_model=check, **kwargs), llm, source, check


def test_real_three_agents_review_and_projection(context, demo):
    real, llm, source, check = backend(context, demo)
    package = run(real.prepare(1, context.brief, context.students))
    assert [role for role, _ in llm.calls] == ["Theory", "AssignmentSet", "ReviewReport"]
    check.assert_awaited_once()
    source.materials.assert_awaited_once_with(context.brief)
    docs = JsonDocuments()
    teacher = run(docs.teacher(package))
    student = run(docs.student(package.for_student(context.brief.student_ids[0])))
    assert teacher.name == "teacher.json"
    assert json.loads(teacher.content)["review"]["summary"]
    projection = json.loads(student.content)
    assert "answer" not in projection["lesson_assignments"][0]
    assert "context" not in projection
    assert "DEMO" not in student.name


def test_review_requires_correction_and_fresh_review(context, demo):
    real, llm, *_ = backend(context, demo, errors=1)
    package = run(real.prepare(1, context.brief, context.students))
    assert package.review.approved
    assert [role for role, _ in llm.calls] == [
        "Theory",
        "AssignmentSet",
        "ReviewReport",
        "AssignmentSet",
        "ReviewReport",
    ]
    assert "feedback" in llm.calls[3][1]
    real, llm, *_ = backend(context, demo, errors=99)
    with pytest.raises(ReviewRejectedError):
        run(real.prepare(1, context.brief, context.students))
    assert len(llm.calls) == 5


def test_no_calls_before_confirmation_or_profile_validation(context, demo):
    real, llm, source, check = backend(context, demo)
    brief = LessonBrief.model_validate({**context.brief.model_dump(), "confirmed": False})
    for teacher, b, students in [
        (1, brief, context.students),
        (0, context.brief, context.students),
        (1, context.brief, ()),
    ]:
        with pytest.raises(ValueError):
            run(real.prepare(teacher, b, students))
    assert not llm.calls
    check.assert_not_awaited()
    source.materials.assert_not_awaited()
    with pytest.raises(ValueError):
        RealBackend(llm, max_corrections=3)


def test_no_generation_on_missing_sources_or_model_preflight(context, demo):
    real, llm, source, check = backend(context, demo)
    check.side_effect = LLMError("model_not_free")
    with pytest.raises(LLMError):
        run(real.prepare(1, context.brief, context.students))
    source.materials.assert_not_awaited()
    assert not llm.calls
    check.side_effect = None
    source.materials.side_effect = InsufficientMaterialsError(SimpleNamespace())
    with pytest.raises(InsufficientMaterialsError):
        run(real.prepare(1, context.brief, context.students))
    assert not llm.calls


def test_fipi_sources_keep_real_provenance_instruction_and_no_images(context, monkeypatch):
    task = BankTask(
        exam=context.brief.exam,
        task_id="ABC",
        url="https://ege.fipi.ru/bank/questions.php?qid=ABC",
        kes=(),
        answer_kind="multiple_choice",
        instruction="Выберите ровно два ответа",
        statement="A body moves at constant speed.",
    )
    search = AsyncMock(
        return_value=SearchResult(
            exam=context.brief.exam, topics=(), total_available=1, tasks=(task,)
        )
    )

    # SimpleNamespace doesn't implement async context manager special lookup.
    class Bank:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

    monkeypatch.setattr("prepa.preparation.real.maintenance_for_exam", AsyncMock(return_value=None))
    monkeypatch.setattr("prepa.preparation.real.FipiClient", Bank)
    monkeypatch.setattr(
        "prepa.preparation.real.TaskSearch", lambda *a, **kw: SimpleNamespace(search=search)
    )
    brief = LessonBrief.model_validate(
        {**context.brief.model_dump(), "topics": ["Motion", "Speed"]}
    )
    materials = run(FipiMaterials().materials(brief))
    assert len(materials) == 1
    assert materials[0].topics == ("Motion", "Speed")
    assert materials[0].source == task.url
    assert "Выберите ровно два ответа" in materials[0].content
    assert all(call.kwargs["with_images"] is False for call in search.call_args_list)
    search.return_value = SearchResult(
        exam=context.brief.exam, topics=(), total_available=0, tasks=()
    )
    with pytest.raises(InsufficientMaterialsError):
        run(FipiMaterials().materials(brief))
    search.side_effect = UnknownTopicError(context.brief.exam, "Unknown")
    with pytest.raises(InsufficientMaterialsError):
        run(FipiMaterials().materials(brief))


def test_safe_messages():
    for error in [
        LLMError("rate_limit"),
        TaskSourceError("secret"),
        TimeoutError("secret"),
        InsufficientMaterialsError(SimpleNamespace()),
        ValueError("secret"),
    ]:
        code, message = failure_message(error)
        assert code and "secret" not in message


def test_theory_review_regenerates_dependent_practice(context, demo):
    real, llm, *_ = backend(context, demo)
    original = llm.generate
    first = True

    async def generate(**kwargs):
        nonlocal first
        value = await original(**kwargs)
        if kwargs["response_schema"]["title"] == "ReviewReport" and first:
            first = False
            value["issues"] = [
                {
                    "author": "theory",
                    "target_id": demo["theory"]["sections"][0]["section_id"],
                    "severity": "error",
                    "category": "physics",
                    "message": "Check law",
                    "suggestion": "Correct formula",
                }
            ]
        return value

    llm.generate = generate
    assert run(real.prepare(1, context.brief, context.students)).review.approved
    assert [role for role, _ in llm.calls] == [
        "Theory",
        "AssignmentSet",
        "ReviewReport",
        "Theory",
        "AssignmentSet",
        "ReviewReport",
    ]
    assert "feedback" in llm.calls[3][1]
    assert "previous" not in llm.calls[4][1]


@pytest.mark.parametrize("role", ["Theory", "AssignmentSet"])
@pytest.mark.parametrize("budget", [0, 1])
def test_structural_correction_is_bounded(context, demo, role, budget):
    from prepa.agents.runtime import ContentValidationError

    real, llm, *_ = backend(context, demo, max_corrections=budget)
    original = llm.generate
    first = True

    async def generate(**kwargs):
        nonlocal first
        value = await original(**kwargs)
        if kwargs["response_schema"]["title"] == role and first:
            first = False
            if role == "Theory":
                value["sections"][0]["source_ids"] = ["unknown-source"]
            else:
                value["lesson_assignments"][0]["source_ids"] = ["unknown-source"]
        return value

    llm.generate = generate
    if not budget:
        with pytest.raises(ContentValidationError):
            run(real.prepare(1, context.brief, context.students))
    else:
        assert run(real.prepare(1, context.brief, context.students)).review.approved
        assert len(llm.calls) == 4
        repaired = [payload for name, payload in llm.calls if name == role][-1]
        assert "feedback" in repaired and "previous" in repaired


def test_exam_mismatch_before_external_calls(context, demo):
    from prepa.schemas import StudentProfile

    real, llm, source, check = backend(context, demo)
    students = tuple(
        StudentProfile.model_validate(
            {**s.model_dump(), "exam": "ege" if s.exam == "oge" else "oge"}
        )
        for s in context.students
    )
    with pytest.raises(ValueError, match="exam"):
        run(real.prepare(1, context.brief, students))
    source.materials.assert_not_awaited()
    check.assert_not_awaited()
    assert not llm.calls


def test_real_app_lifecycle_closes_provider(monkeypatch):
    from unittest.mock import MagicMock

    from prepa.bot import app
    from prepa.bot.settings import Settings

    repository = SimpleNamespace(check=AsyncMock())
    monkeypatch.setattr(app, "PostgresRepository", MagicMock(return_value=repository))
    bot = MagicMock(send_message=AsyncMock(), send_document=AsyncMock())
    bot.__aenter__ = AsyncMock(return_value=bot)
    bot.__aexit__ = AsyncMock()
    monkeypatch.setattr(app, "Bot", MagicMock(return_value=bot))
    llm = SimpleNamespace(aclose=AsyncMock(), check_model=AsyncMock())
    monkeypatch.setattr(app, "OpenRouterSettings", SimpleNamespace(from_env=lambda: object()))
    monkeypatch.setattr(app, "OpenRouterLLM", lambda _: llm)
    reached = asyncio.Event()

    async def fake_work(queue, backend, docs, deliver, ids):
        assert queue.mode == "real"
        from prepa.documents.source import SourceDocuments
        from prepa.preparation.source import SourceSelectionBackend

        assert isinstance(backend, SourceSelectionBackend)
        assert isinstance(docs, SourceDocuments)
        reached.set()
        await asyncio.Event().wait()

    async def polling(*args, **kwargs):
        await reached.wait()

    monkeypatch.setattr(app, "Dispatcher", lambda: MagicMock(start_polling=polling))
    monkeypatch.setattr(app, "work", fake_work)
    run(app.run(Settings("secret", None, "hidden", "real")))
    llm.aclose.assert_awaited_once()


def test_real_help_and_settings(monkeypatch):
    from prepa.bot.service import DialogService
    from prepa.bot.settings import Settings

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "hidden")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "*")
    monkeypatch.setenv("DATABASE_URL", "hidden")
    monkeypatch.setenv("PREPARATION_MODE", "real")
    assert Settings.from_env().preparation_mode == "real"
    service = DialogService(None)
    service.job_mode = "real"
    help_text = run(service.respond(1, "/help")).text
    assert "REAL" in help_text and "PDF" in help_text
