"""Telegram transcript input stays data and respects access/file bounds."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from prepa.bot.app import create_router
from prepa.bot.service import DialogService, Reply


def incoming(text=None, filename="lesson.txt", content=b"Student: I need help.", size=30):
    async def download(document, destination):
        destination.write(content)

    return SimpleNamespace(
        text=text,
        chat=SimpleNamespace(type="private"),
        from_user=SimpleNamespace(id=1),
        document=SimpleNamespace(file_name=filename, file_size=size),
        bot=SimpleNamespace(download=AsyncMock(side_effect=download)),
        answer=AsyncMock(),
        answer_document=AsyncMock(),
    )


@pytest.mark.parametrize(
    "filename,size,pending",
    [
        ("lesson.pdf", 30, True),
        ("lesson.txt", 400001, True),
        ("lesson.txt", None, True),
        ("lesson.txt", 30, None),
    ],
)
def test_unsupported_file_not_downloaded(filename, size, pending):
    summary = SimpleNamespace(
        memory=SimpleNamespace(pending=AsyncMock(return_value=pending)), respond=AsyncMock()
    )
    message = incoming(filename=filename, size=size)
    router = create_router(DialogService(frozenset({1})), summary)
    asyncio.run(router.message.handlers[0].callback(message))
    message.bot.download.assert_not_awaited()
    summary.respond.assert_not_awaited()


def test_uploaded_transcript_not_executed_as_command():
    summary = SimpleNamespace(
        memory=SimpleNamespace(pending=AsyncMock(return_value=True)),
        respond=AsyncMock(return_value=Reply("Сводка")),
    )
    message = incoming(content=b"/confirm_summary")
    router = create_router(DialogService(frozenset({1})), summary)
    asyncio.run(router.message.handlers[0].callback(message))
    summary.respond.assert_awaited_once_with(1, "/confirm_summary", transcript_file=True)
    assert message.answer.call_args.args[0] == "Сводка"


@pytest.mark.parametrize("content", [b"\xff", b"x" * 400001])
def test_invalid_download_content_never_reaches_model(content):
    summary = SimpleNamespace(
        memory=SimpleNamespace(pending=AsyncMock(return_value=True)), respond=AsyncMock()
    )
    message = incoming(content=content)
    router = create_router(DialogService(frozenset({1})), summary)
    asyncio.run(router.message.handlers[0].callback(message))
    summary.respond.assert_not_awaited()
    assert "UTF-8" in message.answer.call_args.args[0]


def test_transcript_command_argument_preserved():
    summary = SimpleNamespace(respond=AsyncMock(return_value=Reply("Транскрипт")))
    message = incoming(text="/summarize@PrepaBot 2")
    router = create_router(DialogService(frozenset({1})), summary)
    asyncio.run(router.message.handlers[0].callback(message))
    summary.respond.assert_awaited_once_with(1, "/summarize 2", transcript_file=False)
