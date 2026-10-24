"""Teacher-scoped transactions. Common content models remain in prepa.schemas."""

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from prepa.schemas import LessonBrief, StudentProfile


@dataclass(frozen=True)
class StudentRecord:
    profile: StudentProfile
    display_name: str
    goal: str | None = None


class Store(Protocol):
    async def load_state(self) -> dict[str, Any] | None: ...
    async def save_state(self, state: dict[str, Any]) -> None: ...
    async def students(self) -> tuple[StudentRecord, ...]: ...
    async def add_student(self, student: StudentRecord) -> None: ...
    async def save_brief(self, brief: LessonBrief) -> None: ...
    async def enqueue(
        self, brief: LessonBrief, students: tuple[StudentProfile, ...], mode: str
    ) -> None: ...
    async def job(self, brief: LessonBrief) -> dict[str, Any] | None: ...
    async def retry(self, brief: LessonBrief, mode: str) -> bool: ...


class Repository(Protocol):
    def transaction(self, teacher_id: int) -> AbstractAsyncContextManager[Store]: ...


class PostgresRepository:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    async def check(self) -> None:
        async with await AsyncConnection.connect(self.dsn, connect_timeout=10) as conn:
            row = await (
                await conn.execute("SELECT max(version) FROM schema_migrations")
            ).fetchone()
            if row is None or row[0] != 4:
                raise RuntimeError("Apply migrations 001 through 004 before starting the bot")

    @asynccontextmanager
    async def transaction(self, teacher_id: int) -> AsyncIterator[Store]:
        async with await AsyncConnection.connect(self.dsn, connect_timeout=10) as conn:
            await conn.execute("SET LOCAL statement_timeout = '15s'")
            await conn.execute("SET LOCAL lock_timeout = '10s'")
            await conn.execute(
                "INSERT INTO teachers(telegram_user_id, display_name) VALUES (%s, %s) "
                "ON CONFLICT (telegram_user_id) DO NOTHING",
                (teacher_id, str(teacher_id)),
            )
            # Serializes all state transitions for this teacher, including across processes.
            await conn.execute(
                "SELECT telegram_user_id FROM teachers WHERE telegram_user_id = %s FOR UPDATE",
                (teacher_id,),
            )
            yield PostgresStore(conn, teacher_id)
            # Connection context commits only on success; any exception rolls everything back.


