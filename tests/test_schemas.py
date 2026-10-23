"""Shared contracts and the boundary between teacher and student documents."""

import copy
import json

import pytest
from pydantic import ValidationError

from prepa.schemas import (
    Assignment,
    AssignmentSet,
    GenerationContext,
    GenerationFailure,
    LessonBrief,
    LessonPackage,
    Material,
    RepairFeedback,
    ReviewIssue,
    ReviewReport,
    ReviewResult,
    StudentAssignment,
    StudentLesson,
    StudentProfile,
    TextBlock,
    Theory,
)
from prepa.schemas.validation import content_digest


@pytest.mark.parametrize(
    "fixture_name",
    ["context", "theory", "assignments", "review", "package"],
)
def test_contract_json_round_trip_is_lossless(request, fixture_name):
    original = request.getfixturevalue(fixture_name)

    restored = type(original).model_validate_json(original.model_dump_json())

    assert restored == original
    assert json.loads(original.model_dump_json()) == original.model_dump(mode="json")
    schema = type(original).model_json_schema()
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize("value", ["", "   ", "with spaces", "bad/path", "a" * 101])
def test_preparation_id_is_safe_and_nonempty(demo, value):
    demo["context"]["brief"]["preparation_id"] = value
    with pytest.raises(ValidationError):
        LessonBrief.model_validate(demo["context"]["brief"])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", 0),
        ("version", True),
        ("version", "1"),
        ("duration_minutes", 0),
        ("duration_minutes", 181),
        ("lesson_task_count", 0),
        ("lesson_task_count", 51),
        ("lesson_task_count", 2.0),
        ("homework_task_count", -1),
        ("homework_task_count", 21),
        ("homework_minutes", -1),
        ("homework_minutes", 181),
        ("confirmed", "true"),
        ("confirmed", 1),
        ("exam", "other"),
        ("theory_level", "expert"),
        ("topics", []),
        ("topics", [" "]),
        ("topics", [f"topic-{i}" for i in range(9)]),
        ("student_ids", []),
        ("student_ids", ["a", "b", "c"]),
    ],
)
def test_brief_rejects_invalid_limits_and_implicit_coercion(demo, field, value):
    demo["context"]["brief"][field] = value
    with pytest.raises(ValidationError):
        LessonBrief.model_validate(demo["context"]["brief"])


@pytest.mark.parametrize(
    ("count", "minutes"),
    [(0, 1), (1, 0)],
)
def test_homework_count_and_time_must_agree(demo, count, minutes):
    brief = demo["context"]["brief"]
    brief.update(homework_task_count=count, homework_minutes=minutes)
    with pytest.raises(ValidationError, match="both be zero or both positive"):
        LessonBrief.model_validate(brief)


def test_each_topic_requires_a_lesson_assignment(demo):
    brief = demo["context"]["brief"]
    brief.update(topics=["one", "two"], lesson_task_count=1)
    with pytest.raises(ValidationError, match="cover every requested topic"):
        LessonBrief.model_validate(brief)


@pytest.mark.parametrize("field", ["student_ids", "topics"])
def test_brief_rejects_duplicates(demo, field):
    brief = demo["context"]["brief"]
    brief[field] = [brief[field][0], brief[field][0]]
    with pytest.raises(ValidationError, match="unique"):
        LessonBrief.model_validate(brief)


@pytest.mark.parametrize(
    ("field", "value"),
    [("grade", 8), ("grade", 12), ("grade", True), ("level", "expert")],
)
def test_student_profile_rejects_invalid_grade_or_level(demo, field, value):
    student = demo["context"]["students"][0]
    student[field] = value
    with pytest.raises(ValidationError):
        StudentProfile.model_validate(student)


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate", "wrong_exam"])
def test_profiles_must_match_exactly_the_confirmed_students(demo, change):
    context = demo["context"]
    if change == "missing":
        context["students"].pop()
    elif change == "extra":
        context["students"][1]["student_id"] = "unknown-student"
    elif change == "duplicate":
        context["students"][1] = copy.deepcopy(context["students"][0])
    else:
        context["students"][0]["exam"] = "ege"
    with pytest.raises(ValidationError):
        GenerationContext.model_validate(context)


