"""Background execution. Save before delivery; Telegram failures never lose the result."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol, cast

from prepa.agents.runtime import InsufficientMaterialsError
from prepa.bot.service import PreparationBackend, Reply
from prepa.documents.delivery import Attachment, DocumentRenderer
from prepa.documents.latex import DocumentError
from prepa.documents.solutions import solution_document
from prepa.documents.source import SourceDocuments
from prepa.llm import LLMError
from prepa.preparation.jobs import JobQueue
from prepa.preparation.source import SourceCapacityError, SourceCorpusError
from prepa.schemas import LessonPackage, TaskWorksheet
from prepa.task_bank import TaskSourceError

logger = logging.getLogger(__name__)


class WorksheetRenderer(Protocol):
    async def worksheet(self, worksheet: TaskWorksheet) -> Attachment: ...


async def process_one(
    queue: JobQueue,
    backend: PreparationBackend,
    documents: DocumentRenderer | WorksheetRenderer,
    deliver: Callable[[int, Reply], Awaitable[None]],
    teacher_ids: frozenset[int] | None,
) -> bool:
    job = await queue.claim()
    if job is None:
        return False
    if teacher_ids is not None and job.teacher_id not in teacher_ids:
        await queue.finish(job, error="access_denied")
        return True
    label = ("Ученик: " + ", ".join(job.student_names) + "\n") if job.student_names else ""
    if job.mode == "demo":
        label += "ДЕМО — тест интеграции, не учебный материал. "
    try:
        deadline = asyncio.get_running_loop().time() + 265
        async with asyncio.timeout(270):
            package = await backend.prepare(job.teacher_id, job.brief, job.students)
            files: tuple[Attachment, ...]
            if isinstance(package, TaskWorksheet):
                package = TaskWorksheet.model_validate(package.model_dump(mode="json"))
                if (
                    package.preparation_id != job.brief.preparation_id
                    or package.version != job.brief.version
                    or package.student_ids != job.brief.student_ids
                    or package.exam != job.brief.exam
                    or package.topics != job.brief.topics
                    or len(package.tasks) != job.brief.lesson_task_count
                ):
                    raise ValueError("Backend worksheet mismatch")
                files = (await cast(WorksheetRenderer, documents).worksheet(package),)
                if isinstance(documents, SourceDocuments):
                    try:
                        teacher_copy = await asyncio.wait_for(
                            solution_document(documents, package),
                            timeout=max(0.1, min(30, deadline - asyncio.get_running_loop().time())),
                        )
                    except (DocumentError, TimeoutError):
                        logger.warning("Source solution PDF unavailable; worksheet retained")
                    else:
                        if teacher_copy is not None:
                            files += (teacher_copy,)
            else:
                package = LessonPackage.model_validate(package.model_dump(mode="json"))
                if package.context.brief != job.brief or set(package.context.students) != set(
                    job.students
                ):
                    raise ValueError("Backend context mismatch")
                files = (
                    await cast(DocumentRenderer, documents).tasks(
                        package.for_student(job.brief.student_ids[0]), demo=job.mode == "demo"
                    ),
                )
            if any(not f.content or len(f.content) > 10_000_000 for f in files):
                raise ValueError("Document size")
    except Exception as error:
        logger.warning("Preparation failed (%s)", type(error).__name__)
        code, message = failure_message(error)
        saved = await queue.finish(job, error=code)
        reply = Reply(label + message)
    else:
        saved = await queue.finish(job, package, files)
        reply = Reply(
            label
            + (
                (
                    "Готово. PDF с задачами и отдельный PDF с решениями из источника. "
                    if len(files) > 1
                    else "Готово. Один PDF с задачами. Подходящих решений из источника нет. "
                )
                + "/result — получить файл повторно."
                if job.mode == "real"
                else "Готово. Один демонстрационный файл с задачами и местом для решения. "
                "/result — получить файл повторно."
            ),
            attachments=files,
        )
        if isinstance(package, TaskWorksheet) and len(files) > 1:
            count = sum(task.solution is not None for task in package.tasks)
            reply = Reply(
                reply.text + f" Разборы найдены для {count} из {len(package.tasks)} задач; "
                "для остальных отсутствие отмечено в файле.",
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
    documents: DocumentRenderer | WorksheetRenderer,
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


def failure_message(error: Exception) -> tuple[str, str]:
    """Only static messages reach Telegram; external error text is never copied."""
    if isinstance(error, SourceCapacityError):
        return "source_capacity", (
            f"В подключённом источнике доступно {error.available} подходящих задач, "
            f"а запрошено {error.requested}. Новые условия не генерируются.\n\n"
            "/edit — изменить темы или количество задач.\n"
            "/retry — повторить поиск."
        )
    if isinstance(error, SourceCorpusError):
        return "source_corpus", (
            "Не удалось получить подходящие задачи из источника.\n\n"
            "/edit — изменить темы и пожелания.\n"
            "/retry — повторить поиск."
        )

    if isinstance(error, InsufficientMaterialsError):
        return "insufficient_materials", (
            "Недостаточно текстовых источников ФИПИ. Уточните тему или код КЭС через /edit. "
            "Задачи с рисунками пока не используются."
        )
    if isinstance(error, TaskSourceError):
        return "source_unavailable", "ФИПИ недоступен. /retry — повторить позже."
    if isinstance(error, LLMError):
        messages = {
            "authentication": "OpenRouter: проверьте API-ключ в настройках.",
            "invalid_request": "OpenRouter отклонил формат запроса; требуется проверка интеграции.",
            "provider_unavailable": "Провайдер модели недоступен. /retry — повторить позже.",
            "quota": "OpenRouter: запрос отклонён из-за лимита аккаунта.",
            "rate_limit": "Лимит бесплатной модели OpenRouter. /retry — повторить позже.",
            "model_not_free": "Модель больше не бесплатна; вызовы остановлены.",
            "model_unavailable": "Модель недоступна. Измените OPENROUTER_MODEL.",
            "structured_outputs_unavailable": "Модель не поддерживает нужный формат JSON.",
            "reasoning_configuration_unavailable": "Модель не поддерживает отключение reasoning.",
        }
        return "model_" + error.code, messages.get(
            error.code, "OpenRouter не вернул корректный ответ. /retry — повторить позже."
        )
    if isinstance(error, DocumentError):
        return "pdf_failed", "PDF не собран. Выдача отменена; проверьте LaTeX. /retry — повторить."
    if isinstance(error, TimeoutError):
        return "preparation_timeout", "Время подготовки истекло. /retry — повторить."
    return "preparation_failed", "Подготовка не удалась. /retry — повторить."
