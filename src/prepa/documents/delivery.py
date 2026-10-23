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


class DemoDocuments:
    """Plain UTF-8 JSON inside a marked text file; no TeX or PDF execution."""

    async def teacher(self, package: LessonPackage) -> Attachment:
        return Attachment("DEMO-teacher.txt", self._text(package.model_dump_json(indent=2)))

    async def student(self, lesson: StudentLesson) -> Attachment:
        return Attachment(
            f"DEMO-student-{lesson.student_id}.txt", self._text(lesson.model_dump_json(indent=2))
        )

    @staticmethod
    def _text(payload: str) -> bytes:
        return (
            "ДЕМО — тест интеграции, не учебный материал. Это текст, не PDF.\n\n" + payload
        ).encode()