@pytest.mark.parametrize("change", ["empty", "duplicate", "wrong_exam", "missing_topic"])
def test_context_requires_unique_matching_materials_covering_the_brief(demo, change):
    context = demo["context"]
    if change == "empty":
        context["materials"] = []
    elif change == "duplicate":
        context["materials"].append(copy.deepcopy(context["materials"][0]))
    elif change == "wrong_exam":
        context["materials"][0]["exam"] = "ege"
    else:
        context["materials"][0]["topics"] = ["Another topic"]
    with pytest.raises(ValidationError):
        GenerationContext.model_validate(context)


@pytest.mark.parametrize("field", ["title", "source", "content"])
def test_supplied_material_cannot_have_blank_fields(demo, field):
    material = demo["context"]["materials"][0]
    material[field] = " \n "
    with pytest.raises(ValidationError):
        Material.model_validate(material)


@pytest.mark.parametrize("value", ["", "\n\t", "x" * 20_001])
def test_text_blocks_reject_blank_or_unbounded_text(value):
    with pytest.raises(ValidationError):
        TextBlock(text=value)


def test_contracts_trim_text_and_are_immutable():
    block = TextBlock(text="  Сила тяжести  ", math=["  F = mg  "])
    assert block.text == "Сила тяжести"
    assert block.math == ("F = mg",)
    with pytest.raises(ValidationError, match="frozen"):
        block.text = "changed"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("difficulty", 0),
        ("difficulty", 4),
        ("difficulty", True),
        ("estimated_minutes", 0),
        ("estimated_minutes", 181),
        ("estimated_minutes", "5"),
        ("source_ids", []),
        ("solution", []),
        ("answer", {"text": " "}),
        ("statement", {"text": " "}),
    ],
)
def test_assignments_require_complete_bounded_teacher_content(demo, field, value):
    assignment = demo["assignments"]["lesson_assignments"][0]
    assignment[field] = value
    with pytest.raises(ValidationError):
        Assignment.model_validate(assignment)


def test_theory_requires_a_worked_example(demo):
    demo["theory"]["sections"][0]["worked_examples"] = []
    with pytest.raises(ValidationError):
        Theory.model_validate(demo["theory"])


def test_theory_section_ids_are_unique(demo):
    demo["theory"]["sections"].append(copy.deepcopy(demo["theory"]["sections"][0]))
    with pytest.raises(ValidationError, match="section IDs must be unique"):
        Theory.model_validate(demo["theory"])


@pytest.mark.parametrize("location", ["lesson", "homework", "recipients"])
def test_assignment_ids_and_homework_recipients_are_globally_unique(demo, location):
    assignments = demo["assignments"]
    if location == "lesson":
        assignments["lesson_assignments"][1]["assignment_id"] = "lesson-1"
    elif location == "homework":
        assignments["homeworks"][0]["assignments"][0]["assignment_id"] = "lesson-1"
    else:
        assignments["homeworks"][1]["student_id"] = "student-a"
    with pytest.raises(ValidationError, match="unique"):
        AssignmentSet.model_validate(assignments)


@pytest.mark.parametrize("fixture_name", ["context", "theory", "assignments", "review", "package"])
def test_unknown_top_level_fields_are_integration_errors(request, fixture_name):
    original = request.getfixturevalue(fixture_name)
    data = original.model_dump(mode="json")
    data["unexpected"] = "silently dropping this would hide a contract mismatch"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        type(original).model_validate(data)


def test_unknown_nested_fields_are_rejected(demo):
    demo["theory"]["sections"][0]["worked_examples"][0]["answer"]["raw_html"] = "<b>1</b>"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        Theory.model_validate(demo["theory"])


def test_review_approval_is_derived_and_findings_are_addressed_by_author(demo, review):
    issue = ReviewIssue(
        author="assignments",
        target_id="lesson-1",
        severity="error",
        category="answer",
        message="Неверный ответ",
        suggestion="Пересчитать результат",
    )
    failed = ReviewResult.model_validate({**review.model_dump(), "issues": [issue]})
    assert not failed.approved
    assert failed.for_author("assignments") == (issue,)
    assert failed.for_author("theory") == ()
    warning = issue.model_copy(update={"severity": "warning"})
    assert ReviewResult.model_validate({**review.model_dump(), "issues": [warning]}).approved
    demo["review"]["approved"] = True
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ReviewReport.model_validate(demo["review"])


