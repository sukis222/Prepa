"""Offline persistence contracts and failure behavior; no DB connections."""

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from prepa.bot import app
from prepa.bot.service import SESSION_ADAPTER, DialogService, Session, demo_students
from prepa.db.config import database_dsn
from prepa.db.repository import PostgresRepository, PostgresStore, StudentRecord
from prepa.schemas import LessonBrief


class MemoryRepository:
    def __init__(self):
        self.data = {}
        self.fail = False

    @asynccontextmanager
    async def transaction(self, teacher_id):
        data = deepcopy(self.data.get(teacher_id, {"state": None, "students": [], "briefs": []}))

        class Store:
            async def load_state(self):
                return data["state"]

            async def save_state(self, state):
                data["state"] = deepcopy(state)

            async def students(self):
                return tuple(data["students"])

            async def add_student(self, student):
                data["students"].append(student)

            async def save_brief(self, brief):
                data["briefs"].append(brief)

            async def enqueue(self, brief, students, mode):
                data.setdefault("jobs", {})[(brief.preparation_id, brief.version)] = {
                    "status": "queued",
                    "mode": mode,
                    "students": students,
                    "result": None,
                }

            async def job(self, brief):
                return data.get("jobs", {}).get((brief.preparation_id, brief.version))

            async def retry(self, brief, mode):
                job = await self.job(brief)
                if job and job["mode"] == mode and job["status"] == "failed":
                    job["status"] = "queued"
                    return True
                return False

        yield Store()
        if self.fail:
            raise RuntimeError("commit failed")
        self.data[teacher_id] = data


def send(repo, text, teacher=1, backend=None):
    # Re-create the service on every message: no process-local state can help it.
    return asyncio.run(DialogService(None, backend, repo).respond(teacher, text))


def add_student(repo, teacher=1):
    send(repo, "/add_student", teacher)
    send(repo, "Синтетический ученик", teacher)
    send(repo, "9 ОГЭ 1", teacher)
    return send(repo, "Сдать экзамен", teacher)


def lesson(repo):
    for text in ("/lesson", "1", "Кинематика", "60 1 4 2 20", "-"):
        send(repo, text)


def test_restart_at_every_step_and_isolation():
    repo = MemoryRepository()
    assert "PostgreSQL" in send(repo, "/start").text
    assert "/add_student" in send(repo, "/lesson").text
    assert "/add_student" in send(repo, "/students").text
    assert "добавлен" in add_student(repo).text
    assert "Синтетический" in send(repo, "/students").text
    assert "Синтетический" not in send(repo, "/students", 2).text
    lesson(repo)
    assert "Ожидает" in send(repo, "/status").text
    assert "PostgreSQL" in send(repo, "/confirm").text
    first = repo.data[1]["briefs"][0]
    assert "v1" in send(repo, "/history").text
    assert "Нет запроса" in send(repo, "/confirm").text
    assert len(repo.data[1]["briefs"]) == 1
    assert "Новая версия" in send(repo, "/edit").text
    for text in ("Динамика", "45 2 3 0 0", "Изменить задачи", "/confirm"):
        send(repo, text)
    second = repo.data[1]["briefs"][1]
    assert first.preparation_id == second.preparation_id and second.version == 2
    assert "v2" in send(repo, "/history").text
    send(repo, "/edit")
    send(repo, "/cancel")
    assert "v2" in send(repo, "/history").text
    assert "Пока пусто" in send(repo, "/history", 2).text


def test_failed_commit_preserves_retryable_draft():
    repo = MemoryRepository()
    add_student(repo)
    lesson(repo)
    before = deepcopy(repo.data)
    repo.fail = True
    with pytest.raises(RuntimeError):
        send(repo, "/confirm")
    assert repo.data == before
    repo.fail = False
    assert "PostgreSQL" in send(repo, "/confirm").text
    assert len(repo.data[1]["briefs"]) == 1


def test_backend_runs_after_commit(package):
    repo = MemoryRepository()
    brief = package.context.brief
    pending = LessonBrief.model_validate({**brief.model_dump(), "confirmed": False})
    state = Session(step="confirm", draft=pending, selected=package.context.students)
    repo.data[1] = {
        "state": {"format_version": 1, "session": SESSION_ADAPTER.dump_python(state, mode="json")},
        "students": [StudentRecord(s, s.student_id) for s in package.context.students],
        "briefs": [],
    }

    async def prepare(*args):
        assert repo.data[1]["briefs"] == [brief]
        return package

    result = send(repo, "/confirm", backend=SimpleNamespace(prepare=prepare))
    assert len(result.attachments) == 3
    repo.data[1]["state"]["format_version"] = 999
    with pytest.raises(ValueError, match="Unsupported"):
        send(repo, "/status")


