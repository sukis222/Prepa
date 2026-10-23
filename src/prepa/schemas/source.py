"""Immutable snapshots of existing source conditions; never generated lesson solutions."""

import base64
import hashlib
import json
from typing import Annotated, Self

from pydantic import ConfigDict, Field, model_validator

from .content import Contract, Exam, Id, Topic, Versioned, require_unique

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


def source_task_digest(text: str, math: tuple[str, ...] = ()) -> str:
    payload = {"statement_exact": text, "statement_math_exact": list(math)}
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


class SourceImage(Contract):
    data_base64: Annotated[str, Field(min_length=1, max_length=4_000_000)]
    sha256: Digest
    width: Annotated[int, Field(strict=True, ge=1, le=10_000)]
    height: Annotated[int, Field(strict=True, ge=1, le=10_000)]

    @model_validator(mode="after")
    def verify_bytes(self) -> Self:
        try:
            content = base64.b64decode(self.data_base64, validate=True)
        except ValueError:
            raise ValueError("Invalid source image encoding") from None
        if hashlib.sha256(content).hexdigest() != self.sha256:
            raise ValueError("Source image digest mismatch")
        return self


class SourceTask(Contract):
    # Preserve the source byte-for-byte, including whitespace in conditions and math.
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)
    id: Id
    statement_exact: Annotated[str, Field(min_length=1, max_length=20_000)]
    statement_math_exact: Annotated[tuple[str, ...], Field(max_length=30)] = ()
    source_url: Annotated[str, Field(min_length=1, max_length=3000)]
    page: Annotated[int, Field(strict=True, ge=1)] | None = None
    images: Annotated[tuple[SourceImage, ...], Field(max_length=4)] = ()
    sha256: Digest

    @model_validator(mode="after")
    def verify_digest(self) -> Self:
        if any(not m or len(m) > 4000 for m in self.statement_math_exact):
            raise ValueError("Invalid source mathematics")
        if self.sha256 != source_task_digest(self.statement_exact, self.statement_math_exact):
            raise ValueError("Source condition digest mismatch")
        return self


class TaskWorksheet(Versioned):
    student_ids: Annotated[tuple[Id, ...], Field(min_length=1, max_length=2)]
    exam: Exam
    topics: Annotated[tuple[Topic, ...], Field(min_length=1, max_length=8)]
    title: Annotated[str, Field(min_length=1, max_length=200)]
    tasks: Annotated[tuple[SourceTask, ...], Field(min_length=1, max_length=50)]

    @model_validator(mode="after")
    def verify_unique(self) -> Self:
        require_unique(self.student_ids, "student_ids")
        require_unique(self.topics, "topics")
        require_unique(tuple(task.id for task in self.tasks), "tasks")
        return self