@pytest.mark.parametrize("student_id", ["student-a", "student-b"])
def test_student_document_contains_only_own_questions_and_public_sources(package, student_id):
    lesson = package.for_student(student_id)
    data = lesson.model_dump(mode="json")
    own = next(h for h in package.assignments.homeworks if h.student_id == student_id)
    others = {
        a.assignment_id
        for h in package.assignments.homeworks
        if h.student_id != student_id
        for a in h.assignments
    }

    assert lesson.student_id == student_id
    assert {a.assignment_id for a in lesson.homework} == {a.assignment_id for a in own.assignments}
    assert not others.intersection(a.assignment_id for a in lesson.homework)
    assert lesson.theory == package.theory
    assert lesson.theory.sections[0].worked_examples[0].solution
    for assignment in data["lesson_assignments"] + data["homework"]:
        assert set(assignment) == {
            "assignment_id",
            "topic",
            "estimated_minutes",
            "statement",
            "source_ids",
        }
    teacher_questions = package.assignments.lesson_assignments + own.assignments
    student_questions = lesson.lesson_assignments + lesson.homework
    assert {a.assignment_id: a.source_ids for a in student_questions} == {
        a.assignment_id: a.source_ids for a in teacher_questions
    }
    cited_ids = {source.material_id for source in lesson.sources}
    assert all(set(question.source_ids) <= cited_ids for question in student_questions)
    assert all(set(source) == {"material_id", "title", "source"} for source in data["sources"])
    assert not {"students", "context", "rationale", "review"}.intersection(data)
    assert StudentLesson.model_validate_json(lesson.model_dump_json()) == lesson


def test_student_document_does_not_leak_sensitive_fields_or_other_students_sources(
    context,
    theory,
    assignments,
    review,
):
    context_data = context.model_dump(mode="json")
    context_data["students"][0]["common_errors"] = ["PRIVATE_PROFILE_SENTINEL"]
    context_data["materials"][0]["content"] = "PRIVATE_RAW_MATERIAL_SENTINEL"
    other_source = copy.deepcopy(context_data["materials"][0])
    other_source.update(material_id="private-b-source", title="Only B homework uses this")
    unused_source = {**other_source, "material_id": "unused-source"}
    context_data["materials"].extend([other_source, unused_source])
    changed_context = GenerationContext.model_validate(context_data)
    assignment_data = assignments.model_dump(mode="json")
    assignment_data["homeworks"][0]["rationale"] = "PRIVATE_RATIONALE_SENTINEL"
    for assignment in assignment_data["lesson_assignments"]:
        assignment["answer"] = {"text": "PRIVATE_ANSWER_SENTINEL"}
        assignment["solution"] = [{"text": "PRIVATE_SOLUTION_SENTINEL"}]
        assignment["hints"] = [{"text": "PRIVATE_HINT_SENTINEL"}]
    assignment_data["homeworks"][1]["assignments"][0]["source_ids"] = ["private-b-source"]
    changed_assignments = AssignmentSet.model_validate(assignment_data)
    changed_review = ReviewResult.model_validate(
        {
            **review.model_dump(),
            "theory_digest": content_digest(changed_context, theory),
            "assignments_digest": content_digest(changed_context, changed_assignments),
        }
    )
    package = LessonPackage(
        context=changed_context,
        theory=theory,
        assignments=changed_assignments,
        review=changed_review,
    )

    student_a = package.for_student("student-a")
    serialized = student_a.model_dump_json()
    assert "PRIVATE_" not in serialized
    assert {source.material_id for source in student_a.sources} == {"demo-motion"}
    assert {source.material_id for source in package.for_student("student-b").sources} == {
        "demo-motion",
        "private-b-source",
    }


@pytest.mark.parametrize("field", ["answer", "solution", "hints", "rationale"])
def test_student_assignment_contract_rejects_accidental_teacher_fields(package, field):
    data = package.for_student("student-a").lesson_assignments[0].model_dump()
    data[field] = "teacher-only content"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        StudentAssignment.model_validate(data)


def test_student_document_rejects_unknown_student(package):
    with pytest.raises(ValueError, match="not part of this preparation"):
        package.for_student("unknown-student")


@pytest.mark.parametrize("field", ["preparation_id", "version"])
def test_standalone_student_document_rejects_theory_from_another_preparation(package, field):
    data = package.for_student("student-a").model_dump(mode="json")
    data["theory"][field] = "another-preparation" if field == "preparation_id" else 2
    with pytest.raises(ValidationError):
        StudentLesson.model_validate_json(json.dumps(data, ensure_ascii=False))


