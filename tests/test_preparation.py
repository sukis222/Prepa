"""Offline workflow tests, including process loss, delivery failures and isolation."""

import asyncio
import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from test_bot import message
from test_persistence import MemoryRepository, add_student, connection, lesson

from prepa.bot import app
from prepa.bot.service import DialogService
from prepa.bot.settings import Settings
from prepa.db.repository import PostgresStore, StudentRecord
from prepa.documents.delivery import Attachment, DemoDocuments
from prepa.preparation import worker
from prepa.preparation.demo import DEMO_NOTICE, DemoBackend
from prepa.preparation.jobs import Job, JobQueue, attachments
from prepa.schemas import LessonBrief


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("homework", [0, 2, 20])
def test_demo_contract_and_student_projection(context, homework):
    brief = LessonBrief.model_validate(
        {
            **context.brief.model_dump(),
            "topics": ["Демо тема A", "Демо тема B"],
            "lesson_task_count": 20,
            "homework_task_count": homework,
            "homework_minutes": 20 if homework else 0,
        }
    )
    backend = DemoBackend()
    package = run(backend.prepare(1, brief, context.students))
    assert package.context.brief == brief
    assert len(package.assignments.lesson_assignments) == 20
    assert DEMO_NOTICE in package.review.summary
    files = [run(DemoDocuments().teacher(package))]
    for sid in brief.student_ids:
        projection = package.for_student(sid)
        assert len(projection.homework) == homework
        artifact = run(DemoDocuments().student(projection))
        assert b"PDF" in artifact.content
        assert "закрытый ответ" not in artifact.content.decode()
        assert "закрытое решение" not in artifact.content.decode()
        assert "rationale" not in artifact.content.decode()
        assert "common_errors" not in artifact.content.decode()
        assert all(
            other not in artifact.content.decode() for other in brief.student_ids if other != sid
        )
        files.append(artifact)
    assert len({f.name for f in files}) == 3
    pending = LessonBrief.model_validate({**brief.model_dump(), "confirmed": False})
    with pytest.raises(ValueError, match="Confirmation"):
        run(backend.prepare(1, pending, context.students))


def test_enqueue_atomic_retrieval_retry_and_versions():
    repo = MemoryRepository()

    def say(text, teacher=1, mode="demo"):
        return run(DialogService(None, repository=repo, job_mode=mode).respond(teacher, text))

    for mode in ("bad", "demo"):
        with pytest.raises(ValueError):
            DialogService(None, job_mode=mode)
    assert "Сначала" in say("/result").text
    add_student(repo)
    lesson(repo)
    assert not repo.data[1].get("jobs")
    repo.fail = True
    with pytest.raises(RuntimeError):
        say("/confirm")
    repo.fail = False
    assert not repo.data[1].get("jobs")
    assert "ДЕМО" in say("/help").text
    assert "очередь" in say("/confirm").text
    assert "Нет запроса" in say("/confirm").text
    assert len(repo.data[1]["jobs"]) == 1
    assert "очереди" in say("Результат").text
    assert "только после ошибки" in say("Повторить").text
    assert "Сначала" in say("/result", 2).text
    for command in ("/result 0", "/result 2", "/result a", "/result 1 extra"):
        assert "Укажите номер" in say(command).text
    key = next(iter(repo.data[1]["jobs"]))
    repo.data[1]["jobs"][key]["status"] = "running"
    assert "выполняется" in say("/result").text
    repo.data[1]["jobs"][key]["status"] = "failed"
    assert "не удалась" in say("/result").text
    assert "только после ошибки" in say("/retry", mode=None).text
    assert "очередь" in say("/retry 1").text
    repo.data[1]["jobs"][key].update(
        status="ready",
        result={
            "files": [{"name": "demo.txt", "content": base64.b64encode(b"persisted").decode()}]
        },
    )
    result = say("/result 1")
    assert result.attachments[0].content == b"persisted"
    assert "Синтетический ученик" in result.text
    assert key[0] not in result.text and "teacher" not in result.text
    original = repo.data[1]["jobs"][key]["result"]
    repo.data[1]["jobs"][key]["result"] = {
        "files": original["files"] * 2,
    }
    old = say("/result 1")
    assert "Сохранён старый формат" in old.text and not old.attachments
    assert len(repo.data[1]["jobs"][key]["result"]["files"]) == 2
    repo.data[1]["jobs"][key]["result"] = original
    for text in ("/edit", "Новая тема", "4", "/confirm"):
        say(text)
    assert len(repo.data[1]["jobs"]) == 2
    assert say("/result 1").attachments[0].content == b"persisted"
    assert "очереди" in say("/result 2").text
    assert "v2" in say("/history").text
    del repo.data[1]["jobs"]
    assert "нет задания" in say("/result").text


