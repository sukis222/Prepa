"""Background execution. Save before delivery; Telegram failures never lose the result."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from prepa.bot.service import PreparationBackend, Reply
from prepa.documents.delivery import DocumentRenderer
from prepa.preparation.jobs import JobQueue
from prepa.schemas import LessonPackage

logger = logging.getLogger(__name__)


async def process_one(
    queue: JobQueue,
    backend: PreparationBackend,
    documents: DocumentRenderer,
    deliver: Callable[[int, Reply], Awaitable[None]],
    teacher_ids: frozenset[int] | None,
) -> bool:
    job = await queue.claim()
    if job is None:
        return False
    if teacher_ids is not None and job.teacher_id not in teacher_ids:
        await queue.finish(job, error="access_denied")
        return True
    label = f"Подготовка {job.brief.preparation_id}, v{job.brief.version}. "
    if job.mode == "demo":
        label += "ДЕМО — тест интеграции, не учебный материал. "
    try:
        async with asyncio.timeout(180):
            package = await backend.prepare(job.teacher_id, job.brief, job.students)
            package = LessonPackage.model_validate(package.model_dump(mode="json"))
            if package.context.brief != job.brief or set(package.context.students) != set(
                job.students
            ):
                raise ValueError("Backend context mismatch")
            teacher_file = await documents.teacher(package)
            student_files = tuple(
                [await documents.student(package.for_student(sid)) for sid in job.brief.student_ids]
            )
            files = (teacher_file, *student_files)
            if any(not f.content or len(f.content) > 10_000_000 for f in files):
                raise ValueError("Document size")
    except Exception as error:
        logger.warning("Preparation failed (%s)", type(error).__name__)
        saved = await queue.finish(job, error="preparation_failed")
        reply = Reply(label + "Подготовка не удалась. /retry — повторить.")
    else:
        saved = await queue.finish(job, package, files)
        reply = Reply(
            label + "Готово. teacher — ответы для преподавателя. "
            "Не передавайте его ученикам. /result — получить файлы повторно.",
            attachments=files,
        )
    if saved:
        try:
            await deliver(job.teacher_id, reply)
        except Exception as error:
            logger.warning("Delivery failed (%s); result retained", type(error).__name__)
    return True


async def work(
    queue: JobQueue,
    backend: PreparationBackend,
    documents: DocumentRenderer,
    deliver: Callable[[int, Reply], Awaitable[None]],
    teacher_ids: frozenset[int] | None,
) -> None:
    while True:
        try:
            busy = await process_one(queue, backend, documents, deliver, teacher_ids)
        except Exception as error:
            logger.error("Worker failed (%s)", type(error).__name__)
            busy = False
        if not busy:
            await asyncio.sleep(2)
