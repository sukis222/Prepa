"""Deterministic quality checks and approval freshness for generated lesson content."""

import copy

import pytest
from pydantic import ValidationError

from prepa.schemas import (
    AssignmentSet,
    GenerationContext,
    LessonBrief,
    LessonPackage,
    ReviewResult,
    Theory,
)
from prepa.schemas.validation import (
    check_assignments,
    check_review,
    check_theory,
    content_digest,
)


def test_demo_passes_all_deterministic_checks(context, theory, assignments, review):
    assert check_theory(context, theory) == ()
    assert check_assignments(context, assignments) == ()
    assert check_review(context, theory, assignments, review) is None
    assert review.approved


@pytest.mark.parametrize("field", ["preparation_id", "version"])
@pytest.mark.parametrize("kind", ["theory", "assignments", "review"])
def test_every_artifact_must_match_current_preparation_and_version(
    demo,
    context,
    theory,
    assignments,
    review,
    field,
    kind,
):
    data = demo[kind]
    data[field] = "another-preparation" if field == "preparation_id" else 2
    with pytest.raises(ValueError, match="preparation_id and version"):
        if kind == "theory":
            check_theory(context, Theory.model_validate(data))
        elif kind == "assignments":
            check_assignments(context, AssignmentSet.model_validate(data))
        else:
            changed = ReviewResult.model_validate({**review.model_dump(), **data})
            check_review(context, theory, assignments, changed)


@pytest.mark.parametrize("kind", ["theory", "assignments"])
@pytest.mark.parametrize("sources", [["invented-source"], ["demo-motion", "demo-motion"]])
def test_unknown_or_duplicate_citations_block_both_authors(demo, context, kind, sources):
    data = demo[kind]
    collection = data["sections"] if kind == "theory" else data["lesson_assignments"]
    collection[0]["source_ids"] = sources
    model = Theory if kind == "theory" else AssignmentSet
    checker = check_theory if kind == "theory" else check_assignments

    issues = checker(context, model.model_validate(data))

    assert any(issue.category == "source" and issue.severity == "error" for issue in issues)
    assert all(issue.author == kind for issue in issues)


@pytest.mark.parametrize("kind", ["theory", "assignments"])
def test_a_known_citation_must_cover_the_items_topic(demo, context, kind):
    context_data = context.model_dump(mode="json")
    extra = {**context_data["materials"][0], "material_id": "unrelated", "topics": ["Other"]}
    context_data["materials"].append(extra)
    changed_context = GenerationContext.model_validate(context_data)
    data = demo[kind]
    collection = data["sections"] if kind == "theory" else data["lesson_assignments"]
    collection[0]["source_ids"] = ["unrelated"]
    model = Theory if kind == "theory" else AssignmentSet
    checker = check_theory if kind == "theory" else check_assignments

    issues = checker(changed_context, model.model_validate(data))

    assert any(issue.category == "source" for issue in issues)


@pytest.mark.parametrize("kind", ["theory", "assignments"])
def test_unconfirmed_topics_are_reported_for_each_author(demo, context, kind):
    data = demo[kind]
    collection = data["sections"] if kind == "theory" else data["lesson_assignments"]
    collection[0]["topic"] = "Несогласованная тема"
    model = Theory if kind == "theory" else AssignmentSet
    checker = check_theory if kind == "theory" else check_assignments

    issues = checker(context, model.model_validate(data))

    assert any(issue.category == "topic" for issue in issues)


def test_theory_and_practice_must_cover_every_confirmed_topic(context, theory, assignments):
    context_data = context.model_dump(mode="json")
    context_data["brief"]["topics"].append("Вторая тема")
    context_data["materials"][0]["topics"].append("Вторая тема")
    changed_context = GenerationContext.model_validate(context_data)

    assert any(issue.category == "coverage" for issue in check_theory(changed_context, theory))
    assert any(
        issue.category == "coverage" for issue in check_assignments(changed_context, assignments)
    )


@pytest.mark.parametrize(
    "change",
    ["lesson_count", "homework_count", "missing_recipient", "unknown_recipient"],
)
def test_assignment_volume_and_homework_recipients_match_the_brief(demo, context, change):
    data = demo["assignments"]
    if change == "lesson_count":
        data["lesson_assignments"].pop()
    elif change == "homework_count":
        extra = copy.deepcopy(data["homeworks"][0]["assignments"][0])
        extra["assignment_id"] = "homework-extra"
        data["homeworks"][0]["assignments"].append(extra)
    elif change == "missing_recipient":
        data["homeworks"].pop()
    else:
        data["homeworks"][0]["student_id"] = "unknown-student"

    issues = check_assignments(context, AssignmentSet.model_validate(data))

    assert any(issue.category == "coverage" and issue.severity == "error" for issue in issues)


@pytest.mark.parametrize("location", ["lesson", "homework"])
def test_practice_and_each_homework_must_fit_agreed_time(demo, context, location):
    data = demo["assignments"]
    if location == "lesson":
        data["lesson_assignments"][0]["estimated_minutes"] = context.brief.duration_minutes
    else:
        data["homeworks"][1]["assignments"][0]["estimated_minutes"] = (
            context.brief.homework_minutes + 1
        )

    issues = check_assignments(context, AssignmentSet.model_validate(data))

    assert any(issue.category == "timing" and issue.severity == "error" for issue in issues)


