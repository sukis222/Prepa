"""Telegram-independent dialog with transactional PostgreSQL checkpoints."""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError

from prepa.agents.runtime import (
    AgentResponseError,
    ContentValidationError,
    InsufficientMaterialsError,
)
from prepa.db.repository import Repository, StudentRecord
from prepa.documents.delivery import Attachment
from prepa.preparation.jobs import attachments
from prepa.schemas import LessonBrief, LessonPackage, StudentProfile

MENU = (
    ("Новое занятие", "Ученики"),
    ("Добавить ученика",),
    ("Статус", "История"),
    ("Результат", "Повторить"),
    ("Правки", "Помощь"),
)
ALIASES = {
    "Новое занятие": "/lesson",
    "Ученики": "/students",
    "Добавить ученика": "/add_student",
    "Статус": "/status",
    "История": "/history",
    "Правки": "/edit",
    "Помощь": "/help",
    "Результат": "/result",
    "Повторить": "/retry",
    "Отмена": "/cancel",
    "Подтвердить": "/confirm",
}
HELP = (
    "Prepa — подготовка занятий по физике.\n"
    "/id — ваш числовой Telegram ID\n"
    "/students — список учеников\n"
    "/add_student — добавить ученика\n"
    "/lesson — согласовать новое занятие\n"
    "/confirm — подтвердить текущий запрос\n"
    "/edit — новая версия последнего запроса\n"
    "/status — текущий запрос\n"
    "/history — подтверждённые запросы\n"
    "/result — получить результат (или /result N из истории)\n"
    "/retry — повторить неудачную подготовку (или /retry N)\n"
    "/homework — проверка выполненного ДЗ\n"
    "/cancel — отменить черновик\n\n"
    "Генерация, PDF и проверка ДЗ пока не подключены."
)


class PreparationBackend(Protocol):
    """Implement in the orchestrator; must authorize sources and re-review each version."""

    async def prepare(
        self, teacher_id: int, brief: LessonBrief, students: tuple[StudentProfile, ...]
    ) -> LessonPackage: ...


@dataclass(frozen=True)
class Reply:
    text: str
    buttons: tuple[tuple[str, ...], ...] = MENU
    attachments: tuple[Attachment, ...] = ()


@dataclass
class Session:
    step: Literal[
        "idle",
        "students",
        "topics",
        "format",
        "notes",
        "confirm",
        "student_name",
        "student_profile",
        "student_goal",
    ] = "idle"
    selected: tuple[StudentProfile, ...] = ()
    draft: LessonBrief | None = None
    topics: tuple[str, ...] = ()
    history: deque[LessonBrief] = field(default_factory=lambda: deque(maxlen=20))
    choices: tuple[StudentRecord, ...] = ()
    student_name: str = ""
    student_profile: StudentProfile | None = None
    new_student: StudentRecord | None = None


SESSION_ADAPTER = TypeAdapter(Session)


def demo_students() -> tuple[StudentProfile, ...]:
    return (
        StudentProfile(student_id="demo-a", grade=9, exam="oge", common_errors=("Перевод в СИ",)),
        StudentProfile(student_id="demo-b", grade=9, exam="oge", level="intermediate"),
        StudentProfile(student_id="demo-c", grade=11, exam="ege"),
    )


def summary(brief: LessonBrief) -> str:
    level = {"basic": "базовый", "intermediate": "средний", "advanced": "углублённый"}
    return (
        f"Подготовка {brief.preparation_id}, версия {brief.version}\n"
        f"Ученики: {', '.join(brief.student_ids)}; {brief.exam.upper()}\n"
        f"Темы: {'; '.join(brief.topics)}\n"
        f"Урок: {brief.duration_minutes} мин.; теория: {level[brief.theory_level]}; "
        f"задач: {brief.lesson_task_count}\n"
        f"ДЗ каждому: {brief.homework_task_count} задач, {brief.homework_minutes} мин.\n"
        f"Пожелания: {brief.teacher_notes or 'нет'}\n"
        f"{'Подтверждено' if brief.confirmed else 'Ожидает подтверждения'}"
    )


