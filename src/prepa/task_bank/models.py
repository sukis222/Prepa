"""Exam problems found in an external bank, independent of Telegram, agents and LaTeX."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Exam = Literal["oge", "ege"]
KesCode = Annotated[str, Field(pattern=r"^\d+(\.\d+){0,2}$")]


class AnswerKind(StrEnum):
    SHORT = "short"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    MATCHING = "matching"
    EXTENDED = "extended"
    FILL_TERMS = "fill_terms"
    OTHER = "other"


class BankModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class KesTopic(BankModel):
    """One element of the exam content codifier (КЭС); parent codes include children."""

    code: KesCode
    title: Annotated[str, Field(min_length=1)]

    @property
    def depth(self) -> int:
        return self.code.count(".") + 1


class BankTask(BankModel):
    """A problem statement as published. Banks publish no answers or solutions.

    statement is plain text: MathML becomes inline LaTeX between `$`, pictures become
    `[рисунок N]` markers pointing into images (absolute URLs, same order).
    """

    source: Literal["fipi"] = "fipi"
    exam: Exam
    task_id: Annotated[str, Field(pattern=r"^[0-9A-Za-z]+$")]
    url: str
    kes: tuple[KesTopic, ...]
    answer_kind: AnswerKind
    instruction: str = ""
    statement: Annotated[str, Field(min_length=1)]
    options: tuple[str, ...] = ()
    matching_keys: tuple[str, ...] = ()
    answer_unit: str = ""
    images: tuple[str, ...] = ()

    @property
    def has_images(self) -> bool:
        return bool(self.images)


class SearchResult(BankModel):
    exam: Exam
    topics: tuple[KesTopic, ...]
    total_available: Annotated[int, Field(ge=0)]
    tasks: tuple[BankTask, ...]
