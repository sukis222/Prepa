"""aiogram transport; domain dialogs can be tested without Telegram."""

import asyncio
import logging
import os
from contextlib import suppress
from io import BytesIO
from pathlib import Path

from aiogram import Bot, Dispatcher, Router
from aiogram.types import BufferedInputFile, KeyboardButton, Message, ReplyKeyboardMarkup
from dotenv import load_dotenv

from prepa.agents.summarizer import LessonSummarizerAgent
from prepa.bot.lesson_summary import SummaryDialog
from prepa.bot.service import DialogService, Reply
from prepa.bot.settings import Settings
from prepa.db.lesson_memory import PostgresLessonMemory
from prepa.db.repository import PostgresRepository
from prepa.documents.latex import LatexDocuments
from prepa.documents.source import SourceDocuments
from prepa.llm import OpenRouterLLM, OpenRouterSettings
from prepa.preparation.demo import DemoBackend
from prepa.preparation.jobs import JobQueue
from prepa.preparation.source import SourceSelectionBackend
from prepa.preparation.worker import work
from prepa.task_bank.reshai import ReshaiSource

logger = logging.getLogger(__name__)


def create_router(service: DialogService, summary_service: SummaryDialog | None = None) -> Router:
    router = Router(name="prepa")

    @router.message()
    async def handle_message(message: Message) -> None:
        if message.chat.type != "private" or message.from_user is None:
            await message.answer("Работа с учениками доступна только в личном чате с ботом.")
            return
        if service.teacher_ids is not None and message.from_user.id not in service.teacher_ids:
            await message.answer("Доступ не настроен. Обратитесь к администратору.")
            return
        text = message.text
        transcript_file = False
        if text is None and summary_service is not None and message.document:
            document = message.document
            if (
                Path(document.file_name or "").suffix.lower() not in (".txt", ".srt", ".vtt")
                or document.file_size is None
                or document.file_size > 400000
                or await summary_service.memory.pending(message.from_user.id) is None
            ):
                await message.answer(
                    "Для транскрипта сначала /summarize N, затем TXT/SRT/VTT до 400 КБ."
                )
                return
            buffer = BytesIO()
            try:
                transport_bot = message.bot
                if transport_bot is None:
                    raise ValueError("missing transport")
                await transport_bot.download(document, destination=buffer)
                if buffer.tell() > 400000:
                    raise ValueError("transcript size")
                text = buffer.getvalue().decode("utf-8-sig")
                transcript_file = True
            except (ValueError, UnicodeError):
                await message.answer("Нужен текстовый файл UTF-8 до 400 КБ. Файл не сохранён.")
                return
        if text is None:
            await message.answer(
                "Пока принимаю только текст. Файл не сохранён; проверка ДЗ ещё не подключена."
            )
            return
        # Accept /command@botname and /start deep links without changing free text.
        if text.startswith("/") and not transcript_file:
            command, *arguments = text.split(maxsplit=1)
            command = command.split("@")[0].lower()
            text = command
            if command in ("/result", "/retry", "/summarize", "/knowledge") and arguments:
                text += " " + arguments[0]
        try:
            reply = (
                await summary_service.respond(
                    message.from_user.id, text, transcript_file=transcript_file
                )
                if summary_service is not None
                else None
            )
            if reply is None:
                reply = await service.respond(message.from_user.id, text)
        except Exception as error:
            # Provider errors may contain tokens or pupils' data: never log their text.
            logger.error("Dialog failed (%s)", type(error).__name__)
            await message.answer(
                "Не удалось обработать запрос. /status — состояние; /cancel — отмена."
            )
            return
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=button) for button in row] for row in reply.buttons],
            resize_keyboard=True,
        )
        # 2000 code points fit Telegram's 4096 UTF-16-unit limit even with emoji.
        for offset in range(0, len(reply.text), 2000):
            await message.answer(reply.text[offset : offset + 2000], reply_markup=keyboard)
        for attachment in reply.attachments:
            await message.answer_document(
                BufferedInputFile(attachment.content, filename=attachment.name)
            )

    return router


async def run(settings: Settings) -> None:
    repository = PostgresRepository(settings.database_url)
    await repository.check()
    mode = settings.preparation_mode if settings.preparation_mode != "off" else None
    service = DialogService(settings.teacher_ids, repository=repository, job_mode=mode)
    dispatcher = Dispatcher()
    async with Bot(settings.token) as bot:
        llm = OpenRouterLLM(OpenRouterSettings.from_env()) if mode == "real" else None
        summary_service = (
            SummaryDialog(
                PostgresLessonMemory(settings.database_url),
                LessonSummarizerAgent(llm),
                llm.check_model,
            )
            if llm is not None
            else None
        )
        dispatcher.include_router(create_router(service, summary_service))

        async def deliver(teacher_id: int, reply: Reply) -> None:
            await bot.send_message(teacher_id, reply.text)
            for attachment in reply.attachments:
                await bot.send_document(
                    teacher_id, BufferedInputFile(attachment.content, filename=attachment.name)
                )

        worker = (
            asyncio.create_task(
                work(
                    JobQueue(settings.database_url, mode),
                    SourceSelectionBackend(
                        llm,
                        corpus_path=(
                            Path(settings.source_corpus_path)
                            if settings.source_provider == "local"
                            else None
                        ),
                        source=ReshaiSource() if settings.source_provider == "reshai" else None,
                        check_model=llm.check_model,
                    )
                    if llm
                    else DemoBackend(),
                    (SourceDocuments if llm else LatexDocuments)(
                        engine=os.environ.get("LATEX_ENGINE", "xelatex"),
                        font=os.environ.get("LATEX_FONT", "DejaVu Serif"),
                    ),
                    deliver,
                    settings.teacher_ids,
                )
            )
            if mode
            else None
        )
        try:
            await dispatcher.start_polling(
                bot,
                allowed_updates=["message"],
                handle_as_tasks=False,
                close_bot_session=False,
            )
        finally:
            if worker is not None:
                worker.cancel()
                with suppress(asyncio.CancelledError):
                    await worker
            if llm is not None:
                await llm.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    try:
        settings = Settings.from_env()
    except ValueError as error:
        raise SystemExit(str(error)) from None
    try:
        asyncio.run(run(settings))
    except Exception as error:
        raise SystemExit(
            f"Не удалось запустить бот ({type(error).__name__}). "
            "Проверьте PostgreSQL, миграции и настройки Telegram."
        ) from None
