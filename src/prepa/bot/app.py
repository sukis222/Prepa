"""aiogram transport; domain dialogs can be tested without Telegram."""

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher, Router
from aiogram.types import BufferedInputFile, KeyboardButton, Message, ReplyKeyboardMarkup
from dotenv import load_dotenv

from prepa.bot.service import DialogService, Reply
from prepa.bot.settings import Settings
from prepa.db.repository import PostgresRepository
from prepa.documents.delivery import DemoDocuments
from prepa.preparation.demo import DemoBackend
from prepa.preparation.jobs import JobQueue
from prepa.preparation.worker import work

logger = logging.getLogger(__name__)


def create_router(service: DialogService) -> Router:
    router = Router(name="prepa")

    @router.message()
    async def handle_message(message: Message) -> None:
        if message.chat.type != "private" or message.from_user is None:
            await message.answer("Работа с учениками доступна только в личном чате с ботом.")
            return
        if service.teacher_ids is not None and message.from_user.id not in service.teacher_ids:
            await message.answer("Доступ не настроен. Обратитесь к администратору.")
            return
        if message.text is None:
            await message.answer(
                "Пока принимаю только текст. Файл не сохранён; проверка ДЗ ещё не подключена."
            )
            return
        # Accept /command@botname and /start deep links without changing free text.
        text = message.text
        if text.startswith("/"):
            command, *arguments = text.split(maxsplit=1)
            command = command.split("@")[0].lower()
            text = command
            if command in ("/result", "/retry") and arguments:
                text += " " + arguments[0]
        try:
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
    mode = "demo" if settings.preparation_mode == "demo" else None
    service = DialogService(settings.teacher_ids, repository=repository, job_mode=mode)
    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(service))
    async with Bot(settings.token) as bot:

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
                    DemoBackend(),
                    DemoDocuments(),
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
