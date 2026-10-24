"""Evidence-grounded lesson notes; proposals never update pupil progress themselves."""

import hashlib
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .content import Contract, Id, Topic, Versioned, require_unique

ShortText = Annotated[str, Field(min_length=1, max_length=1200)]


class TranscriptTurn(Contract):
    turn_id: Id
    speaker: Literal["student", "teacher", "unknown"]
    text: Annotated[str, Field(min_length=1, max_length=6000)]


class LessonTaskReference(Contract):
    task_id: Id
    statement: Annotated[str, Field(min_length=1, max_length=20000)]


class LessonSummaryInput(Versioned):
    student_id: Id
    tasks: Annotated[tuple[LessonTaskReference, ...], Field(max_length=50)] = ()
    transcript: Annotated[tuple[TranscriptTurn, ...], Field(min_length=1, max_length=1000)]

    @model_validator(mode="after")
    def check_input(self) -> Self:
        require_unique(tuple(t.turn_id for t in self.transcript), "transcript turn IDs")
        require_unique(tuple(t.task_id for t in self.tasks), "task IDs")
        if sum(len(t.text) for t in self.transcript) > 100000:
            raise ValueError("transcript exceeds 100000 characters")
        if sum(len(t.statement) for t in self.tasks) > 100000:
            raise ValueError("task statements exceed 100000 characters")
        return self

    def digest(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


class TranscriptEvidence(Contract):
    turn_id: Id
    quote: Annotated[str, Field(min_length=1, max_length=500)]


class LessonObservation(Contract):
    topic: Topic
    status: Literal["understood", "difficulty", "unclear"]
    finding: ShortText
    evidence: Annotated[tuple[TranscriptEvidence, ...], Field(min_length=1, max_length=5)]
    task_ids: Annotated[tuple[Id, ...], Field(max_length=10)] = ()


class SummaryNextStep(Contract):
    topic: Topic
    action: ShortText
    basis_turn_ids: Annotated[tuple[Id, ...], Field(min_length=1, max_length=10)]


class LessonSummary(Versioned):
    student_id: Id
    input_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    overview: ShortText
    observations: Annotated[tuple[LessonObservation, ...], Field(max_length=30)] = ()
    next_steps: Annotated[tuple[SummaryNextStep, ...], Field(max_length=15)] = ()
    insufficient_evidence: bool
    uncertainty: Annotated[tuple[ShortText, ...], Field(max_length=10)] = ()
    requires_teacher_confirmation: Literal[True] = True