@pytest.mark.parametrize("location", ["lesson", "lesson_and_homework", "citations"])
def test_standalone_student_document_rejects_duplicate_ids(package, location):
    data = package.for_student("student-a").model_dump(mode="json")
    if location == "lesson":
        data["lesson_assignments"][1]["assignment_id"] = data["lesson_assignments"][0][
            "assignment_id"
        ]
    elif location == "lesson_and_homework":
        data["homework"][0]["assignment_id"] = data["lesson_assignments"][0]["assignment_id"]
    else:
        data["sources"].append(copy.deepcopy(data["sources"][0]))
    with pytest.raises(ValidationError, match="unique"):
        StudentLesson.model_validate_json(json.dumps(data, ensure_ascii=False))


@pytest.mark.parametrize("location", ["theory", "lesson", "homework"])
def test_standalone_student_document_requires_every_referenced_citation(package, location):
    data = package.for_student("student-a").model_dump(mode="json")
    if location == "theory":
        item = data["theory"]["sections"][0]
    elif location == "lesson":
        item = data["lesson_assignments"][0]
    else:
        item = data["homework"][0]
    item["source_ids"] = ["uncited-source"]
    with pytest.raises(ValidationError):
        StudentLesson.model_validate_json(json.dumps(data, ensure_ascii=False))


@pytest.mark.parametrize("source_ids", [[], [f"source-{i}" for i in range(11)]])
def test_student_assignment_requires_nonempty_bounded_attribution(package, source_ids):
    data = package.for_student("student-a").lesson_assignments[0].model_dump(mode="json")
    data["source_ids"] = source_ids
    with pytest.raises(ValidationError):
        StudentAssignment.model_validate_json(json.dumps(data, ensure_ascii=False))


@pytest.mark.parametrize(
    ("field", "id_field", "limit"),
    [
        ("lesson_assignments", "assignment_id", 50),
        ("homework", "assignment_id", 20),
        ("sources", "material_id", 50),
    ],
)
def test_student_document_collections_are_bounded_for_document_rendering(
    package,
    field,
    id_field,
    limit,
):
    data = package.for_student("student-a").model_dump(mode="json")
    original = copy.deepcopy(data[field][0])
    # Preserve the first item because its ID may be referenced elsewhere in the document.
    data[field] = [original] + [
        {**copy.deepcopy(original), id_field: f"{field}-{index}"} for index in range(1, limit)
    ]
    document = StudentLesson.model_validate_json(json.dumps(data, ensure_ascii=False))
    assert len(getattr(document, field)) == limit
    data[field].append({**original, id_field: f"{field}-extra"})
    with pytest.raises(ValidationError) as error:
        StudentLesson.model_validate_json(json.dumps(data, ensure_ascii=False))
    assert any(
        item["loc"] == (field,) and item["type"] == "too_long" for item in error.value.errors()
    )


@pytest.mark.parametrize(
    ("kind", "path", "limit"),
    [
        ("theory", ("sections",), 32),
        ("theory", ("sections", 0, "worked_examples"), 3),
        ("theory", ("sections", 0, "worked_examples", 0, "solution"), 20),
        ("theory", ("sections", 0, "source_ids"), 10),
        ("assignments", ("lesson_assignments", 0, "solution"), 20),
        ("assignments", ("lesson_assignments", 0, "statement", "math"), 20),
        ("assignments", ("lesson_assignments", 0, "source_ids"), 10),
        ("review", ("issues",), 100),
    ],
)
def test_response_collections_accept_limit_and_reject_oversized_json(demo, kind, path, limit):
    """Provider JSON cannot bypass bounded collections, including deeply nested ones."""
    data = demo[kind]
    owner = data
    for component in path[:-1]:
        owner = owner[component]
    field = path[-1]
    if field == "issues":
        prototype = {
            "author": "theory",
            "target_id": "theory-motion",
            "severity": "warning",
            "category": "level",
            "message": "Уточнить пример",
            "suggestion": "Добавить пояснение",
        }
    elif field == "math":
        prototype = "s = v t"
    else:
        prototype = owner[field][0]
    owner[field] = [copy.deepcopy(prototype) for _ in range(limit)]
    if field == "sections":
        for index, section in enumerate(owner[field]):
            section["section_id"] = f"section-{index}"
    elif field == "source_ids":
        owner[field] = [f"source-{index}" for index in range(limit)]
    model = {"theory": Theory, "assignments": AssignmentSet, "review": ReviewReport}[kind]

    model.model_validate_json(json.dumps(data, ensure_ascii=False))
    owner[field].append(copy.deepcopy(prototype))

    with pytest.raises(ValidationError) as error:
        model.model_validate_json(json.dumps(data, ensure_ascii=False))
    assert any(item["loc"] == path and item["type"] == "too_long" for item in error.value.errors())