class PostgresStore:
    def __init__(self, conn: AsyncConnection[Any], teacher_id: int) -> None:
        self.conn = conn
        self.teacher_id = teacher_id

    async def load_state(self) -> dict[str, Any] | None:
        row = await (
            await self.conn.execute(
                "SELECT state FROM bot_sessions WHERE teacher_id = %s", (self.teacher_id,)
            )
        ).fetchone()
        if row is None:
            return None
        state: dict[str, Any] = row[0]
        return state

    async def save_state(self, state: dict[str, Any]) -> None:
        await self.conn.execute(
            "INSERT INTO bot_sessions(teacher_id, state) VALUES (%s, %s) "
            "ON CONFLICT (teacher_id) DO UPDATE SET state = EXCLUDED.state, updated_at = now()",
            (self.teacher_id, Jsonb(state)),
        )

    async def students(self) -> tuple[StudentRecord, ...]:
        rows = await (
            await self.conn.execute(
                "SELECT profile, display_name, goal FROM students "
                "WHERE teacher_id = %s ORDER BY created_at, student_id",
                (self.teacher_id,),
            )
        ).fetchall()
        return tuple(
            StudentRecord(StudentProfile.model_validate(row[0]), row[1], row[2]) for row in rows
        )

    async def add_student(self, student: StudentRecord) -> None:
        profile = StudentProfile.model_validate(student.profile.model_dump())
        await self.conn.execute(
            "INSERT INTO students(student_id, teacher_id, display_name, goal, profile) "
            "VALUES (%s, %s, %s, %s, %s)",
            (
                profile.student_id,
                self.teacher_id,
                student.display_name,
                student.goal,
                Jsonb(profile.model_dump(mode="json")),
            ),
        )

    async def save_brief(self, brief: LessonBrief) -> None:
        brief = LessonBrief.model_validate(brief.model_dump())
        if not brief.confirmed:
            raise ValueError("Only confirmed requests belong in preparation_versions")
        owned = {s.profile.student_id for s in await self.students()}
        if not set(brief.student_ids) <= owned:
            raise ValueError("Student access denied")
        await self.conn.execute(
            "INSERT INTO preparations(preparation_id, teacher_id) VALUES (%s, %s) "
            "ON CONFLICT (preparation_id) DO NOTHING",
            (brief.preparation_id, self.teacher_id),
        )
        owner = await (
            await self.conn.execute(
                "SELECT teacher_id FROM preparations WHERE preparation_id = %s AND teacher_id = %s",
                (brief.preparation_id, self.teacher_id),
            )
        ).fetchone()
        if owner is None:
            raise ValueError("Preparation access denied")
        members = await (
            await self.conn.execute(
                "SELECT student_id FROM preparation_students "
                "WHERE preparation_id = %s AND teacher_id = %s",
                (brief.preparation_id, self.teacher_id),
            )
        ).fetchall()
        if members and {row[0] for row in members} != set(brief.student_ids):
            raise ValueError("Preparation membership cannot change")
        for student_id in brief.student_ids:
            await self.conn.execute(
                "INSERT INTO preparation_students(preparation_id, student_id, teacher_id) "
                "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (brief.preparation_id, student_id, self.teacher_id),
            )
        existing = await (
            await self.conn.execute(
                "SELECT brief FROM preparation_versions "
                "WHERE preparation_id = %s AND version = %s AND teacher_id = %s",
                (brief.preparation_id, brief.version, self.teacher_id),
            )
        ).fetchone()
        if existing is not None:
            if LessonBrief.model_validate(existing[0]) != brief:
                raise ValueError("Confirmed versions are immutable")
            return
        await self.conn.execute(
            "INSERT INTO preparation_versions"
            "(preparation_id, version, teacher_id, status, brief, confirmed_at) "
            "VALUES (%s, %s, %s, 'confirmed', %s, now())",
            (
                brief.preparation_id,
                brief.version,
                self.teacher_id,
                Jsonb(brief.model_dump(mode="json")),
            ),
        )

    async def enqueue(
        self, brief: LessonBrief, students: tuple[StudentProfile, ...], mode: str
    ) -> None:
        owned = {s.profile for s in await self.students()}
        if not set(students) <= owned or {s.student_id for s in students} != set(brief.student_ids):
            raise ValueError("Student snapshot access denied")
        await self.conn.execute(
            "INSERT INTO preparation_jobs(preparation_id, version, teacher_id, mode, students) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (
                brief.preparation_id,
                brief.version,
                self.teacher_id,
                mode,
                Jsonb([s.model_dump(mode="json") for s in students]),
            ),
        )

    async def job(self, brief: LessonBrief) -> dict[str, Any] | None:
        row = await (
            await self.conn.execute(
                "SELECT status, mode, result FROM preparation_jobs "
                "WHERE preparation_id=%s AND version=%s AND teacher_id=%s",
                (brief.preparation_id, brief.version, self.teacher_id),
            )
        ).fetchone()
        return None if row is None else {"status": row[0], "mode": row[1], "result": row[2]}

    async def retry(self, brief: LessonBrief, mode: str) -> bool:
        cursor = await self.conn.execute(
            "UPDATE preparation_jobs SET status='queued', attempts=0, error_code=NULL "
            "WHERE preparation_id=%s AND version=%s AND teacher_id=%s AND mode=%s "
            "AND status='failed'",
            (brief.preparation_id, brief.version, self.teacher_id, mode),
        )
        return cursor.rowcount == 1
