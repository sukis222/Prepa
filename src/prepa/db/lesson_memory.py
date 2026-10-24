"""Teacher-scoped lesson notes. Full transcripts are never persisted here."""

from typing import Any

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from prepa.schemas import LessonBrief, TaskWorksheet
from prepa.schemas.lesson_summary import LessonSummary, LessonSummaryInput


class PostgresLessonMemory:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    async def _owned(
        self, conn: AsyncConnection[Any], teacher_id: int, preparation_id: str, version: int
    ) -> TaskWorksheet:
        row = await (
            await conn.execute(
                "select j.result from preparation_jobs j "
                "join preparation_versions v using(preparation_id, version, teacher_id) "
                "where j.teacher_id=%s and j.preparation_id=%s and j.version=%s "
                "and j.status='ready' and v.confirmed_at is not null",
                (teacher_id, preparation_id, version),
            )
        ).fetchone()
        if row is None or row[0].get("package_kind") != "source_worksheet":
            raise ValueError("Готовое занятие не найдено")
        worksheet = TaskWorksheet.model_validate(row[0]["package"])
        if (
            worksheet.preparation_id != preparation_id
            or worksheet.version != version
            or len(worksheet.student_ids) != 1
        ):
            raise ValueError("Нужно отдельное занятие одного ученика")
        member = await (
            await conn.execute(
                "select student_id from preparation_students where teacher_id=%s "
                "and preparation_id=%s and student_id=%s",
                (teacher_id, preparation_id, worksheet.student_ids[0]),
            )
        ).fetchone()
        if member is None:
            raise ValueError("Ученик занятия недоступен")
        return worksheet

    async def select_lesson(self, teacher_id: int, history_index: int) -> TaskWorksheet:
        if history_index < 1:
            raise ValueError("Укажите номер занятия из истории")
        async with await AsyncConnection.connect(self.dsn, connect_timeout=10) as conn:
            row = await (
                await conn.execute(
                    "select state from bot_sessions where teacher_id=%s", (teacher_id,)
                )
            ).fetchone()
            history = row[0].get("session", {}).get("history", []) if row else []
            if history_index > len(history):
                raise ValueError("Занятие не найдено")
            brief = LessonBrief.model_validate(history[history_index - 1])
            return await self._owned(conn, teacher_id, brief.preparation_id, brief.version)

    async def set_pending(self, teacher_id: int, worksheet: TaskWorksheet) -> None:
        async with await AsyncConnection.connect(self.dsn, connect_timeout=10) as conn:
            actual = await self._owned(
                conn, teacher_id, worksheet.preparation_id, worksheet.version
            )
            if worksheet != actual:
                raise ValueError("Материалы занятия изменены")
            await conn.execute(
                "insert into lesson_summary_sessions "
                "(teacher_id, preparation_id, version, student_id, worksheet) "
                "values (%s,%s,%s,%s,%s) on conflict (teacher_id) do update set "
                "preparation_id=excluded.preparation_id, version=excluded.version, "
                "student_id=excluded.student_id, worksheet=excluded.worksheet, updated_at=now()",
                (
                    teacher_id,
                    worksheet.preparation_id,
                    worksheet.version,
                    worksheet.student_ids[0],
                    Jsonb(worksheet.model_dump(mode="json")),
                ),
            )

    async def pending(self, teacher_id: int) -> TaskWorksheet | None:
        async with await AsyncConnection.connect(self.dsn, connect_timeout=10) as conn:
            row = await (
                await conn.execute(
                    "select worksheet from lesson_summary_sessions where teacher_id=%s",
                    (teacher_id,),
                )
            ).fetchone()
            if row is None:
                return None
            worksheet = TaskWorksheet.model_validate(row[0])
            actual = await self._owned(
                conn, teacher_id, worksheet.preparation_id, worksheet.version
            )
            if worksheet != actual:
                raise ValueError("Материалы занятия изменены")
            return worksheet

    async def clear_pending(self, teacher_id: int) -> None:
        async with await AsyncConnection.connect(self.dsn, connect_timeout=10) as conn:
            await conn.execute(
                "delete from lesson_summary_sessions where teacher_id=%s", (teacher_id,)
            )

    async def save_proposal(
        self, teacher_id: int, input: LessonSummaryInput, summary: LessonSummary
    ) -> None:
        if (
            summary.preparation_id != input.preparation_id
            or summary.version != input.version
            or summary.student_id != input.student_id
            or summary.input_digest != input.digest()
        ):
            raise ValueError("Итог не соответствует занятию")
        async with await AsyncConnection.connect(self.dsn, connect_timeout=10) as conn:
            worksheet = await self._owned(conn, teacher_id, input.preparation_id, input.version)
            if worksheet.student_ids != (input.student_id,) or {
                t.task_id: t.statement for t in input.tasks
            } != {t.id: t.statement_exact for t in worksheet.tasks}:
                raise ValueError("Ученик или задачи не соответствуют занятию")
            await conn.execute(
                "insert into lesson_summaries "
                "(teacher_id, preparation_id, version, student_id, input_digest, summary) "
                "values (%s,%s,%s,%s,%s,%s) "
                "on conflict (teacher_id, preparation_id, version, input_digest) "
                "do update set summary=excluded.summary where lesson_summaries.status='pending'",
                (
                    teacher_id,
                    input.preparation_id,
                    input.version,
                    input.student_id,
                    input.digest(),
                    Jsonb(summary.model_dump(mode="json")),
                ),
            )
            await conn.execute(
                "delete from lesson_summary_sessions where teacher_id=%s", (teacher_id,)
            )

    async def confirm_latest(self, teacher_id: int) -> LessonSummary | None:
        async with await AsyncConnection.connect(self.dsn, connect_timeout=10) as conn:
            row = await (
                await conn.execute(
                    "select summary_id, summary from lesson_summaries where teacher_id=%s "
                    "order by created_at desc, summary_id desc limit 1 for update",
                    (teacher_id,),
                )
            ).fetchone()
            if row is None:
                return None
            summary = LessonSummary.model_validate(row[1])
            await self._owned(conn, teacher_id, summary.preparation_id, summary.version)
            await conn.execute(
                "update lesson_summaries set status='confirmed', "
                "confirmed_at=coalesce(confirmed_at, now()) where summary_id=%s and teacher_id=%s",
                (row[0], teacher_id),
            )
            return summary

    async def knowledge(self, teacher_id: int, student_index: int) -> tuple[LessonSummary, ...]:
        if student_index < 1:
            raise ValueError("Укажите номер ученика")
        async with await AsyncConnection.connect(self.dsn, connect_timeout=10) as conn:
            row = await (
                await conn.execute(
                    "select student_id from students where teacher_id=%s "
                    "order by created_at, student_id offset %s limit 1",
                    (teacher_id, student_index - 1),
                )
            ).fetchone()
            if row is None:
                raise ValueError("Ученик не найден")
            rows = await (
                await conn.execute(
                    "select summary from lesson_summaries where teacher_id=%s "
                    "and student_id=%s and status='confirmed' order by created_at, summary_id",
                    (teacher_id, row[0]),
                )
            ).fetchall()
            return tuple(LessonSummary.model_validate(r[0]) for r in rows)
