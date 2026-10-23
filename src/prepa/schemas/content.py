"""Telegram-independent contracts for content generation, review and document input."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Id = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")]
Text = Annotated[str, Field(min_length=1, max_length=20_000)]
Topic = Annotated[str, Field(min_length=1, max_length=160)]
Exam = Literal["oge", "ege"]
Author = Literal["theory", "assignments"]
Count = Annotated[int, Field(strict=True, ge=0, le=20)]
Minutes = Annotated[int, Field(strict=True, ge=1, le=180)]


class Contract(BaseModel):
    """Immutable, closed objects: unexpected fields are integration errors."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


def require_unique(values: tuple[str, ...], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


class Versioned(Contract):
    preparation_id: Id
    version: Annotated[int, Field(strict=True, ge=1)]


class StudentProfile(Contract):
    student_id: Id
    grade: Annotated[int, Field(strict=True, ge=9, le=11)]
    exam: Exam
    level: Literal["basic", "intermediate", "advanced"] = "basic"
    mastered_topics: Annotated[tuple[Topic, ...], Field(max_length=100)] = ()
    common_errors: Annotated[tuple[Text, ...], Field(max_length=50)] = ()


class LessonBrief(Versioned):
    student_ids: Annotated[tuple[Id, ...], Field(min_length=1, max_length=2)]
    exam: Exam
    topics: Annotated[tuple[Topic, ...], Field(min_length=1, max_length=8)]
    duration_minutes: Minutes = 60
    theory_level: Literal["basic", "intermediate", "advanced"] = "basic"
    lesson_task_count: Annotated[int, Field(strict=True, ge=1, le=50)] = 4
    homework_task_count: Count = 2
    homework_minutes: Annotated[int, Field(strict=True, ge=0, le=180)] = 20
    teacher_notes: Text | None = None
    confirmed: Annotated[bool, Field(strict=True)] = False

    @model_validator(mode="after")
    def check_brief(self) -> Self:
        require_unique(self.student_ids, "student_ids")
        require_unique(self.topics, "topics")
        if self.lesson_task_count < len(self.topics):
            raise ValueError("lesson_task_count must cover every requested topic")
        if bool(self.homework_task_count) != bool(self.homework_minutes):
            raise ValueError("homework count and time must both be zero or both positive")
        if self.lesson_task_count > self.duration_minutes:
            raise ValueError("lesson tasks cannot fit even at one minute per task")
        if self.homework_task_count > self.homework_minutes:
            raise ValueError("homework tasks cannot fit even at one minute per task")
        return self


class Material(Contract):
    """One supplied library item. source is its real URL, book/page or local provenance."""

    material_id: Id
    title: Text
    source: Text
    exam: Exam
    topics: Annotated[tuple[Topic, ...], Field(min_length=1, max_length=50)]
    content: Text


class GenerationContext(Contract):
    brief: LessonBrief
    students: Annotated[tuple[StudentProfile, ...], Field(min_length=1, max_length=2)]
    materials: Annotated[tuple[Material, ...], Field(min_length=1, max_length=50)]

    @model_validator(mode="after")
    def check_context(self) -> Self:
        require_unique(tuple(s.student_id for s in self.students), "students")
        require_unique(tuple(m.material_id for m in self.materials), "materials")
        if set(self.brief.student_ids) != {s.student_id for s in self.students}:
            raise ValueError("profiles must match exactly the students in the brief")
        if any(s.exam != self.brief.exam for s in self.students):
            raise ValueError("student exams must match the brief")
        if any(m.exam != self.brief.exam for m in self.materials):
            raise ValueError("material exams must match the brief")
        covered = {topic for m in self.materials for topic in m.topics}
        if not set(self.brief.topics) <= covered:
            raise ValueError("supplied materials must cover every requested topic")
        return self


class TextBlock(Contract):
    """Plain text plus separate LaTeX math expressions, without document commands."""

    text: Text
    math: Annotated[tuple[Text, ...], Field(max_length=20)] = ()


class GenerationFailure(Contract):
    """Explicit model refusal when the supplied library cannot support the request."""

    status: Literal["insufficient_material"]
    missing_topics: Annotated[tuple[Topic, ...], Field(min_length=1, max_length=8)]
    reason: Text

    @model_validator(mode="after")
    def unique_topics(self) -> Self:
        require_unique(self.missing_topics, "missing_topics")
        return self


class Formula(Contract):
    expression: Text
    meaning: Text
    conditions: Text
    units: Text


class WorkedExample(Contract):
    statement: TextBlock
    answer: TextBlock
    solution: Annotated[tuple[TextBlock, ...], Field(min_length=1, max_length=20)]


class TheorySection(Contract):
    section_id: Id
    topic: Topic
    title: Text
    explanation: TextBlock
    formulas: Annotated[tuple[Formula, ...], Field(max_length=20)] = ()
    worked_examples: Annotated[tuple[WorkedExample, ...], Field(min_length=1, max_length=3)]
    source_ids: Annotated[tuple[Id, ...], Field(min_length=1, max_length=10)]


class Theory(Versioned):
    sections: Annotated[tuple[TheorySection, ...], Field(min_length=1, max_length=32)]

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        require_unique(tuple(s.section_id for s in self.sections), "section IDs")
        return self


class Assignment(Contract):
    assignment_id: Id
    topic: Topic
    difficulty: Annotated[int, Field(strict=True, ge=1, le=3)]
    estimated_minutes: Minutes
    statement: TextBlock
    answer: TextBlock
    solution: Annotated[tuple[TextBlock, ...], Field(min_length=1, max_length=20)]
    hints: Annotated[tuple[TextBlock, ...], Field(max_length=5)] = ()
    source_ids: Annotated[tuple[Id, ...], Field(min_length=1, max_length=10)]


class Homework(Contract):
    student_id: Id
    rationale: Text
    assignments: Annotated[tuple[Assignment, ...], Field(min_length=1, max_length=20)]


class AssignmentSet(Versioned):
    lesson_assignments: Annotated[tuple[Assignment, ...], Field(min_length=1, max_length=50)]
    homeworks: Annotated[tuple[Homework, ...], Field(max_length=2)]

    def all_assignments(self) -> tuple[Assignment, ...]:
        return self.lesson_assignments + tuple(a for h in self.homeworks for a in h.assignments)

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        require_unique(tuple(h.student_id for h in self.homeworks), "homework recipients")
        require_unique(tuple(a.assignment_id for a in self.all_assignments()), "assignment IDs")
        return self


class ReviewIssue(Contract):
    author: Author
    target_id: Id
    severity: Literal["error", "warning"]
    category: Literal[
        "physics", "units", "answer", "topic", "level", "source", "coverage", "timing"
    ]
    message: Text
    suggestion: Text


class ReviewReport(Versioned):
    """Model-produced findings. The runtime binds them to exact content below."""

    summary: Text
    issues: Annotated[tuple[ReviewIssue, ...], Field(max_length=100)] = ()


class RepairFeedback(Versioned):
    """Code-produced findings for a rejected individual generation, before full review."""

    author: Author
    content_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    issues: Annotated[tuple[ReviewIssue, ...], Field(min_length=1, max_length=200)]

    @model_validator(mode="after")
    def check_author(self) -> Self:
        if any(issue.author != self.author for issue in self.issues):
            raise ValueError("repair feedback must only contain issues for its author")
        return self


class ReviewResult(ReviewReport):
    # The runtime merges bounded model findings with deterministic contract findings.
    issues: Annotated[tuple[ReviewIssue, ...], Field(max_length=400)] = ()
    theory_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    assignments_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]

    @property
    def approved(self) -> bool:
        """Derived in code; the model cannot declare approval while returning errors."""
        return not any(issue.severity == "error" for issue in self.issues)

    def for_author(self, author: Author) -> tuple[ReviewIssue, ...]:
        return tuple(issue for issue in self.issues if issue.author == author)


