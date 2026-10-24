"""Transcript-to-confirmation flow with synthetic pupils and no external calls."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from prepa.agents.runtime import AgentResponseError
from prepa.bot.lesson_summary import SummaryDialog, summary_text, transcript_turns
from prepa.llm import LLMError
from prepa.schemas import SourceTask, TaskWorksheet
from prepa.schemas.lesson_summary import LessonSummary
from prepa.schemas.source import source_task_digest


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def dialog(context):
    worksheet = TaskWorksheet(
        preparation_id=context.brief.preparation_id,
        version=context.brief.version,
        student_ids=(context.brief.student_ids[0],),
        exam=context.brief.exam,
        topics=context.brief.topics,
        title="Работа газа",
        tasks=(
            SourceTask(
                id="task1",
                statement_exact="Найдите работу газа.",
                source_url="https://example.test/task1",
                sha256=source_task_digest("Найдите работу газа."),
            ),
        ),
    )
    summary = LessonSummary(
        preparation_id=worksheet.preparation_id,
        version=worksheet.version,
        student_id=worksheet.student_ids[0],
        input_digest="a" * 64,
        overview="Обсудили работу газа.",
        insufficient_evidence=False,
        observations=(
            {
                "topic": "Работа газа",
                "status": "difficulty",
                "finding": "Повторить знак работы.",
                "evidence": ({"turn_id": "turn-1", "quote": "Не понимаю знак."},),
                "task_ids": ("task1",),
            },
        ),
        next_steps=(
            {
                "topic": "Работа газа",
                "action": "Разобрать расширение газа.",
                "basis_turn_ids": ("turn-1",),
            },
        ),
        uncertainty=("Не проверено самостоятельное решение.",),
    )
    memory = SimpleNamespace(
        select_lesson=AsyncMock(return_value=worksheet),
        set_pending=AsyncMock(),
        pending=AsyncMock(return_value=worksheet),
        clear_pending=AsyncMock(),
        save_proposal=AsyncMock(),
        confirm_latest=AsyncMock(return_value=summary),
        knowledge=AsyncMock(return_value=(summary,)),
    )
    agent = SimpleNamespace(summarize=AsyncMock(return_value=summary))
    return SimpleNamespace(
        service=SummaryDialog(memory, agent),
        memory=memory,
        agent=agent,
        worksheet=worksheet,
        summary=summary,
    )


@pytest.mark.parametrize("command", ["/summarize", "/summarize abc", "/summarize 1 2"])
def test_invalid_lesson_command_no_model(dialog, command):
    reply = run(dialog.service.respond(81, command))
    assert "/summarize N" in reply.text
    dialog.agent.summarize.assert_not_called()
    dialog.memory.select_lesson.assert_not_called()


def test_select_lesson_starts_persisted_transcript_flow(dialog):
    reply = run(dialog.service.respond(81, "/summarize 2"))
    dialog.memory.select_lesson.assert_awaited_once_with(81, 2)
    dialog.memory.set_pending.assert_awaited_once_with(81, dialog.worksheet)
    dialog.agent.summarize.assert_not_called()
    assert "OpenRouter" in reply.text
    assert "Полный транскрипт не сохраняется" in reply.text
    assert "/cancel" in reply.text


@pytest.mark.parametrize(
    "command", ["/cancel", "/lesson", "Новое занятие", "Отмена", "Добавить ученика"]
)
def test_other_commands_cancel_pending_and_pass_through(dialog, command):
    assert run(dialog.service.respond(81, command)) is None
    dialog.memory.clear_pending.assert_awaited_once_with(81)
    dialog.agent.summarize.assert_not_called()


def test_regular_text_without_pending_is_not_intercepted(dialog):
    dialog.memory.pending.return_value = None
    assert run(dialog.service.respond(81, "Термодинамика")) is None
    dialog.agent.summarize.assert_not_called()


def test_transcript_proposal_preserves_lesson_and_requires_confirmation(dialog):
    reply = run(
        dialog.service.respond(81, "Ученик: Не понимаю знак.\nПреподаватель: Разберём расширение.")
    )
    context = dialog.agent.summarize.call_args.args[0]
    assert context.student_id == dialog.worksheet.student_ids[0]
    assert context.preparation_id == dialog.worksheet.preparation_id
    assert context.version == dialog.worksheet.version
    assert context.tasks[0].statement == dialog.worksheet.tasks[0].statement_exact
    assert [t.speaker for t in context.transcript] == ["student", "teacher"]
    dialog.memory.save_proposal.assert_awaited_once_with(81, context, dialog.summary)
    dialog.memory.confirm_latest.assert_not_called()
    assert "проверьте перед сохранением" in reply.text
    assert "/confirm_summary" in reply.text
    assert "Нужно повторить" in reply.text
    assert "Основание:" in reply.text
    assert "На следующие занятия:" in reply.text
    assert "Неясно:" in reply.text


@pytest.mark.parametrize("has_summary", [True, False])
def test_confirmation_is_explicit(dialog, has_summary):
    dialog.memory.confirm_latest.return_value = dialog.summary if has_summary else None
    reply = run(dialog.service.respond(81, "/confirm_summary"))
    dialog.memory.confirm_latest.assert_awaited_once_with(81)
    assert ("Итоги сохранены" if has_summary else "Нет итогов") in reply.text
    dialog.agent.summarize.assert_not_called()


@pytest.mark.parametrize("command", ["/knowledge", "/knowledge a", "/knowledge 1 2"])
def test_invalid_knowledge_command_no_model(dialog, command):
    reply = run(dialog.service.respond(81, command))
    assert "/knowledge N" in reply.text
    dialog.memory.knowledge.assert_not_called()
    dialog.agent.summarize.assert_not_called()


def test_knowledge_returns_only_memory_records(dialog):
    reply = run(dialog.service.respond(81, "/knowledge 1"))
    dialog.memory.knowledge.assert_awaited_once_with(81, 1)
    assert "Занятие 1" in reply.text
    assert dialog.summary.overview in reply.text
    dialog.agent.summarize.assert_not_called()
    dialog.memory.knowledge.return_value = ()
    assert "пока нет" in run(dialog.service.respond(81, "/knowledge 1")).text


@pytest.mark.parametrize("command", ["/summarize 0", "/knowledge 0"])
def test_inaccessible_lesson_or_student_is_safe(dialog, command):
    error = ValueError("private DSN or pupil data must not appear")
    dialog.memory.select_lesson.side_effect = error
    dialog.memory.knowledge.side_effect = error
    reply = run(dialog.service.respond(81, command))
    assert "Проверьте номер" in reply.text
    assert "private" not in reply.text
    dialog.agent.summarize.assert_not_called()


@pytest.mark.parametrize("text", ["", "WEBVTT\n\n1\n00:00:00 --> 00:00:02", "x" * 100001])
def test_invalid_transcript_never_calls_model(dialog, text):
    reply = run(dialog.service.respond(81, text))
    assert "Проверьте номер" in reply.text
    dialog.agent.summarize.assert_not_called()
    dialog.memory.save_proposal.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        AgentResponseError("private provider details"),
        LLMError("private provider details"),
        TimeoutError("private provider details"),
    ],
)
def test_model_errors_do_not_persist_or_leak(dialog, error):
    dialog.agent.summarize.side_effect = error
    reply = run(dialog.service.respond(81, "Ученик: Не понимаю знак."))
    assert "Модель не вернула" in reply.text
    assert "private" not in reply.text
    dialog.memory.save_proposal.assert_not_called()
    dialog.memory.confirm_latest.assert_not_called()


def test_vtt_unknown_and_named_speakers():
    text = (
        "\ufeffWEBVTT\n\n1\n00:00:00.000 --> 00:00:02.000\n"
        "Неопознанная реплика.\nStudent: Не понимаю.\nTeacher: Рассмотрим пример."
    )
    turns = transcript_turns(text)
    assert [t.speaker for t in turns] == ["unknown", "student", "teacher"]
    assert [t.turn_id for t in turns] == ["turn-1", "turn-2", "turn-3"]
    assert turns[0].text == "Неопознанная реплика."
    assert all("-->" not in t.text and "WEBVTT" not in t.text for t in turns)


def test_long_turn_split_and_excessive_turns_rejected():
    turns = transcript_turns("Ученик: " + "я" * 6001)
    assert [len(t.text) for t in turns] == [6000, 1]
    assert all(t.speaker == "student" for t in turns)
    with pytest.raises(ValueError):
        transcript_turns("реплика\n" * 1001)


def test_summary_labels_for_understood_and_unclear(dialog):
    data = dialog.summary.model_dump()
    first = data["observations"][0]
    data["observations"] = [dict(first, status="understood"), dict(first, status="unclear")]
    text = summary_text(LessonSummary.model_validate(data))
    assert "Разобрался" in text and "Недостаточно данных" in text


def test_summary_without_optional_sections(dialog):
    data = dialog.summary.model_dump()
    data.update(observations=(), next_steps=(), uncertainty=())
    assert summary_text(LessonSummary.model_validate(data)) == dialog.summary.overview