def test_no_homework_is_valid_when_both_count_and_time_are_zero(
    context,
    theory,
    assignments,
    review,
):
    context_data = context.model_dump(mode="json")
    context_data["brief"].update(homework_task_count=0, homework_minutes=0)
    changed_context = GenerationContext.model_validate(context_data)
    no_homework = AssignmentSet.model_validate({**assignments.model_dump(), "homeworks": []})
    changed_review = ReviewResult.model_validate(
        {
            **review.model_dump(),
            "theory_digest": content_digest(changed_context, theory),
            "assignments_digest": content_digest(changed_context, no_homework),
        }
    )

    assert check_assignments(changed_context, no_homework) == ()
    package = LessonPackage(
        context=changed_context,
        theory=theory,
        assignments=no_homework,
        review=changed_review,
    )
    assert all(package.for_student(student).homework == () for student in context.brief.student_ids)
    assert any(
        issue.category == "coverage" for issue in check_assignments(changed_context, assignments)
    )


@pytest.mark.parametrize(
    ("author", "target"),
    [("theory", "lesson-1"), ("assignments", "theory-motion"), ("theory", "unknown-id")],
)
def test_review_targets_must_exist_and_belong_to_the_named_author(
    context,
    theory,
    assignments,
    review,
    author,
    target,
):
    changed = ReviewResult.model_validate(
        {
            **review.model_dump(),
            "issues": [
                {
                    "author": author,
                    "target_id": target,
                    "severity": "warning",
                    "category": "physics",
                    "message": "Проверить",
                    "suggestion": "Уточнить",
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="existing IDs belonging to the named author"):
        check_review(context, theory, assignments, changed)


@pytest.mark.parametrize("change", ["unconfirmed", "deterministic_issue", "review_error"])
def test_package_blocks_unconfirmed_invalid_or_rejected_content(package, change):
    data = package.model_dump(mode="json")
    if change == "unconfirmed":
        data["context"]["brief"]["confirmed"] = False
    elif change == "deterministic_issue":
        data["assignments"]["lesson_assignments"][0]["source_ids"] = ["missing-source"]
        context = GenerationContext.model_validate(data["context"])
        assignments = AssignmentSet.model_validate(data["assignments"])
        data["review"]["assignments_digest"] = content_digest(context, assignments)
    else:
        data["review"]["issues"] = [
            {
                "author": "assignments",
                "target_id": "lesson-1",
                "severity": "error",
                "category": "answer",
                "message": "Ошибка ответа",
                "suggestion": "Пересчитать",
            }
        ]
    with pytest.raises(ValidationError):
        LessonPackage.model_validate(data)


def test_warnings_do_not_block_package_approval(package):
    data = package.model_dump(mode="json")
    data["review"]["issues"] = [
        {
            "author": "theory",
            "target_id": "theory-motion",
            "severity": "warning",
            "category": "level",
            "message": "Можно упростить",
            "suggestion": "Сократить объяснение",
        }
    ]
    assert LessonPackage.model_validate(data).review.approved


@pytest.mark.parametrize(
    "change",
    ["theory", "assignments", "brief", "profile", "material_content", "material_source"],
)
def test_review_becomes_stale_after_any_relevant_content_or_context_change(package, change):
    data = package.model_dump(mode="json")
    if change == "theory":
        data["theory"]["sections"][0]["explanation"]["text"] += " Дополнение."
    elif change == "assignments":
        data["assignments"]["lesson_assignments"][0]["answer"]["text"] = "Другой ответ"
    elif change == "brief":
        data["context"]["brief"]["teacher_notes"] = "Новый акцент занятия"
    elif change == "profile":
        data["context"]["students"][0]["common_errors"].append("Новая ошибка ученика")
    elif change == "material_content":
        data["context"]["materials"][0]["content"] += " Уточнение источника."
    else:
        data["context"]["materials"][0]["source"] = "Новый источник, страница 42"

    with pytest.raises(ValidationError, match="review is stale"):
        LessonPackage.model_validate(data)


def test_digest_is_stable_across_json_round_trips(context, theory):
    assert content_digest(context, theory) == content_digest(
        GenerationContext.model_validate_json(context.model_dump_json()),
        Theory.model_validate_json(theory.model_dump_json()),
    )


@pytest.mark.parametrize(
    ("count_field", "time_field"),
    [("lesson_task_count", "duration_minutes"), ("homework_task_count", "homework_minutes")],
)
def test_impossible_volume_is_rejected_in_brief_before_generation(demo, count_field, time_field):
    brief = demo["context"]["brief"]
    brief[count_field] = 3
    brief[time_field] = 2

    with pytest.raises(ValidationError, match="cannot fit even at one minute per task"):
        LessonBrief.model_validate(brief)

    # The boundary itself is a viable request; generated timing still needs its own checks.
    brief[time_field] = 3
    assert getattr(LessonBrief.model_validate(brief), count_field) == 3