class StudentAssignment(Contract):
    assignment_id: Id
    topic: Topic
    estimated_minutes: Minutes
    statement: TextBlock
    source_ids: Annotated[tuple[Id, ...], Field(min_length=1, max_length=10)]


class SourceCitation(Contract):
    material_id: Id
    title: Text
    source: Text


class StudentLesson(Versioned):
    """Document input with no practice answers/solutions or another student's homework."""

    student_id: Id
    theory: Theory
    lesson_assignments: Annotated[tuple[StudentAssignment, ...], Field(min_length=1, max_length=50)]
    homework: Annotated[tuple[StudentAssignment, ...], Field(max_length=20)]
    sources: Annotated[tuple[SourceCitation, ...], Field(min_length=1, max_length=50)]

    @model_validator(mode="after")
    def check_document(self) -> Self:
        if (self.theory.preparation_id, self.theory.version) != (self.preparation_id, self.version):
            raise ValueError("student document and theory must have matching identity")
        require_unique(
            tuple(a.assignment_id for a in self.lesson_assignments + self.homework),
            "student assignment IDs",
        )
        source_ids = tuple(s.material_id for s in self.sources)
        require_unique(source_ids, "student source IDs")
        used = {s for section in self.theory.sections for s in section.source_ids}
        used.update(s for a in self.lesson_assignments + self.homework for s in a.source_ids)
        if not used <= set(source_ids):
            raise ValueError("student document must include all cited sources")
        return self


class LessonPackage(Contract):
    """Internal teacher package. Only an approved, matching review can enter it."""

    context: GenerationContext
    theory: Theory
    assignments: AssignmentSet
    review: ReviewResult

    @model_validator(mode="after")
    def check_package(self) -> Self:
        # Local import keeps the individual data contracts independent of quality rules.
        from .validation import check_assignments, check_review, check_theory

        if not self.context.brief.confirmed:
            raise ValueError("the brief must be confirmed")
        issues = check_theory(self.context, self.theory) + check_assignments(
            self.context, self.assignments
        )
        check_review(self.context, self.theory, self.assignments, self.review)
        if issues or not self.review.approved:
            raise ValueError("the package contains blocking review issues")
        return self

    def for_student(self, student_id: str) -> StudentLesson:
        if student_id not in self.context.brief.student_ids:
            raise ValueError("student is not part of this preparation")

        def question(assignment: Assignment) -> StudentAssignment:
            return StudentAssignment(
                assignment_id=assignment.assignment_id,
                topic=assignment.topic,
                estimated_minutes=assignment.estimated_minutes,
                statement=assignment.statement,
                source_ids=assignment.source_ids,
            )

        homework = next(
            (h.assignments for h in self.assignments.homeworks if h.student_id == student_id), ()
        )
        source_ids = {s for section in self.theory.sections for s in section.source_ids}
        source_ids.update(
            s for a in self.assignments.lesson_assignments + homework for s in a.source_ids
        )
        return StudentLesson(
            preparation_id=self.context.brief.preparation_id,
            version=self.context.brief.version,
            student_id=student_id,
            theory=self.theory,
            lesson_assignments=tuple(map(question, self.assignments.lesson_assignments)),
            homework=tuple(map(question, homework)),
            sources=tuple(
                SourceCitation(material_id=m.material_id, title=m.title, source=m.source)
                for m in self.context.materials
                if m.material_id in source_ids
            ),
        )
