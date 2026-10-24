"""Teacher-confirmed lesson memory, independently of the worksheet dialog."""

import asyncio
import re
from collections.abc import Awaitable, Callable
from typing import Literal

from prepa.agents.runtime import AgentResponseError
from prepa.agents.summarizer import LessonSummarizerAgent
from prepa.bot.service import Reply
from prepa.db.lesson_memory import PostgresLessonMemory
from prepa.llm import LLMError
from prepa.schemas.lesson_summary import (
    LessonSummary,
    LessonSummaryInput,
    LessonTaskReference,
    TranscriptTurn,
)


def transcript_turns(text: str) -> tuple[TranscriptTurn, ...]:
    if not text.strip() or len(text) > 100000:
        raise ValueError("Нужен текст транскрипта до 100000 символов.")
    turns: list[TranscriptTurn] = []
    for line in text.splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line or line.isdigit() or "-->" in line or line == "WEBVTT":
            continue
        match = re.match(
            r"^(ученик|student|преподаватель|репетитор|teacher)\s*:\s*(.+)$", line, re.I
        )
        speaker: Literal["student", "teacher", "unknown"] = "unknown"
        if match:
            speaker = "student" if match[1].casefold() in ("ученик", "student") else "teacher"
            line = match[2]
        for start in range(0, len(line), 6000):
            turns.append(
                TranscriptTurn(
                    turn_id=f"turn-{len(turns) + 1}",
                    speaker=speaker,
                    text=line[start : start + 6000],
                )
            )
    if not turns or len(turns) > 1000:
        raise ValueError("Не найдены реплики или их слишком много.")
    return tuple(turns)


def summary_text(summary: LessonSummary) -> str:
    labels = {
        "understood": "Разобрался",
        "difficulty": "Нужно повторить",
        "unclear": "Недостаточно данных",
    }
    lines = [summary.overview]
    for item in summary.observations:
        lines.append(f"{labels[item.status]} — {item.topic}: {item.finding}")
        lines.extend("Основание: «" + e.quote + "»" for e in item.evidence)
    if summary.next_steps:
        lines.append("На следующие занятия:")
        lines.extend("- " + item.topic + ": " + item.action for item in summary.next_steps)
    if summary.uncertainty:
        lines.append("Неясно: " + "; ".join(summary.uncertainty))
    return "\n\n".join(lines)


class SummaryDialog:
    def __init__(
        self,
        memory: PostgresLessonMemory,
        agent: LessonSummarizerAgent,
        check_model: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.memory, self.agent = memory, agent
        self.check_model = check_model
        self.locks: dict[int, asyncio.Lock] = {}

    async def respond(
        self, teacher_id: int, text: str, *, transcript_file: bool = False
    ) -> Reply | None:
        async with self.locks.setdefault(teacher_id, asyncio.Lock()):
            return await self._respond(teacher_id, text, transcript_file=transcript_file)

    async def _respond(
        self, teacher_id: int, text: str, *, transcript_file: bool = False
    ) -> Reply | None:
        command = text.split(maxsplit=1)[0] if text.strip() and not transcript_file else ""
        try:
            if command == "/summarize":
                pieces = text.split()
                if len(pieces) != 2 or not pieces[1].isdigit():
                    return Reply(
                        "После занятия: /summarize N — номер готового занятия из /history."
                    )
                worksheet = await self.memory.select_lesson(teacher_id, int(pieces[1]))
                await self.memory.set_pending(teacher_id, worksheet)
                return Reply(
                    "Пришлите обезличенную транскрипцию Zoom текстом или файлом TXT/SRT/VTT. "
                    "Для распознавания участников используйте «Ученик:» и «Преподаватель:». "
                    "Текст будет отправлен модели OpenRouter. Полный транскрипт не сохраняется; "
                    "в базе останутся подтверждённые тезисы и короткие цитаты. /cancel — отмена."
                )
            if command == "/confirm_summary":
                result = await self.memory.confirm_latest(teacher_id)
                return Reply(
                    "Итоги сохранены в базе знаний ученика."
                    if result
                    else "Нет итогов для подтверждения."
                )
            if command == "/knowledge":
                pieces = text.split()
                if len(pieces) != 2 or not pieces[1].isdigit():
                    return Reply("/knowledge N — номер ученика из /students.")
                records = await self.memory.knowledge(teacher_id, int(pieces[1]))
                return Reply(
                    "\n\n".join(
                        f"Занятие {i}\n" + summary_text(s) for i, s in enumerate(records, 1)
                    )
                    if records
                    else "Подтверждённых итогов занятий пока нет."
                )
            if not transcript_file and (
                text.startswith("/") or text in ("Новое занятие", "Отмена", "Добавить ученика")
            ):
                await self.memory.clear_pending(teacher_id)
                return None
            pending_worksheet = await self.memory.pending(teacher_id)
            if pending_worksheet is None:
                return None
            worksheet = pending_worksheet
            context = LessonSummaryInput(
                preparation_id=worksheet.preparation_id,
                version=worksheet.version,
                student_id=worksheet.student_ids[0],
                tasks=tuple(
                    LessonTaskReference(task_id=t.id, statement=t.statement_exact)
                    for t in worksheet.tasks
                ),
                transcript=transcript_turns(text),
            )
            if self.check_model is not None:
                await asyncio.wait_for(self.check_model(), timeout=10)
            result = await self.agent.summarize(context)
            await self.memory.save_proposal(teacher_id, context, result)
            return Reply(
                "Предложенные итоги занятия — проверьте перед сохранением.\n\n"
                + summary_text(result)
                + "\n\n/confirm_summary — сохранить в базе знаний ученика."
            )
        except (AgentResponseError, LLMError, TimeoutError):
            return Reply(
                "Модель не вернула проверенные итоги. Текст не сохранён. "
                "Пришлите транскрипт повторно; /cancel — отмена."
            )
        except ValueError:
            return Reply(
                "Проверьте номер из /history или /students и текст транскрипта. "
                "Для анализа нужны готовые материалы отдельного ученика."
            )
