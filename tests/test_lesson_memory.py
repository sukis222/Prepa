"""Persistence boundaries with synthetic records only; no external DB or models."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from prepa.db.lesson_memory import PostgresLessonMemory
from prepa.schemas import SourceTask, TaskWorksheet
from prepa.schemas.lesson_summary import LessonSummary, LessonSummaryInput
from prepa.schemas.source import source_task_digest


@pytest.fixture
def memory(monkeypatch, context):
    task = SourceTask(
        id="task1",
        statement_exact="Найдите работу газа.",
        source_url="https://example.test/task1",
        sha256=source_task_digest("Найдите работу газа."),
    )
    brief = context.brief
    worksheet = TaskWorksheet(
        preparation_id=brief.preparation_id,
        version=brief.version,
        student_ids=(brief.student_ids[0],),
        exam=brief.exam,
        topics=brief.topics,
        title="Термодинамика",
        tasks=(task,),
    )
    input = LessonSummaryInput(
        preparation_id=worksheet.preparation_id,
        version=worksheet.version,
        student_id=worksheet.student_ids[0],
        tasks=({"task_id": task.id, "statement": task.statement_exact},),
        transcript=(
            {"turn_id": "turn1", "speaker": "student", "text": "Мне непонятен знак работы."},
        ),
    )
    summary = LessonSummary(
        preparation_id=input.preparation_id,
        version=input.version,
        student_id=input.student_id,
        input_digest=input.digest(),
        overview="Обсудили работу газа.",
        insufficient_evidence=True,
    )
    conn = AsyncMock()
    manager = AsyncMock()
    manager.__aenter__.return_value = conn
    connect = AsyncMock(return_value=manager)
    monkeypatch.setattr("prepa.db.lesson_memory.AsyncConnection.connect", connect)
    obj = PostgresLessonMemory("synthetic")
    return SimpleNamespace(
        obj=obj, conn=conn, worksheet=worksheet, input=input, summary=summary, brief=brief
    )


def replies(memory, *rows):
    memory.conn.execute.side_effect = [
        SimpleNamespace(fetchone=AsyncMock(return_value=row)) for row in rows
    ]


def owned(memory):
    return (
        {"package_kind": "source_worksheet", "package": memory.worksheet.model_dump(mode="json")},
    )


def test_select_lesson_uses_same_history_as_bot(memory):
    replies(
        memory,
        ({"session": {"history": [memory.brief.model_dump(mode="json")]}},),
        owned(memory),
        (memory.input.student_id,),
    )
    assert asyncio.run(memory.obj.select_lesson(81, 1)) == memory.worksheet
    assert memory.conn.execute.call_args_list[0].args[1] == (81,)
    assert memory.conn.execute.call_args_list[1].args[1] == (
        81,
        memory.input.preparation_id,
        memory.input.version,
    )


@pytest.mark.parametrize("row", [None, ({"session": {"history": []}},)])
def test_missing_history(memory, row):
    replies(memory, row)
    with pytest.raises(ValueError):
        asyncio.run(memory.obj.select_lesson(81, 1))


@pytest.mark.parametrize("method", ["select_lesson", "knowledge"])
def test_indices(memory, method):
    with pytest.raises(ValueError):
        asyncio.run(getattr(memory.obj, method)(81, 0))


@pytest.mark.parametrize("row", [None, ({"package_kind": "lesson"},)])
def test_lesson_not_owned_or_not_source(memory, row):
    replies(memory, row)
    with pytest.raises(ValueError):
        asyncio.run(memory.obj._owned(memory.conn, 999, "p", 1))


def test_bad_worksheet_identity_or_membership(memory):
    replies(memory, owned(memory))
    with pytest.raises(ValueError):
        asyncio.run(memory.obj._owned(memory.conn, 81, "different", 1))
    replies(memory, owned(memory), None)
    with pytest.raises(ValueError):
        asyncio.run(
            memory.obj._owned(memory.conn, 81, memory.input.preparation_id, memory.input.version)
        )


def test_pending_roundtrip_and_clear(memory):
    replies(memory, owned(memory), (memory.input.student_id,), None)
    asyncio.run(memory.obj.set_pending(81, memory.worksheet))
    assert memory.conn.execute.call_args.args[1][0] == 81
    replies(
        memory,
        (memory.worksheet.model_dump(mode="json"),),
        owned(memory),
        (memory.input.student_id,),
    )
    assert asyncio.run(memory.obj.pending(81)) == memory.worksheet
    memory.conn.execute.side_effect = None
    asyncio.run(memory.obj.clear_pending(81))
    assert memory.conn.execute.call_args.args[1] == (81,)
    replies(memory, None)
    assert asyncio.run(memory.obj.pending(81)) is None


def test_changed_pending_rejected(memory):
    changed = TaskWorksheet.model_validate(
        {**memory.worksheet.model_dump(), "title": "Другая тема"}
    )
    replies(memory, owned(memory), (memory.input.student_id,))
    with pytest.raises(ValueError):
        asyncio.run(memory.obj.set_pending(81, changed))
    replies(memory, (changed.model_dump(mode="json"),), owned(memory), (memory.input.student_id,))
    with pytest.raises(ValueError):
        asyncio.run(memory.obj.pending(81))


def test_proposal_never_stores_transcript(memory):
    replies(memory, owned(memory), (memory.input.student_id,), None, None)
    asyncio.run(memory.obj.save_proposal(81, memory.input, memory.summary))
    stored = memory.conn.execute.call_args_list[-2].args[1][-1].obj
    assert stored == memory.summary.model_dump(mode="json")
    assert "transcript" not in stored
    assert "Мне непонятен знак работы." not in str(stored)
    assert memory.conn.execute.call_args.args[1] == (81,)


def test_mismatched_digest_or_tasks_rejected(memory):
    summary = LessonSummary.model_validate(
        {**memory.summary.model_dump(), "input_digest": "a" * 64}
    )
    with pytest.raises(ValueError):
        asyncio.run(memory.obj.save_proposal(81, memory.input, summary))
    input = LessonSummaryInput.model_validate({**memory.input.model_dump(), "tasks": []})
    summary = LessonSummary.model_validate(
        {**memory.summary.model_dump(), "input_digest": input.digest()}
    )
    replies(memory, owned(memory), (memory.input.student_id,))
    with pytest.raises(ValueError):
        asyncio.run(memory.obj.save_proposal(81, input, summary))


def test_confirm_is_atomic_teacher_scoped_and_no_profile_updates(memory):
    replies(
        memory,
        (17, memory.summary.model_dump(mode="json")),
        owned(memory),
        (memory.input.student_id,),
        None,
    )
    assert asyncio.run(memory.obj.confirm_latest(81)) == memory.summary
    queries = [c.args[0] for c in memory.conn.execute.call_args_list]
    assert "for update" in queries[0]
    assert not any("update students" in q for q in queries)
    assert memory.conn.execute.call_args.args[1] == (17, 81)
    replies(memory, None)
    assert asyncio.run(memory.obj.confirm_latest(81)) is None


def test_knowledge_only_owned_student_and_confirmed(memory):
    rows = SimpleNamespace(
        fetchall=AsyncMock(return_value=[(memory.summary.model_dump(mode="json"),)])
    )
    memory.conn.execute.side_effect = [
        SimpleNamespace(fetchone=AsyncMock(return_value=(memory.input.student_id,))),
        rows,
    ]
    assert asyncio.run(memory.obj.knowledge(81, 1)) == (memory.summary,)
    assert "status='confirmed'" in memory.conn.execute.call_args.args[0]
    assert memory.conn.execute.call_args.args[1] == (81, memory.input.student_id)
    replies(memory, None)
    with pytest.raises(ValueError):
        asyncio.run(memory.obj.knowledge(81, 1))
