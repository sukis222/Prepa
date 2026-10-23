"""Bot scenarios are exercised offline; no Telegram, paid models or database."""

import asyncio
import json
import runpy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from prepa.agents.runtime import AgentResponseError, InsufficientMaterialsError
from prepa.bot import app
from prepa.bot.service import DialogService, Reply, Session, summary
from prepa.bot.settings import Settings
from prepa.schemas import GenerationFailure, LessonBrief, LessonPackage


def say(service, text, user=1):
    return asyncio.run(service.respond(user, text))


def draft(service, topics="Кинематика", students="1,2", format_text="60 1 4 2 20"):
    say(service, "/lesson")
    say(service, students)
    say(service, topics)
    say(service, format_text)
    return say(service, "-")


def test_complete_flow_and_versions():
    service = DialogService(frozenset({1, 2}))
    assert "Демонстрационный" in say(service, "/start").text
    assert "demo-a" in say(service, "Ученики").text
    assert "Ожидает" in draft(service).text
    pending = service.sessions[1].draft
    assert pending and not pending.confirmed
    assert "не подключены" in say(service, "Подтвердить").text
    first = service.sessions[1].history[-1]
    assert first.confirmed
    assert "Нет запроса" in say(service, "/confirm").text
    assert len(service.sessions[1].history) == 1
    assert "v1" in say(service, "История").text
    assert "Подтверждено" in say(service, "Статус").text
    assert "Пока пусто" in say(service, "/history", user=2).text
    assert "Новая версия" in say(service, "Правки").text
    say(service, "Динамика")
    say(service, "90 3 5 0 0")
    say(service, "Усложнить вторую задачу")
    assert "Ожидает" in say(service, "/status").text
    say(service, "/confirm")
    second = service.sessions[1].history[-1]
    assert second.preparation_id == first.preparation_id and second.version == 2
    assert second.topics == ("Динамика",) and second.homework_task_count == 0
    assert second.teacher_notes == "Усложнить вторую задачу"
    say(service, "/edit")
    say(service, "Отмена")
    assert len(service.sessions[1].history) == 2
    assert service.sessions[1].draft is None
    assert service.sessions[1].step == "idle"
    draft(service, students="3")
    assert service.sessions[1].draft.exam == "ege"
    assert service.sessions[1].draft.preparation_id != first.preparation_id


def test_help_empty_states_permissions_and_retention():
    service = DialogService(frozenset({1}))
    assert "Доступ" in say(service, "/start", user=9).text
    assert 9 not in service.sessions
    assert "Сначала" in say(service, "/edit").text
    assert "ещё не составлен" in say(service, "/status").text
    assert "Начните" in say(service, "что-то").text
    assert "Неизвестная" in say(service, "/unknown").text
    assert "не подключена" in say(service, "/homework").text
    for _ in range(22):
        draft(service, students="1")
        say(service, "/confirm")
    assert len(service.sessions[1].history) == 20


@pytest.mark.parametrize("selection", ["", "x", "0", "4", "-1", "1,1", "1,2,3", "1,3"])
def test_bad_selection_does_not_advance(selection):
    service = DialogService(frozenset({1}))
    say(service, "/lesson")
    assert "Не удалось" in say(service, selection).text
    assert service.sessions[1].step == "students"


@pytest.mark.parametrize("topics", ["", ";", "A;A", "A" * 161, ";".join(map(str, range(9)))])
def test_bad_topics_do_not_advance(topics):
    service = DialogService(frozenset({1}))
    say(service, "/lesson")
    say(service, "1")
    assert "Не удалось" in say(service, topics).text
    assert service.sessions[1].step == "topics"


@pytest.mark.parametrize(
    "values",
    ["60 1 4 2", "x", "60 0 4 2 20", "0 1 4 2 20", "60 1 1 2 20", "60 1 4 0 20"],
)
def test_bad_format_can_be_corrected(values):
    service = DialogService(frozenset({1}))
    say(service, "/lesson")
    say(service, "1")
    say(service, "A;B")
    assert "Не удалось" in say(service, values).text
    assert service.sessions[1].draft is None
    say(service, "60 2 4 2 20")
    assert service.sessions[1].step == "notes"
    assert "Не удалось" in say(service, "x" * 1001).text
    assert "Не удалось" in say(service, " ").text
    assert "Ожидает" in say(service, "Проверить перевод единиц").text
    assert "Подтвердить" in say(service, "да").text
    assert not service.sessions[1].history