def test_add_student_validation_and_memory_fallback():
    service = DialogService(None)

    def say(text):
        return asyncio.run(service.respond(1, text))

    say("Добавить ученика")
    for value in ("", "a" * 101):
        assert "Не удалось" in say(value).text
    say("Тест")
    for value in ("8 ОГЭ 1", "9 ОГЭ 4", "9 XXX 1", "wrong"):
        assert "Не удалось" in say(value).text
    say("10 егэ 3")
    for value in ("", "a" * 501):
        assert "Не удалось" in say(value).text
    assert "добавлен" in say("-").text
    assert "Тест" in say("/students").text
    assert len(service.catalogs[1]) == 4


def test_config(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    assert database_dsn() == "postgresql://localhost/test"
    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.delenv("PGHOST", raising=False)
    with pytest.raises(ValueError):
        database_dsn()
    monkeypatch.setenv("PGHOST", "postgres")
    assert "host=postgres" in database_dsn()


def connection():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone = AsyncMock(return_value=None)
    cursor.fetchall = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value=cursor)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    return conn, cursor


def test_repository_transaction_and_schema_check(monkeypatch):
    conn, cursor = connection()
    monkeypatch.setattr("prepa.db.repository.AsyncConnection.connect", AsyncMock(return_value=conn))
    repo = PostgresRepository("hidden")
    for row in (None, (1,)):
        cursor.fetchone.return_value = row
        with pytest.raises(RuntimeError):
            asyncio.run(repo.check())
    cursor.fetchone.return_value = (3,)
    asyncio.run(repo.check())

    async def use():
        async with repo.transaction(123) as store:
            assert store.teacher_id == 123

    asyncio.run(use())
    assert "FOR UPDATE" in conn.execute.call_args.args[0]
    assert conn.execute.call_args.args[1] == (123,)


def test_store_state_and_students():
    conn, cursor = connection()
    store = PostgresStore(conn, 123)
    assert asyncio.run(store.load_state()) is None
    cursor.fetchone.return_value = ({"format_version": 1},)
    assert asyncio.run(store.load_state()) == {"format_version": 1}
    asyncio.run(store.save_state({"format_version": 1}))
    assert conn.execute.call_args.args[1][0] == 123
    student = demo_students()[0]
    cursor.fetchall.return_value = [(student.model_dump(), "Test", "Goal")]
    assert asyncio.run(store.students()) == (StudentRecord(student, "Test", "Goal"),)
    asyncio.run(store.add_student(StudentRecord(student, "Test")))
    assert conn.execute.call_args.args[1][1] == 123


def test_save_brief_ownership_membership_and_immutability(context):
    conn, cursor = connection()
    store = PostgresStore(conn, 123)
    brief = context.brief
    profiles = tuple(StudentRecord(s, s.student_id) for s in context.students)
    store.students = AsyncMock(return_value=profiles)
    pending = LessonBrief.model_validate({**brief.model_dump(), "confirmed": False})
    with pytest.raises(ValueError, match="confirmed"):
        asyncio.run(store.save_brief(pending))
    store.students.return_value = ()
    with pytest.raises(ValueError, match="Student access"):
        asyncio.run(store.save_brief(brief))
    store.students.return_value = profiles
    with pytest.raises(ValueError, match="Preparation access"):
        asyncio.run(store.save_brief(brief))
    cursor.fetchone.return_value = (123,)
    cursor.fetchall.return_value = [("outsider",)]
    with pytest.raises(ValueError, match="membership"):
        asyncio.run(store.save_brief(brief))
    cursor.fetchall.return_value = [(s.student_id,) for s in context.students]
    changed = {**brief.model_dump(), "teacher_notes": "Changed"}
    cursor.fetchone.side_effect = [(123,), (changed,)]
    with pytest.raises(ValueError, match="immutable"):
        asyncio.run(store.save_brief(brief))
    cursor.fetchone.side_effect = [(123,), (brief.model_dump(),)]
    asyncio.run(store.save_brief(brief))
    cursor.fetchone.side_effect = [(123,), None]
    cursor.fetchall.return_value = []
    asyncio.run(store.save_brief(brief))
    assert "INSERT INTO preparation_versions" in conn.execute.call_args.args[0]


def test_startup_failure_hides_credentials(monkeypatch):
    monkeypatch.setattr(app, "load_dotenv", MagicMock())
    monkeypatch.setattr(app.Settings, "from_env", MagicMock())
    monkeypatch.setattr(app, "run", AsyncMock(side_effect=RuntimeError("secret")))
    with pytest.raises(SystemExit) as error:
        app.main()
    assert "secret" not in str(error.value)
