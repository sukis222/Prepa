"""Confirmed preparation through FIPI, real authors, and bounded full-package review."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Protocol

from prepa.agents.assignments import AssignmentsAgent
from prepa.agents.contracts import StructuredLLM
from prepa.agents.reviewer import ReviewerAgent
from prepa.agents.runtime import ContentValidationError, InsufficientMaterialsError
from prepa.agents.theory import TheoryAgent
from prepa.schemas import (
    AssignmentSet,
    GenerationContext,
    GenerationFailure,
    LessonBrief,
    LessonPackage,
    Material,
    ReviewResult,
    StudentProfile,
    Theory,
)
from prepa.task_bank import FipiClient, TaskSearch, TaskSourceError, UnknownTopicError, to_material
from prepa.task_bank.official import OfficialNavigatorMaterials, maintenance_for_exam


class MaterialSource(Protocol):
    async def materials(self, brief: LessonBrief) -> tuple[Material, ...]: ...


def insufficient(topics: tuple[str, ...]) -> InsufficientMaterialsError:
    return InsufficientMaterialsError(
        GenerationFailure(
            status="insufficient_material",
            missing_topics=topics,
            reason="Нет подходящих текстовых источников ФИПИ; уточните тему или код КЭС.",
        )
    )


class FipiMaterials:
    async def materials(self, brief: LessonBrief) -> tuple[Material, ...]:
        notice = await maintenance_for_exam(brief.exam)
        if notice is not None and notice.active(date.today()):
            return await OfficialNavigatorMaterials().materials(brief)
        try:
            return await self._bank_materials(brief)
        except TaskSourceError:
            return await OfficialNavigatorMaterials().materials(brief)

    async def _bank_materials(self, brief: LessonBrief) -> tuple[Material, ...]:
        found: dict[str, Material] = {}
        async with FipiClient() as bank:
            search = TaskSearch(bank, max_pages=2)
            for topic in brief.topics:
                try:
                    result = await search.search(brief.exam, [topic], limit=3, with_images=False)
                except UnknownTopicError:
                    raise insufficient((topic,)) from None
                if not result.tasks:
                    raise insufficient((topic,))
                for task in result.tasks:
                    material = to_material(task, (topic,))
                    if task.instruction:
                        material = Material.model_validate(
                            {
                                **material.model_dump(),
                                "content": task.instruction + "\n" + material.content,
                            }
                        )
                    previous = found.get(material.material_id)
                    if previous:
                        material = Material.model_validate(
                            {
                                **material.model_dump(),
                                "topics": tuple(dict.fromkeys((*previous.topics, topic))),
                            }
                        )
                    found[material.material_id] = material
        return tuple(found.values())


class ReviewRejectedError(ValueError):
    """No delivery after exhausting the configured correction budget."""


class RealBackend:
    def __init__(
        self,
        llm: StructuredLLM,
        *,
        source: MaterialSource | None = None,
        check_model: Callable[[], Awaitable[None]] | None = None,
        max_corrections: int = 1,
    ) -> None:
        if type(max_corrections) is not int or not 0 <= max_corrections <= 2:
            raise ValueError("max_corrections must be between 0 and 2")
        self.theory = TheoryAgent(llm)
        self.assignments = AssignmentsAgent(llm)
        self.reviewer = ReviewerAgent(llm)
        self.source = source or FipiMaterials()
        self.check_model = check_model
        self.max_corrections = max_corrections

    async def prepare(
        self, teacher_id: int, brief: LessonBrief, students: tuple[StudentProfile, ...]
    ) -> LessonPackage:
        if not brief.confirmed:
            raise ValueError("Confirmation required before sources or model calls")
        # Validate profiles before any external request. Repository already scopes the
        # snapshot to the teacher; no arbitrary student lookup is performed here.
        if teacher_id <= 0 or {s.student_id for s in students} != set(brief.student_ids):
            raise ValueError("Invalid teacher/student context")
        if any(s.exam != brief.exam for s in students):
            raise ValueError("Student exam mismatch")
        async with asyncio.timeout(170):
            if self.check_model:
                await self.check_model()
            context = GenerationContext(
                brief=brief, students=students, materials=await self.source.materials(brief)
            )
            theory = await self._theory(context)
            assignments = await self._assignments(context, theory)
            for attempt in range(self.max_corrections + 1):
                review = await self.reviewer.review(context, theory, assignments)
                if review.approved:
                    return LessonPackage(
                        context=context, theory=theory, assignments=assignments, review=review
                    )
                if attempt == self.max_corrections:
                    break
                if review.for_author("theory"):
                    theory = await self._theory(context, theory, review)
                    # Changed theory invalidates prior practice; generate and review anew.
                    assignments = await self._assignments(context, theory)
                elif review.for_author("assignments"):
                    assignments = await self._assignments(context, theory, assignments, review)
            raise ReviewRejectedError("Материалы не прошли проверку; выдача отменена")

    async def _theory(
        self,
        context: GenerationContext,
        previous: Theory | None = None,
        feedback: ReviewResult | None = None,
    ) -> Theory:
        try:
            return await self.theory.generate(context, previous=previous, feedback=feedback)
        except ContentValidationError as error:
            if not self.max_corrections:
                raise
            assert isinstance(error.content, Theory)
            return await self.theory.generate(
                context, previous=error.content, feedback=error.feedback
            )

    async def _assignments(
        self,
        context: GenerationContext,
        theory: Theory,
        previous: AssignmentSet | None = None,
        feedback: ReviewResult | None = None,
    ) -> AssignmentSet:
        try:
            return await self.assignments.generate(
                context, theory, previous=previous, feedback=feedback
            )
        except ContentValidationError as error:
            if not self.max_corrections:
                raise
            assert isinstance(error.content, AssignmentSet)
            return await self.assignments.generate(
                context, theory, previous=error.content, feedback=error.feedback
            )