def test_repair_feedback_round_trip_binds_findings_to_one_content(context, theory):
    feedback = RepairFeedback(
        preparation_id=context.brief.preparation_id,
        version=context.brief.version,
        author="theory",
        content_digest=content_digest(context, theory),
        issues=[
            ReviewIssue(
                author="theory",
                target_id="theory-motion",
                severity="error",
                category="source",
                message="Неверный источник",
                suggestion="Использовать переданный материал",
            )
        ],
    )

    assert RepairFeedback.model_validate_json(feedback.model_dump_json()) == feedback
    assert feedback.content_digest == content_digest(context, theory)
    data = feedback.model_dump(mode="json")
    data["approved"] = True
    with pytest.raises(ValidationError, match="extra_forbidden"):
        RepairFeedback.model_validate(data)


@pytest.mark.parametrize("change", ["empty", "too_many", "wrong_author", "bad_digest"])
def test_repair_feedback_rejects_unactionable_or_mismatched_findings(context, theory, change):
    issue = {
        "author": "theory",
        "target_id": "theory-motion",
        "severity": "error",
        "category": "coverage",
        "message": "Пропущена тема",
        "suggestion": "Добавить тему",
    }
    data = {
        "preparation_id": context.brief.preparation_id,
        "version": context.brief.version,
        "author": "theory",
        "content_digest": content_digest(context, theory),
        "issues": [issue],
    }
    if change == "empty":
        data["issues"] = []
    elif change == "too_many":
        data["issues"] = [issue] * 201
    elif change == "wrong_author":
        issue["author"] = "assignments"
    else:
        data["content_digest"] = "not-a-content-digest"
    with pytest.raises(ValidationError):
        RepairFeedback.model_validate_json(json.dumps(data, ensure_ascii=False))


def test_insufficient_material_is_a_structured_closed_round_trippable_response():
    failure = GenerationFailure(
        status="insufficient_material",
        missing_topics=["Электродинамика"],
        reason="В библиотеке нет материала по запрошенной теме.",
    )
    assert GenerationFailure.model_validate_json(failure.model_dump_json()) == failure
    assert failure.missing_topics == ("Электродинамика",)
    with pytest.raises(ValidationError, match="extra_forbidden"):
        GenerationFailure.model_validate({**failure.model_dump(), "invented_answer": "answer"})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "success"),
        ("missing_topics", []),
        ("missing_topics", [" "]),
        ("missing_topics", ["Электродинамика", "Электродинамика"]),
        ("missing_topics", [f"topic-{i}" for i in range(9)]),
        ("reason", " \n "),
    ],
)
def test_material_refusal_must_explain_missing_topics(field, value):
    data = {
        "status": "insufficient_material",
        "missing_topics": ["Электродинамика"],
        "reason": "Недостаточно проверенного материала.",
    }
    data[field] = value
    with pytest.raises(ValidationError):
        GenerationFailure.model_validate_json(json.dumps(data, ensure_ascii=False))


def test_internal_feedback_can_exceed_the_provider_report_limit(context, theory, review):
    """Local findings must survive merging even when the model's list is already full."""
    findings = [
        ReviewIssue(
            author="theory",
            target_id="theory-motion",
            severity="error",
            category="coverage",
            message=f"Локальная ошибка {index}",
            suggestion="Исправить содержание",
        )
        for index in range(121)
    ]
    feedback = RepairFeedback(
        preparation_id=context.brief.preparation_id,
        version=context.brief.version,
        author="theory",
        content_digest=content_digest(context, theory),
        issues=findings,
    )
    merged_review = ReviewResult.model_validate({**review.model_dump(), "issues": findings})

    assert len(feedback.issues) == len(merged_review.issues) == 121
    assert not merged_review.approved
    with pytest.raises(ValidationError):
        ReviewReport.model_validate(
            {
                "preparation_id": context.brief.preparation_id,
                "version": context.brief.version,
                "summary": "Слишком много замечаний модели",
                "issues": findings,
            }
        )
