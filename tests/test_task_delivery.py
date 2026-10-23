"""The real worker publishes one public task sheet, never the internal package."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

from prepa.documents.delivery import Attachment, DemoDocuments, JsonDocuments
from prepa.preparation.demo import DemoBackend
from prepa.preparation.jobs import Job
from prepa.preparation.worker import process_one
from prepa.schemas import LessonBrief


def test_real_worker_only_tasks(context):
    brief = LessonBrief.model_validate(
        {
            **context.brief.model_dump(),
            "student_ids": [context.students[0].student_id],
            "homework_task_count": 0,
            "homework_minutes": 0,
        }
    )
    package = asyncio.run(DemoBackend().prepare(7, brief, context.students[:1]))
    job = Job(7, brief, package.context.students, "token", "real")
    queue = SimpleNamespace(claim=AsyncMock(return_value=job), finish=AsyncMock(return_value=True))
    backend = SimpleNamespace(prepare=AsyncMock(return_value=package))
    sheet = Attachment("tasks-v1.pdf", b"%PDF-synthetic")
    docs = SimpleNamespace(
        tasks=AsyncMock(return_value=sheet), teacher=AsyncMock(), student=AsyncMock()
    )
    deliver = AsyncMock()
    assert asyncio.run(process_one(queue, backend, docs, deliver, None))
    docs.tasks.assert_awaited_once_with(package.for_student(brief.student_ids[0]), demo=False)
    docs.teacher.assert_not_awaited()
    docs.student.assert_not_awaited()
    assert queue.finish.call_args.args[2] == (sheet,)
    reply = deliver.call_args.args[1]
    assert reply.attachments == (sheet,)
    assert "Один PDF" in reply.text
    assert "teacher" not in reply.text
    queue.claim.return_value = replace(job, brief=context.brief, students=context.students)
    backend.prepare.return_value = asyncio.run(
        DemoBackend().prepare(7, context.brief, context.students)
    )
    asyncio.run(process_one(queue, backend, docs, deliver, None))
    assert len(queue.finish.call_args.args[2]) == 1
    assert queue.finish.call_args.args[1].context.students == context.students


def test_diagnostic_tasks_projection(package):
    lesson = package.for_student(package.context.brief.student_ids[0])
    assert asyncio.run(DemoDocuments().tasks(lesson)).name.startswith("DEMO-")
    result = asyncio.run(JsonDocuments().tasks(lesson))
    assert result.name == "tasks.json"
    assert b'"answer"' not in result.content
    assert b'"theory"' not in result.content