def test_backend_only_runs_after_confirmation_and_returns_student_projection(package):
    backend = SimpleNamespace(prepare=AsyncMock(return_value=package))
    service = DialogService(frozenset({1}), backend)
    brief = package.context.brief
    pending = LessonBrief.model_validate({**brief.model_dump(), "confirmed": False})
    service.sessions[1] = Session(step="confirm", draft=pending, selected=package.context.students)
    say(service, "/status")
    backend.prepare.assert_not_awaited()
    reply = say(service, "/confirm")
    backend.prepare.assert_awaited_once_with(1, brief, package.context.students)
    assert len(reply.attachments) == 3
    teacher = json.loads(reply.attachments[0].content)
    assert LessonPackage.model_validate(teacher) == package
    student = json.loads(reply.attachments[1].content)
    assert "context" not in student
    assert "answer" not in student["lesson_assignments"][0]
    assert "Содержание прошло" in reply.text
    assert "Нет запроса" in say(service, "/confirm").text
    backend.prepare.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (TimeoutError(), "Время"),
        (AgentResponseError("private"), "не прошли"),
        (ValueError("private"), "не прошли"),
        (
            InsufficientMaterialsError(
                GenerationFailure(status="insufficient_material", missing_topics=("A",), reason="B")
            ),
            "Недостаточно",
        ),
    ],
)
def test_backend_errors_are_safe(error, message):
    service = DialogService(frozenset({1}), SimpleNamespace(prepare=AsyncMock(side_effect=error)))
    draft(service)
    reply = say(service, "/confirm")
    assert message in reply.text and "private" not in reply.text
    assert not reply.attachments


def test_wrong_backend_identity_is_rejected(package):
    service = DialogService(
        frozenset({1}), SimpleNamespace(prepare=AsyncMock(return_value=package))
    )
    draft(service)
    assert "не прошли" in say(service, "/confirm").text


def test_status_summary_levels():
    service = DialogService(frozenset({1}))
    draft(service, format_text="60 2 4 2 20")
    assert "средний" in summary(service.sessions[1].draft)


def test_settings(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/prepa_test")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        Settings.from_env()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret")
    for value in ("", "abc", "1,", "0", "-1", "*,1"):
        monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", value)
        with pytest.raises(ValueError):
            Settings.from_env()
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "1, 2,1")
    settings = Settings.from_env()
    assert settings.teacher_ids == frozenset({1, 2})
    assert "secret" not in repr(settings)
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", " * ")
    assert Settings.from_env().teacher_ids is None


def test_public_access_keeps_sessions_separate():
    service = DialogService(None)
    assert "123" in say(service, "/id", user=123).text
    assert "456" in say(service, "/id", user=456).text
    say(service, "/lesson", user=123)
    assert service.sessions[123].step == "students"
    assert service.sessions[456].step == "idle"
    incoming = message(text="/id", user_id=789)
    handler = app.create_router(service).message.handlers[0].callback
    asyncio.run(handler(incoming))
    assert "789" in incoming.answer.call_args.args[0]


def message(text="/start", chat_type="private", user_id=1):
    return SimpleNamespace(
        text=text,
        chat=SimpleNamespace(type=chat_type),
        from_user=SimpleNamespace(id=user_id) if user_id else None,
        answer=AsyncMock(),
        answer_document=AsyncMock(),
    )


@pytest.mark.parametrize(
    ("incoming", "expected"),
    [
        (message(chat_type="group"), "личном чате"),
        (message(user_id=None), "личном чате"),
        (message(user_id=2), "Доступ"),
        (message(text=None), "только текст"),
        (message(text="/start@PrepaBot invite"), "Демонстрационный"),
        (message(text="Привет"), "Начните"),
    ],
)
def test_aiogram_handler(incoming, expected):
    router = app.create_router(DialogService(frozenset({1})))
    asyncio.run(router.message.handlers[0].callback(incoming))
    assert expected in incoming.answer.call_args.args[0]


def test_transport_sends_attachments_and_sanitizes_errors(caplog):
    from prepa.bot.service import Attachment

    service = SimpleNamespace(
        teacher_ids={1},
        respond=AsyncMock(return_value=Reply("Готово", attachments=(Attachment("x.json", b"{}"),))),
    )
    handler = app.create_router(service).message.handlers[0].callback
    incoming = message()
    asyncio.run(handler(incoming))
    assert incoming.answer_document.call_args.args[0].filename == "x.json"
    service.respond.side_effect = RuntimeError("secret personal details")
    asyncio.run(handler(incoming))
    assert "Не удалось" in incoming.answer.call_args.args[0]
    assert "RuntimeError" in caplog.text and "secret" not in caplog.text


def test_polling_lifecycle(monkeypatch):
    repository = MagicMock()
    repository.check = AsyncMock()
    monkeypatch.setattr(app, "PostgresRepository", MagicMock(return_value=repository))
    bot = MagicMock()
    bot.__aenter__ = AsyncMock(return_value=bot)
    bot.__aexit__ = AsyncMock()
    dispatcher = MagicMock()
    dispatcher.start_polling = AsyncMock()
    monkeypatch.setattr(app, "Bot", MagicMock(return_value=bot))
    monkeypatch.setattr(app, "Dispatcher", MagicMock(return_value=dispatcher))
    asyncio.run(app.run(Settings("secret", frozenset({1}))))
    dispatcher.start_polling.assert_awaited_once_with(
        bot, allowed_updates=["message"], handle_as_tasks=False, close_bot_session=False
    )
    bot.__aexit__.assert_awaited_once()


def test_entrypoints(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/prepa_test")
    monkeypatch.setattr(app, "load_dotenv", MagicMock())
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="TELEGRAM_BOT_TOKEN"):
        app.main()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "1")
    runner = AsyncMock()
    monkeypatch.setattr(app, "run", runner)
    app.main()
    runner.assert_awaited_once()
    main = MagicMock()
    monkeypatch.setattr(app, "main", main)
    runpy.run_module("prepa.bot", run_name="__main__")
    main.assert_called_once()