class DialogService:
    def __init__(
        self,
        teacher_ids: frozenset[int] | None,
        backend: PreparationBackend | None = None,
        repository: Repository | None = None,
        job_mode: str | None = None,
    ) -> None:
        if job_mode not in (None, "demo", "real") or (job_mode and repository is None):
            raise ValueError("Job mode requires a repository")
        self.job_mode = job_mode
        self.teacher_ids = teacher_ids
        self.backend = backend
        self.sessions: dict[int, Session] = {}
        self.repository = repository
        self.catalogs: dict[int, tuple[StudentRecord, ...]] = {}

    async def respond(self, teacher_id: int, text: str) -> Reply:
        if self.teacher_ids is not None and teacher_id not in self.teacher_ids:
            return Reply("Доступ не настроен. Обратитесь к администратору.", ())
        if self.repository is None:
            reply = await self._respond(teacher_id, text)
            session = self.sessions[teacher_id]
            if session.new_student is not None:
                self.catalogs[teacher_id] = (*self._catalog(teacher_id), session.new_student)
                session.new_student = None
            return reply
        text = ALIASES.get(text.strip(), text.strip())
        if text.split(" ", 1)[0] in ("/result", "/retry"):
            return await self._result(teacher_id, text)
        confirmed: LessonBrief | None = None
        async with self.repository.transaction(teacher_id) as store:
            # A short-lived worker avoids retaining uncommitted state after a failed write.
            worker = DialogService(
                self.teacher_ids, repository=self.repository, job_mode=self.job_mode
            )
            state = await store.load_state()
            if state is not None:
                if state.get("format_version") != 1:
                    raise ValueError("Unsupported dialog state version")
                worker.sessions[teacher_id] = SESSION_ADAPTER.validate_python(state["session"])
                history = worker.sessions[teacher_id].history
                worker.sessions[teacher_id].history = deque(history, maxlen=20)
            worker.catalogs[teacher_id] = await store.students()
            previous = worker.sessions.get(teacher_id, Session()).history
            last = previous[-1] if previous else None
            reply = await worker._respond(teacher_id, text)
            session = worker.sessions[teacher_id]
            if session.new_student is not None:
                await store.add_student(session.new_student)
                session.new_student = None
            if session.history and session.history[-1] != last:
                confirmed = session.history[-1]
                await store.save_brief(confirmed)
                if self.job_mode:
                    await store.enqueue(confirmed, session.selected, self.job_mode)
                    reply = Reply(
                        ("ДЕМО: " if self.job_mode == "demo" else "")
                        + "Запрос подтверждён и поставлен в очередь. Результат придёт отдельным "
                        "сообщением. /result — статус и повторная выдача."
                    )
            await store.save_state(
                {"format_version": 1, "session": SESSION_ADAPTER.dump_python(session, mode="json")}
            )
        # Never hold a DB transaction across a model call or Telegram delivery.
        if confirmed is not None and self.backend is not None and not self.job_mode:
            return await self._generate(teacher_id, confirmed, session.selected)
        return reply

    async def _result(self, teacher_id: int, text: str) -> Reply:
        assert self.repository is not None
        async with self.repository.transaction(teacher_id) as store:
            state = await store.load_state()
            history = SESSION_ADAPTER.validate_python(state["session"]).history if state else ()
            if not history:
                return Reply("Сначала подтвердите запрос через /lesson.")
            parts = text.split()
            try:
                index = int(parts[1]) if len(parts) == 2 else len(history)
                if len(parts) > 2 or not 1 <= index <= len(history):
                    raise ValueError("index")
            except ValueError:
                return Reply("Укажите номер из /history: /result 1 или /retry 1.")
            brief = history[index - 1]
            job = await store.job(brief)
            if job is None:
                return Reply("У этого запроса нет задания на подготовку. /edit — новая версия.")
            if parts[0] == "/retry":
                if self.job_mode and await store.retry(brief, self.job_mode):
                    return Reply("Повтор поставлен в очередь. /result — статус.")
                return Reply("Повтор доступен только после ошибки и в том же режиме подготовки.")
            label = f"Подготовка {brief.preparation_id}, v{brief.version}. "
            if job["mode"] == "demo":
                label += "ДЕМО — не учебный материал. "
            if job["status"] == "ready":
                return Reply(
                    label + "Готово. Файл teacher содержит ответы; не передавайте его ученикам.",
                    attachments=attachments(job["result"]),
                )
            statuses = {
                "queued": "В очереди.",
                "running": "Подготовка выполняется.",
                "failed": "Подготовка не удалась. /retry — повторить.",
            }
            return Reply(label + statuses[job["status"]])

    def _catalog(self, teacher_id: int) -> tuple[StudentRecord, ...]:
        if teacher_id not in self.catalogs:
            self.catalogs[teacher_id] = tuple(
                StudentRecord(s, s.student_id) for s in demo_students()
            )
        return self.catalogs[teacher_id]

    async def _respond(self, teacher_id: int, text: str) -> Reply:
        session = self.sessions.setdefault(teacher_id, Session())
        catalog = self._catalog(teacher_id)
        text = ALIASES.get(text.strip(), text.strip())
        if text in ("/start", "/help"):
            storage = (
                "Ученики, черновики и подтверждённые запросы сохраняются в PostgreSQL."
                if self.repository is not None
                else "Демонстрационный режим: данные хранятся в памяти до перезапуска."
            )
            mode = ""
            if self.job_mode == "demo":
                mode = "\nДЕМО: тестовые материалы и TXT-файлы, без LLM, PDF и проверки физики."
            return Reply(HELP + "\n" + storage + mode)
        if text == "/id":
            return Reply(f"Ваш Telegram ID: {teacher_id}")
        if text == "/students":
            return Reply(self._students_text(catalog))
        if text == "/add_student":
            self.sessions[teacher_id] = Session(step="student_name", history=session.history)
            return Reply("Введите имя ученика (до 100 символов).", (("Отмена",),))
        if text == "/cancel":
            self.sessions[teacher_id] = Session(history=session.history)
            return Reply("Черновик отменён. Подтверждённые запросы сохранены.")
        if text == "/lesson":
            if not catalog:
                return Reply("Сначала добавьте ученика: /add_student.")
            self.sessions[teacher_id] = Session(
                step="students", history=session.history, choices=catalog
            )
            return Reply(
                self._students_text(catalog)
                + "\nВведите номера одного или двух учеников: 1 или 1,2."
            )
        if text == "/history":
            entries = [
                f"{i}. {item.preparation_id} · v{item.version} · {', '.join(item.topics)}"
                for i, item in enumerate(session.history, 1)
            ]
            return Reply(
                "Подтверждённые запросы (до 20):\n" + "\n".join(entries or ["Пока пусто."])
            )
        if text == "/status":
            brief = session.draft or (session.history[-1] if session.history else None)
            details = summary(brief) if brief else "Запрос ещё не составлен."
            return Reply(details + f"\nШаг: {session.step}. /cancel — отменить черновик.")
        if text == "/homework":
            return Reply(
                "Проверка ДЗ ещё не подключена. Файлы не сохраняются и не проверяются. "
                "Для этого сценария нужны выданное ДЗ, ученик и агент проверки."
            )
        if text == "/edit":
            if not session.history:
                return Reply("Сначала подтвердите запрос через /lesson.")
            previous = session.history[-1]
            draft = LessonBrief.model_validate(
                {**previous.model_dump(), "version": previous.version + 1, "confirmed": False}
            )
            self.sessions[teacher_id] = Session(
                step="topics",
                draft=draft,
                selected=tuple(
                    s.profile for s in catalog if s.profile.student_id in draft.student_ids
                ),
                history=session.history,
            )
            return Reply("Новая версия запроса. " + self._topics_prompt())
        if text == "/confirm":
            if session.step != "confirm" or session.draft is None:
                return Reply("Нет запроса для подтверждения. Начните с /lesson.")
            return await self._confirm(teacher_id, session)
        if text.startswith("/"):
            return Reply("Неизвестная команда. /help — список команд.")
        try:
            return self._advance(session, text)
        except (ValueError, ValidationError):
            return Reply("Не удалось принять ввод. " + self._prompt(session), (("Отмена",),))

    @staticmethod
    def _students_text(catalog: tuple[StudentRecord, ...]) -> str:
        return (
            "Ученики:\n"
            + "\n".join(
                f"{i}. {s.display_name} — {s.profile.grade} класс, "
                f"{s.profile.exam.upper()}, {s.profile.level}"
                for i, s in enumerate(catalog, 1)
            )
            + ("\n/add_student — добавить ученика." if not catalog else "")
        )

    @staticmethod
    def _topics_prompt() -> str:
        return "Введите от 1 до 8 тем через точку с запятой (до 160 символов каждая)."

    def _prompt(self, session: Session) -> str:
        return {
            "student_name": "Введите имя ученика (от 1 до 100 символов).",
            "student_profile": "Введите класс, экзамен и уровень (1–3). Пример: 9 ОГЭ 1.",
            "student_goal": "Введите цель (до 500 символов) или «-».",
            "students": "Введите 1–2 разных номера через запятую, с одинаковым экзаменом.",
            "topics": self._topics_prompt(),
            "format": (
                "Введите 5 значений через пробел: минуты урока, уровень теории "
                "(1 — базовый, 2 — средний, 3 — углублённый), число задач урока, "
                "число задач ДЗ, минуты ДЗ.\n"
                "Пример: 60 1 4 2 20. "
                "Без ДЗ: 60 1 4 0 0. "
                "Время до 180 мин., задач до 20; задач урока не меньше числа тем."
            ),
            "notes": "Добавьте пожелания (до 1000 символов) или отправьте «-».",
            "confirm": "Нажмите «Подтвердить» или /cancel для отмены.",
            "idle": "Начните с /lesson; /help — помощь.",
        }[session.step]

    def _advance(self, session: Session, text: str) -> Reply:
        if session.step == "student_name":
            if not 1 <= len(text) <= 100:
                raise ValueError("name")
            session.student_name = text
            session.step = "student_profile"
        elif session.step == "student_profile":
            grade, exam, pupil_level = text.lower().split()
            exams = {"огэ": "oge", "егэ": "ege", "oge": "oge", "ege": "ege"}
            pupil_levels = {"1": "basic", "2": "intermediate", "3": "advanced"}
            session.student_profile = StudentProfile.model_validate(
                {
                    "student_id": uuid4().hex,
                    "grade": int(grade),
                    "exam": exams.get(exam),
                    "level": pupil_levels.get(pupil_level),
                }
            )
            session.step = "student_goal"
        elif session.step == "student_goal":
            if not 1 <= len(text) <= 500:
                raise ValueError("goal")
            assert session.student_profile is not None
            session.new_student = StudentRecord(
                session.student_profile, session.student_name, None if text == "-" else text
            )
            session.step = "idle"
            return Reply(f"Ученик {session.student_name} добавлен. /lesson — подготовить занятие.")
        elif session.step == "students":
            numbers = tuple(int(item.strip()) for item in text.split(","))
            if not 1 <= len(numbers) <= 2 or len(set(numbers)) != len(numbers):
                raise ValueError("selection")
            students = tuple(s.profile for s in session.choices)
            if any(number < 1 or number > len(students) for number in numbers):
                raise ValueError("selection")
            selected = tuple(students[number - 1] for number in numbers)
            if len({s.exam for s in selected}) != 1:
                raise ValueError("exams")
            session.selected = selected
            session.step = "topics"
        elif session.step == "topics":
            topics = tuple(topic.strip() for topic in text.split(";"))
            if (
                not 1 <= len(topics) <= 8
                or any(not 1 <= len(topic) <= 160 for topic in topics)
                or len(set(topics)) != len(topics)
            ):
                raise ValueError("topics")
            session.topics = topics
            session.step = "format"
        elif session.step == "format":
            duration, level, tasks, homework, minutes = (int(value) for value in text.split())
            levels = {1: "basic", 2: "intermediate", 3: "advanced"}
            if level not in levels:
                raise ValueError("level")
            session.draft = LessonBrief.model_validate(
                {
                    "preparation_id": session.draft.preparation_id
                    if session.draft
                    else uuid4().hex,
                    "version": session.draft.version if session.draft else 1,
                    "student_ids": tuple(s.student_id for s in session.selected),
                    "exam": session.selected[0].exam,
                    "topics": session.topics,
                    "duration_minutes": duration,
                    "theory_level": levels[level],
                    "lesson_task_count": tasks,
                    "homework_task_count": homework,
                    "homework_minutes": minutes,
                }
            )
            session.step = "notes"
        elif session.step == "notes":
            if not text or len(text) > 1000:
                raise ValueError("notes")
            assert session.draft is not None
            session.draft = LessonBrief.model_validate(
                {**session.draft.model_dump(), "teacher_notes": None if text == "-" else text}
            )
            session.step = "confirm"
            return Reply(summary(session.draft), (("Подтвердить", "Отмена"),))
        return Reply(self._prompt(session), (("Отмена",),))

    async def _confirm(self, teacher_id: int, session: Session) -> Reply:
        assert session.draft is not None
        brief = LessonBrief.model_validate({**session.draft.model_dump(), "confirmed": True})
        session.history.append(brief)
        session.draft = None
        session.step = "idle"
        if self.backend is None:
            destination = (
                "в PostgreSQL" if self.repository is not None else "в памяти до перезапуска"
            )
            return Reply(
                f"Запрос подтверждён и сохранён {destination}. "
                "Генерация и PDF пока не подключены. /edit — подготовить новую версию."
            )
        return await self._generate(teacher_id, brief, session.selected)

    async def _generate(
        self, teacher_id: int, brief: LessonBrief, students: tuple[StudentProfile, ...]
    ) -> Reply:
        assert self.backend is not None
        try:
            async with asyncio.timeout(180):
                package = await self.backend.prepare(teacher_id, brief, students)
            package = LessonPackage.model_validate(package.model_dump(mode="json"))
            if package.context.brief != brief or set(package.context.students) != set(students):
                raise ValueError("Backend returned another context")
        except InsufficientMaterialsError:
            return Reply("Недостаточно источников для выбранных тем. Уточните запрос через /edit.")
        except (ContentValidationError, AgentResponseError, ValidationError, ValueError):
            return Reply("Материалы не прошли проверку. Выдача отменена. /edit — изменить запрос.")
        except TimeoutError:
            return Reply("Время подготовки истекло. /edit — подготовить новый запрос.")
        files = [Attachment("teacher.json", package.model_dump_json(indent=2).encode())]
        files.extend(
            Attachment(f"{sid}.json", package.for_student(sid).model_dump_json(indent=2).encode())
            for sid in brief.student_ids
        )
        return Reply(
            "Содержание прошло проверку. PDF ещё не подключён; "
            "прикреплены JSON для интеграции. teacher.json содержит ответы и профили, "
            "не передавайте его ученикам.",
            attachments=tuple(files),
        )
