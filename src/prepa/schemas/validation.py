"""Deterministic contract checks. These do not establish correctness of physics."""

import hashlib
import json

from .content import (
    AssignmentSet,
    Author,
    GenerationContext,
    ReviewIssue,
    ReviewReport,
    ReviewResult,
    Theory,
    Versioned,
)


def ensure_identity(context: GenerationContext, value: Versioned) -> None:
    brief = context.brief
    if (value.preparation_id, value.version) != (brief.preparation_id, brief.version):
        raise ValueError("preparation_id and version must match the current brief")


def content_digest(context: GenerationContext, content: Versioned) -> str:
    """Bind review to the exact input, including brief, profiles and source contents."""
    payload = {
        "context": context.model_dump(mode="json"),
        "content": content.model_dump(mode="json"),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _error(author: Author, target: str, category: str, message: str, fix: str) -> ReviewIssue:
    return ReviewIssue.model_validate(
        {
            "author": author,
            "target_id": target,
            "category": category,
            "severity": "error",
            "message": message,
            "suggestion": fix,
        }
    )


def _check_item(
    context: GenerationContext, author: Author, target: str, topic: str, sources: tuple[str, ...]
) -> list[ReviewIssue]:
    issues = []
    if topic not in context.brief.topics:
        issues.append(
            _error(
                author,
                target,
                "topic",
                "Тема не согласована.",
                "Используйте точное название темы из brief.topics.",
            )
        )
    materials = {m.material_id: m for m in context.materials}
    if len(sources) != len(set(sources)) or any(s not in materials for s in sources):
        issues.append(
            _error(
                author,
                target,
                "source",
                "Неизвестный или повторный источник.",
                "Укажите уникальные material_id из переданной библиотеки.",
            )
        )
    elif not any(topic in materials[s].topics for s in sources):
        issues.append(
            _error(
                author,
                target,
                "source",
                "Источник не покрывает тему материала.",
                "Выберите переданный источник с соответствующей темой.",
            )
        )
    return issues


def check_theory(context: GenerationContext, theory: Theory) -> tuple[ReviewIssue, ...]:
    ensure_identity(context, theory)
    issues = [
        issue
        for s in theory.sections
        for issue in _check_item(context, "theory", s.section_id, s.topic, s.source_ids)
    ]
    if not set(context.brief.topics) <= {s.topic for s in theory.sections}:
        issues.append(
            _error(
                "theory",
                theory.sections[0].section_id,
                "coverage",
                "Теория не покрывает все согласованные темы.",
                "Добавьте объяснения и примеры по каждой теме brief.topics.",
            )
        )
    return tuple(issues)


def check_assignments(
    context: GenerationContext, assignments: AssignmentSet
) -> tuple[ReviewIssue, ...]:
    ensure_identity(context, assignments)
    brief = context.brief
    first_id = assignments.lesson_assignments[0].assignment_id
    issues = [
        issue
        for a in assignments.all_assignments()
        for issue in _check_item(context, "assignments", a.assignment_id, a.topic, a.source_ids)
    ]
    if len(assignments.lesson_assignments) != brief.lesson_task_count:
        issues.append(
            _error(
                "assignments",
                first_id,
                "coverage",
                "Неверное число задач на урок.",
                "Соблюдайте lesson_task_count из brief.",
            )
        )
    if not set(brief.topics) <= {a.topic for a in assignments.lesson_assignments}:
        issues.append(
            _error(
                "assignments",
                first_id,
                "coverage",
                "Не все темы есть в практике.",
                "Включите в урок задачу по каждой согласованной теме.",
            )
        )
    if sum(a.estimated_minutes for a in assignments.lesson_assignments) > brief.duration_minutes:
        issues.append(
            _error(
                "assignments",
                first_id,
                "timing",
                "Практика длиннее всего урока.",
                "Сократите объём с учётом duration_minutes и времени на теорию.",
            )
        )
    expected = set(brief.student_ids) if brief.homework_task_count else set()
    if {h.student_id for h in assignments.homeworks} != expected:
        issues.append(
            _error(
                "assignments",
                first_id,
                "coverage",
                "Неверные получатели ДЗ.",
                "Подготовьте отдельное ДЗ каждому ученику; при нулевом объёме — [].",
            )
        )
    for homework in assignments.homeworks:
        target = homework.assignments[0].assignment_id
        if len(homework.assignments) != brief.homework_task_count:
            issues.append(
                _error(
                    "assignments",
                    target,
                    "coverage",
                    "Неверное число задач ДЗ.",
                    "Соблюдайте homework_task_count для каждого ученика.",
                )
            )
        if sum(a.estimated_minutes for a in homework.assignments) > brief.homework_minutes:
            issues.append(
                _error(
                    "assignments",
                    target,
                    "timing",
                    "ДЗ превышает согласованное время.",
                    "Уложите ДЗ каждого ученика в homework_minutes.",
                )
            )
    return tuple(issues)


def check_review(
    context: GenerationContext, theory: Theory, assignments: AssignmentSet, review: ReviewReport
) -> None:
    ensure_identity(context, theory)
    ensure_identity(context, assignments)
    ensure_identity(context, review)
    targets = {
        "theory": {s.section_id for s in theory.sections},
        "assignments": {a.assignment_id for a in assignments.all_assignments()},
    }
    if any(issue.target_id not in targets[issue.author] for issue in review.issues):
        raise ValueError("review issues must address existing IDs belonging to the named author")
    if isinstance(review, ReviewResult) and (
        review.theory_digest != content_digest(context, theory)
        or review.assignments_digest != content_digest(context, assignments)
    ):
        raise ValueError("review is stale: content or context changed after review")
