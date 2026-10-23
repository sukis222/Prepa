"""Synthetic contract fixtures, never a source of teaching materials or physics review."""

from prepa.schemas import (
    AssignmentSet,
    GenerationContext,
    LessonBrief,
    LessonPackage,
    ReviewResult,
    StudentProfile,
    Theory,
)
from prepa.schemas.validation import content_digest

DEMO_NOTICE = "ДЕМО — тест интеграции. Не учебный материал; проверка физики не выполнялась."


class DemoBackend:
    async def prepare(
        self, teacher_id: int, brief: LessonBrief, students: tuple[StudentProfile, ...]
    ) -> LessonPackage:
        if not brief.confirmed:
            raise ValueError("Confirmation required")
        context = GenerationContext.model_validate(
            {
                "brief": brief.model_dump(),
                "students": [s.model_dump() for s in students],
                "materials": [
                    {
                        "material_id": "demo-source",
                        "title": DEMO_NOTICE,
                        "source": "Встроенная синтетическая заглушка Prepa, не учебный источник",
                        "exam": brief.exam,
                        "topics": brief.topics,
                        "content": DEMO_NOTICE,
                    }
                ],
            }
        )
        identity = {"preparation_id": brief.preparation_id, "version": brief.version}
        block = {"text": DEMO_NOTICE}
        theory = Theory.model_validate(
            {
                **identity,
                "sections": [
                    {
                        "section_id": f"demo-section-{i}",
                        "topic": topic,
                        "title": f"ДЕМО: {topic}",
                        "explanation": block,
                        "worked_examples": [
                            {"statement": block, "answer": block, "solution": [block]}
                        ],
                        "source_ids": ["demo-source"],
                    }
                    for i, topic in enumerate(brief.topics)
                ],
            }
        )

        def tasks(prefix: str, count: int) -> list[dict[str, object]]:
            return [
                {
                    "assignment_id": f"{prefix}-{i}",
                    "topic": brief.topics[i % len(brief.topics)],
                    "difficulty": 1,
                    "estimated_minutes": 1,
                    "statement": {"text": f"ДЕМО: место для задания №{i + 1}. {DEMO_NOTICE}"},
                    "answer": {"text": "ДЕМО: закрытый ответ преподавателя"},
                    "solution": [{"text": "ДЕМО: закрытое решение преподавателя"}],
                    "source_ids": ["demo-source"],
                }
                for i in range(count)
            ]

        assignments = AssignmentSet.model_validate(
            {
                **identity,
                "lesson_assignments": tasks("lesson", brief.lesson_task_count),
                "homeworks": [
                    {
                        "student_id": sid,
                        "rationale": DEMO_NOTICE,
                        "assignments": tasks(f"hw-{i}", brief.homework_task_count),
                    }
                    for i, sid in enumerate(brief.student_ids)
                    if brief.homework_task_count
                ],
            }
        )
        review = ReviewResult.model_validate(
            {
                **identity,
                "summary": DEMO_NOTICE,
                "theory_digest": content_digest(context, theory),
                "assignments_digest": content_digest(context, assignments),
            }
        )
        return LessonPackage(context=context, theory=theory, assignments=assignments, review=review)
