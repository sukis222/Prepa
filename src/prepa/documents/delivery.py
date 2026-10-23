"""Document port. Student renderers receive only the public student projection."""

from dataclasses import dataclass
from typing import Protocol

from prepa.schemas import LessonPackage, StudentLesson


@dataclass(frozen=True)
class Attachment:
    name: str
    content: bytes


class DocumentRenderer(Protocol):
    async def teacher(self, package: LessonPackage) -> Attachment: ...
    async def student(self, lesson: StudentLesson) -> Attachment: ...
    async def tasks(self, lesson: StudentLesson, *, demo: bool = False) -> Attachment: ...


class DemoDocuments:
    """Plain UTF-8 JSON inside a marked text file; no TeX or PDF execution."""

    async def teacher(self, package: LessonPackage) -> Attachment:
        return Attachment("DEMO-teacher.txt", self._text(package.model_dump_json(indent=2)))

    async def student(self, lesson: StudentLesson) -> Attachment:
        return Attachment(
            f"DEMO-student-{lesson.student_id}.txt", self._text(lesson.model_dump_json(indent=2))
        )

    async def tasks(self, lesson: StudentLesson, *, demo: bool = False) -> Attachment:
        return Attachment(
            "DEMO-tasks.txt",
            self._text(lesson.model_dump_json(include={"lesson_assignments"}, indent=2)),
        )

    @staticmethod
    def _text(payload: str) -> bytes:
        return (
            "ДЕМО — тест интеграции, не учебный материал. Это текст, не PDF.\n\n" + payload
        ).encode()


class JsonDocuments:
    """Diagnostic JSON output; production uses LatexDocuments."""

    async def teacher(self, package: LessonPackage) -> Attachment:
        return Attachment("teacher.json", package.model_dump_json(indent=2).encode())

    async def student(self, lesson: StudentLesson) -> Attachment:
        return Attachment(
            f"student-{lesson.student_id}.json", lesson.model_dump_json(indent=2).encode()
        )

    async def tasks(self, lesson: StudentLesson, *, demo: bool = False) -> Attachment:
        return Attachment(
            "tasks.json",
            lesson.model_dump_json(include={"lesson_assignments"}, indent=2).encode(),
        )
