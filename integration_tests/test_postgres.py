"""Explicit opt-in tests on a separate PostgreSQL database, outside ordinary pytest."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from prepa.bot.service import DialogService
from prepa.db.migrate import migrate
from prepa.db.repository import PostgresRepository, StudentRecord
from prepa.schemas import LessonBrief, StudentProfile


@pytest.fixture(scope="module")
def dsn():
    value = os.environ.get("PREPA_TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set PREPA_TEST_DATABASE_URL to an isolated prepa_test* database")
    assert conninfo_to_dict(value).get("dbname", "").startswith("prepa_test")
    directory = Path(__file__).resolve().parents[1] / "migrations"
    migrate(value, directory)
    migrate(value, directory)  # Re-running migrations must preserve the existing schema/data.
    return value


def teacher_id():
    return uuid4().int % (2**50) + 1


def test_real_restart_and_new_version(dsn):
    teacher = teacher_id()

    def say(text):
        return asyncio.run(
            DialogService(None, repository=PostgresRepository(dsn)).respond(teacher, text)
        )

    for text in (
        "/add_student",
        "Synthetic pupil",
        "9 ОГЭ 1",
        "-",
        "/lesson",
        "1",
        "Кинематика",
        "60 1 4 2 20",
        "-",
    ):
        say(text)
    # Separate Python process reloads the exact unconfirmed draft from the database.
    code = (
        "import asyncio,os; from prepa.bot.service import DialogService; "
        "from prepa.db.repository import PostgresRepository; "
        "repo=PostgresRepository(os.environ['PREPA_TEST_DATABASE_URL']); "
        "s=DialogService(None,repository=repo); "
        f"print(asyncio.run(s.respond({teacher},'/status')).text)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert "Ожидает подтверждения" in result.stdout
    assert "PostgreSQL" in say("/confirm").text
    assert "Нет запроса" in say("/confirm").text
    for text in ("/edit", "Динамика", "60 2 3 0 0", "Новая версия", "/confirm"):
        say(text)
    result = subprocess.run(
        [sys.executable, "-c", code.replace("'/status'", "'/history'")],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "v1" in result.stdout and "v2" in result.stdout
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            "SELECT preparation_id, version FROM preparation_versions "
            "WHERE teacher_id=%s ORDER BY version",
            (teacher,),
        ).fetchall()
        assert len(rows) == 2 and rows[0][0] == rows[1][0]
    outsider = asyncio.run(
        DialogService(None, repository=PostgresRepository(dsn)).respond(teacher_id(), "/students")
    )
    assert "Synthetic pupil" not in outsider.text


def test_rollback_ownership_immutable_version(dsn):
    owner, stranger = teacher_id(), teacher_id()
    repo = PostgresRepository(dsn)
    student = StudentProfile(student_id=uuid4().hex, grade=9, exam="oge")
    brief = LessonBrief(
        preparation_id=uuid4().hex,
        version=1,
        student_ids=(student.student_id,),
        exam="oge",
        topics=("Motion",),
        confirmed=True,
    )

    async def scenario():
        await repo.check()
        with pytest.raises(RuntimeError):
            async with repo.transaction(owner) as store:
                await store.add_student(StudentRecord(student, "Rollback pupil"))
                await store.save_state({"test": "rollback"})
                raise RuntimeError("simulate failure before commit")
        async with repo.transaction(owner) as store:
            assert await store.students() == ()
            assert await store.load_state() is None
            await store.add_student(StudentRecord(student, "Synthetic pupil"))
            await store.save_brief(brief)
        with pytest.raises(ValueError, match="Student access"):
            async with repo.transaction(stranger) as store:
                await store.save_brief(brief)
        async with repo.transaction(owner) as store:
            await store.save_brief(brief)  # Idempotent retry, not a duplicate version.
        changed = LessonBrief.model_validate({**brief.model_dump(), "teacher_notes": "Changed"})
        with pytest.raises(ValueError, match="immutable"):
            async with repo.transaction(owner) as store:
                await store.save_brief(changed)

    asyncio.run(scenario())
