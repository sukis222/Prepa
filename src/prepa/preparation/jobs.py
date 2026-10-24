"""Persistent jobs: bounded leases, fenced completion, and teacher-scoped retrieval."""

import base64
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from prepa.documents.delivery import Attachment
from prepa.schemas import LessonBrief, LessonPackage, StudentProfile, TaskWorksheet


@dataclass(frozen=True)
class Job:
    teacher_id: int
    brief: LessonBrief
    students: tuple[StudentProfile, ...]
    token: str
    mode: str
    student_names: tuple[str, ...] = ()


class JobQueue:
    def __init__(self, dsn: str, mode: str) -> None:
        self.dsn, self.mode = dsn, mode

    async def claim(self) -> Job | None:
        async with await AsyncConnection.connect(self.dsn, connect_timeout=10) as conn:
            # A killed worker can be reclaimed, but never retried forever.
            await conn.execute(
                "UPDATE preparation_jobs SET status='failed', error_code='interrupted' "
                "WHERE mode=%s AND status='running' AND lease_until < now() AND attempts >= 3",
                (self.mode,),
            )
            row = await (
                await conn.execute(
                    "SELECT j.teacher_id, v.brief, j.students FROM preparation_jobs j "
                    "JOIN preparation_versions v USING(preparation_id, version, teacher_id) "
                    "WHERE j.mode=%s AND (j.status='queued' OR "
                    "(j.status='running' AND j.lease_until < now() AND j.attempts < 3)) "
                    "ORDER BY j.created_at LIMIT 1 FOR UPDATE OF j SKIP LOCKED",
                    (self.mode,),
                )
            ).fetchone()
            if row is None:
                return None
            brief = LessonBrief.model_validate(row[1])
            students = tuple(StudentProfile.model_validate(s) for s in row[2])
            name_rows = await (
                await conn.execute(
                    "select student_id, display_name from students "
                    "where teacher_id=%s and student_id = any(%s)",
                    (row[0], list(brief.student_ids)),
                )
            ).fetchall()
            names: dict[str, str] = dict(name_rows)
            student_names = tuple(names.get(sid, "Ученик") for sid in brief.student_ids)
            token = str(uuid4())
            await conn.execute(
                "UPDATE preparation_jobs SET status='running', attempts=attempts+1, "
                "lease_until=now()+interval '5 minutes', claim_token=%s "
                "WHERE preparation_id=%s AND version=%s AND teacher_id=%s",
                (token, brief.preparation_id, brief.version, row[0]),
            )
            return Job(row[0], brief, students, token, self.mode, student_names)

    async def finish(
        self,
        job: Job,
        package: LessonPackage | TaskWorksheet | None = None,
        files: tuple[Attachment, ...] = (),
        error: str | None = None,
    ) -> bool:
        result = (
            None
            if package is None
            else {
                "package": package.model_dump(mode="json"),
                "package_kind": "source_worksheet"
                if isinstance(package, TaskWorksheet)
                else "lesson",
                "files": [
                    {"name": f.name, "content": base64.b64encode(f.content).decode()} for f in files
                ],
            }
        )
        async with await AsyncConnection.connect(self.dsn, connect_timeout=10) as conn:
            cursor = await conn.execute(
                "UPDATE preparation_jobs SET status=%s, result=%s, error_code=%s, lease_until=NULL "
                "WHERE preparation_id=%s AND version=%s AND teacher_id=%s "
                "AND claim_token=%s AND status='running'",
                (
                    "ready" if result else "failed",
                    Jsonb(result) if result else None,
                    error,
                    job.brief.preparation_id,
                    job.brief.version,
                    job.teacher_id,
                    job.token,
                ),
            )
            return cursor.rowcount == 1


def attachments(result: dict[str, Any]) -> tuple[Attachment, ...]:
    return tuple(
        Attachment(f["name"], base64.b64decode(f["content"], validate=True))
        for f in result["files"]
    )