def test_job_store_sql_scope(context):
    conn, cursor = connection()
    store = PostgresStore(conn, 7)
    store.students = AsyncMock(return_value=())
    with pytest.raises(ValueError, match="access"):
        run(store.enqueue(context.brief, context.students, "demo"))
    store.students.return_value = tuple(StudentRecord(s, s.student_id) for s in context.students)
    with pytest.raises(ValueError):
        run(store.enqueue(context.brief, context.students[:1], "demo"))
    run(store.enqueue(context.brief, context.students, "demo"))
    assert conn.execute.call_args.args[1][2:4] == (7, "demo")
    assert run(store.job(context.brief)) is None
    cursor.fetchone.return_value = ("queued", "demo", None)
    assert run(store.job(context.brief))["status"] == "queued"
    assert "teacher_id=%s" in conn.execute.call_args.args[0]
    cursor.rowcount = 1
    assert run(store.retry(context.brief, "demo"))
    assert conn.execute.call_args.args[1][-2:] == (7, "demo")


def test_queue_claim_and_fencing(monkeypatch, package):
    conn, cursor = connection()
    monkeypatch.setattr(
        "prepa.preparation.jobs.AsyncConnection.connect", AsyncMock(return_value=conn)
    )
    queue = JobQueue("hidden", "demo")
    assert run(queue.claim()) is None
    cursor.fetchone.return_value = (
        7,
        package.context.brief.model_dump(),
        [s.model_dump() for s in package.context.students],
    )
    cursor.fetchall.return_value = [
        (package.context.brief.student_ids[0], "Максим"),
        (package.context.brief.student_ids[1], "Ольга"),
    ]
    job = run(queue.claim())
    assert job.teacher_id == 7 and job.mode == "demo"
    assert job.student_names == ("Максим", "Ольга")
    lookup = conn.execute.call_args_list[-2]
    assert "where teacher_id=%s" in lookup.args[0]
    assert lookup.args[1] == (7, list(job.brief.student_ids))
    assert "4 minutes" in conn.execute.call_args.args[0]
    cursor.rowcount = 1
    assert run(queue.finish(job, package, (Attachment("file.pdf", b"\x00\xff"),)))
    args = conn.execute.call_args.args[1]
    assert args[0] == "ready" and args[-1] == job.token
    assert attachments(args[1].obj)[0].content == b"\x00\xff"
    assert "claim_token=%s AND status='running'" in conn.execute.call_args.args[0]
    cursor.rowcount = 0
    assert not run(queue.finish(job, error="failed"))
    assert conn.execute.call_args.args[1][1] is None


def fake_queue(package):
    job = Job(7, package.context.brief, package.context.students, "token", "demo")
    return SimpleNamespace(claim=AsyncMock(return_value=job), finish=AsyncMock(return_value=True))


def test_worker_saves_before_delivery_and_recovers(package):
    queue = fake_queue(package)
    backend = SimpleNamespace(prepare=AsyncMock(return_value=package))

    async def deliver(teacher, reply):
        assert teacher == 7 and "ДЕМО" in reply.text
        queue.finish.assert_awaited_once()
        assert len(reply.attachments) == 1
        raise RuntimeError("private details")

    assert run(worker.process_one(queue, backend, DemoDocuments(), deliver, None))
    queue.finish.reset_mock()
    queue.finish.return_value = False
    delivery = AsyncMock()
    run(worker.process_one(queue, backend, DemoDocuments(), delivery, {7}))
    delivery.assert_not_awaited()  # Fenced-out old worker must not publish stale output.
    queue.claim.return_value = None
    assert not run(worker.process_one(queue, backend, DemoDocuments(), delivery, None))


@pytest.mark.parametrize("failure", ["backend", "identity", "documents", "size", "access"])
def test_worker_errors_and_access(package, failure, caplog):
    queue = fake_queue(package)
    backend = SimpleNamespace(prepare=AsyncMock(return_value=package))
    docs = DemoDocuments()
    allowed = None
    if failure == "backend":
        backend.prepare.side_effect = TimeoutError("secret")
    elif failure == "identity":
        brief = LessonBrief.model_validate({**package.context.brief.model_dump(), "version": 99})
        queue.claim.return_value = Job(7, brief, package.context.students, "token", "real")
    elif failure == "documents":
        docs = SimpleNamespace(tasks=AsyncMock(side_effect=RuntimeError("secret")))
    elif failure == "size":
        docs = SimpleNamespace(
            tasks=AsyncMock(return_value=Attachment("empty", b"")),
        )
    else:
        allowed = frozenset({999})
    deliver = AsyncMock()
    run(worker.process_one(queue, backend, docs, deliver, allowed))
    assert queue.finish.call_args.kwargs["error"] in (
        "preparation_failed",
        "access_denied",
        "preparation_timeout",
    )
    assert "secret" not in caplog.text
    if failure == "access":
        backend.prepare.assert_not_awaited()
        deliver.assert_not_awaited()
    else:
        assert not deliver.call_args.args[1].attachments


def test_worker_loop_handles_db_outage(monkeypatch):
    process = AsyncMock(side_effect=[True, RuntimeError("secret"), asyncio.CancelledError()])
    monkeypatch.setattr(worker, "process_one", process)
    sleep = AsyncMock()
    monkeypatch.setattr(worker.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        run(worker.work(None, None, None, None, None))
    sleep.assert_awaited_once_with(2)


def test_demo_settings_and_transport_arguments(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "hidden")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "*")
    monkeypatch.setenv("DATABASE_URL", "hidden")
    monkeypatch.setenv("PREPARATION_MODE", "invalid")
    with pytest.raises(ValueError, match="PREPARATION_MODE"):
        Settings.from_env()
    monkeypatch.setenv("PREPARATION_MODE", "demo")
    assert Settings.from_env().preparation_mode == "demo"
    service = SimpleNamespace(teacher_ids=None, respond=AsyncMock(return_value=app.Reply("OK")))
    run(app.create_router(service).message.handlers[0].callback(message("/result@Bot 2")))
    service.respond.assert_awaited_once_with(1, "/result 2")


def test_demo_app_worker_lifecycle(monkeypatch):
    repository = SimpleNamespace(check=AsyncMock())
    monkeypatch.setattr(app, "PostgresRepository", MagicMock(return_value=repository))
    bot = MagicMock(send_message=AsyncMock(), send_document=AsyncMock())
    bot.__aenter__ = AsyncMock(return_value=bot)
    bot.__aexit__ = AsyncMock()
    monkeypatch.setattr(app, "Bot", MagicMock(return_value=bot))
    reached = asyncio.Event()

    async def fake_work(queue, backend, docs, deliver, ids):
        await deliver(7, app.Reply("DEMO", attachments=(Attachment("demo.txt", b"test"),)))
        reached.set()
        await asyncio.Event().wait()

    async def polling(*args, **kwargs):
        await reached.wait()

    dispatcher = MagicMock(start_polling=AsyncMock(side_effect=polling))
    monkeypatch.setattr(app, "Dispatcher", MagicMock(return_value=dispatcher))
    monkeypatch.setattr(app, "work", fake_work)
    run(app.run(Settings("secret", None, "hidden", "demo")))
    bot.send_document.assert_awaited_once()


@pytest.mark.parametrize("failed", [False, True])
def test_worker_labels_each_delivery_with_names_without_sending_them_to_backend(package, failed):
    queue = fake_queue(package)
    original = queue.claim.return_value
    queue.claim.return_value = Job(
        original.teacher_id,
        original.brief,
        original.students,
        original.token,
        original.mode,
        ("Максим", "Ольга"),
    )
    backend = SimpleNamespace(prepare=AsyncMock(return_value=package))
    if failed:
        backend.prepare.side_effect = TimeoutError()
    delivery = AsyncMock()
    run(worker.process_one(queue, backend, DemoDocuments(), delivery, None))
    reply = delivery.call_args.args[1]
    assert reply.text.startswith("Ученик: Максим, Ольга\n")
    assert bool(reply.attachments) is not failed
    backend.prepare.assert_awaited_once_with(7, original.brief, original.students)
