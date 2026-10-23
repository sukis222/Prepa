"""Provider-free behavior tests; recorded responses do not prove LLM physics quality."""

import asyncio
import copy
import json
from typing import Any

import pytest
from pydantic import ValidationError

from prepa.agents.assignments import AssignmentsAgent
from prepa.agents.reviewer import ReviewerAgent
from prepa.agents.runtime import (
    AgentResponseError,
    ContentValidationError,
    InsufficientMaterialsError,
)
from prepa.agents.theory import TheoryAgent
from prepa.schemas import (
    AssignmentSet,
    GenerationContext,
    LessonPackage,
    RepairFeedback,
    ReviewIssue,
    ReviewResult,
    Theory,
)
from prepa.schemas.validation import check_assignments, check_theory, content_digest

ROLES = ("theory", "assignments", "reviewer")


@pytest.mark.parametrize("agent_type", (TheoryAgent, AssignmentsAgent, ReviewerAgent))
def test_default_agent_timeout_is_120_seconds(agent_type: Any) -> None:
    assert agent_type(FakeLLM()).timeout_seconds == 120


class FakeLLM:
    """Return queued responses and retain the complete structured provider boundary."""

    def __init__(self, *responses: Any) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def generate(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("unexpected provider call or automatic retry")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class WaitingLLM:
    """An unfinished provider request, released only by task cancellation."""

    def __init__(self) -> None:
        self.calls = 0
        self.started = asyncio.Event()
        self.cancelled = False

    async def generate(self, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        raise AssertionError("the waiting provider must never complete")


async def invoke(
    role: str,
    llm: Any,
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
    *,
    timeout_seconds: float = 60,
    max_response_chars: int = 200_000,
) -> Any:
    options = {"timeout_seconds": timeout_seconds, "max_response_chars": max_response_chars}
    if role == "theory":
        return await TheoryAgent(llm, **options).generate(context)
    if role == "assignments":
        return await AssignmentsAgent(llm, **options).generate(context, theory)
    if role == "reviewer":
        return await ReviewerAgent(llm, **options).review(context, theory, assignments)
    raise AssertionError(f"unknown test role: {role}")


def response_for(role: str, demo: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(demo["review" if role == "reviewer" else role])


def issue_for(author: str, target: str) -> ReviewIssue:
    return ReviewIssue.model_validate(
        {
            "author": author,
            "target_id": target,
            "severity": "error",
            "category": "answer",
            "message": "Численный ответ неверен.",
            "suggestion": "Пересчитайте ответ с указанными величинами.",
        }
    )


def review_with_issues(
    review: ReviewResult, theory: Theory, assignments: AssignmentSet
) -> ReviewResult:
    return review.model_copy(
        update={
            "issues": (
                issue_for("theory", theory.sections[0].section_id),
                issue_for("assignments", assignments.lesson_assignments[0].assignment_id),
            )
        }
    )


def large_invalid_assignment_set(
    context: GenerationContext, assignments: AssignmentSet
) -> tuple[GenerationContext, AssignmentSet]:
    """A schema-valid maximum-size set with more than 100 semantic contract issues."""
    context_payload = context.model_dump(mode="json")
    context_payload["brief"].update(
        {
            "lesson_task_count": 20,
            "homework_task_count": 20,
            "duration_minutes": 180,
            "homework_minutes": 180,
        }
    )
    payload = assignments.model_dump(mode="json")
    template = copy.deepcopy(payload["lesson_assignments"][0])
    template.update({"topic": "other-topic", "source_ids": ["missing"], "estimated_minutes": 1})

    def item(identifier: str) -> dict[str, Any]:
        result = copy.deepcopy(template)
        result["assignment_id"] = identifier
        return result

    payload["lesson_assignments"] = [item(f"large-lesson-{i}") for i in range(20)]
    for recipient, homework in enumerate(payload["homeworks"]):
        homework["assignments"] = [item(f"large-homework-{recipient}-{i}") for i in range(20)]
    return GenerationContext.model_validate(context_payload), AssignmentSet.model_validate(payload)


def test_complete_generation_chain_uses_structured_context_and_review(
    demo: dict[str, Any], context: GenerationContext
) -> None:
    llm = FakeLLM(demo["theory"], demo["assignments"], demo["review"])

    async def scenario() -> LessonPackage:
        theory = await TheoryAgent(llm).generate(context)
        assignments = await AssignmentsAgent(llm).generate(context, theory)
        review = await ReviewerAgent(llm).review(context, theory, assignments)
        return LessonPackage(context=context, theory=theory, assignments=assignments, review=review)

    package = asyncio.run(scenario())

    assert package.review.approved
    assert package.review.theory_digest == content_digest(context, package.theory)
    assert package.review.assignments_digest == content_digest(context, package.assignments)
    assert len(llm.calls) == 3
    assert not llm.responses
    assert len({call["system_prompt"] for call in llm.calls}) == 3
    for call, schema in zip(llm.calls, ("Theory", "AssignmentSet", "ReviewReport"), strict=True):
        assert call["system_prompt"].strip()
        assert call["response_schema"]["title"] == schema
        variants = call["response_schema"]["$defs"]
        assert variants[schema]["additionalProperties"] is False
        assert variants["GenerationFailure"]["additionalProperties"] is False
        assert json.loads(call["user_prompt"])["context"] == context.model_dump(mode="json")
    assignments_input = json.loads(llm.calls[1]["user_prompt"])
    review_input = json.loads(llm.calls[2]["user_prompt"])
    assert assignments_input["theory"] == package.theory.model_dump(mode="json")
    assert review_input["theory"] == package.theory.model_dump(mode="json")
    assert review_input["assignments"] == package.assignments.model_dump(mode="json")
    assert review_input["contract_issues"] == []
    review_schema = llm.calls[2]["response_schema"]["$defs"]["ReviewReport"]
    assert "theory_digest" not in review_schema["properties"]


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("as_json", (False, True), ids=("object", "json-string"))
def test_agents_accept_both_supported_provider_formats(
    role: str,
    as_json: bool,
    demo: dict[str, Any],
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    response = response_for(role, demo)
    llm = FakeLLM(json.dumps(response, ensure_ascii=False) if as_json else response)
    result = asyncio.run(invoke(role, llm, context, theory, assignments))
    assert result.preparation_id == context.brief.preparation_id
    assert result.version == context.brief.version
    assert len(llm.calls) == 1


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("as_json", (False, True), ids=("object", "json-string"))
def test_insufficient_material_is_a_typed_failure_without_approval_or_retry(
    role: str,
    as_json: bool,
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    failure = {
        "status": "insufficient_material",
        "missing_topics": list(context.brief.topics),
        "reason": "PRIVATE_SOURCE_DETAIL: в библиотеке отсутствует необходимое объяснение.",
    }
    llm = FakeLLM(json.dumps(failure, ensure_ascii=False) if as_json else failure)
    with pytest.raises(InsufficientMaterialsError) as caught:
        asyncio.run(invoke(role, llm, context, theory, assignments))
    assert caught.value.failure.model_dump(mode="json") == failure
    assert "PRIVATE_SOURCE_DETAIL" not in str(caught.value)
    assert len(llm.calls) == 1


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("bad_topics", ("unknown", "duplicate"))
def test_material_failure_must_only_address_unique_requested_topics(
    role: str,
    bad_topics: str,
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    topics = (
        ["unsolicited-topic"]
        if bad_topics == "unknown"
        else [context.brief.topics[0], context.brief.topics[0]]
    )
    llm = FakeLLM(
        {
            "status": "insufficient_material",
            "missing_topics": topics,
            "reason": "Требуется дополнительный источник.",
        }
    )
    with pytest.raises(AgentResponseError):
        asyncio.run(invoke(role, llm, context, theory, assignments))
    assert len(llm.calls) == 1


@pytest.mark.parametrize("role", ROLES)
def test_confirmation_precedes_every_provider_call(
    role: str,
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    unconfirmed = context.model_copy(
        update={"brief": context.brief.model_copy(update={"confirmed": False})}
    )
    llm = FakeLLM()
    with pytest.raises(ValueError, match="confirmation"):
        asyncio.run(invoke(role, llm, unconfirmed, theory, assignments))
    assert llm.calls == []


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize(
    "failure",
    (
        "malformed-json",
        "markdown",
        "missing-field",
        "extra-field",
        "wrong-type",
        "json-array",
        "list",
        "none",
        "number",
    ),
)
def test_invalid_provider_responses_fail_once_without_leaking_output(
    role: str,
    failure: str,
    demo: dict[str, Any],
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    response: Any = response_for(role, demo)
    private_marker = "PRIVATE_PROVIDER_RESPONSE_MARKER"
    if failure == "malformed-json":
        response = '{"' + private_marker
    elif failure == "markdown":
        response = f"```json\n{json.dumps(response)}\n```"
    elif failure == "missing-field":
        del response["preparation_id"]
    elif failure == "extra-field":
        response["unexpected"] = private_marker
    elif failure == "wrong-type":
        response["version"] = private_marker
    elif failure == "json-array":
        response = json.dumps([response])
    elif failure == "list":
        response = [response]
    elif failure == "none":
        response = None
    elif failure == "number":
        response = 42
    llm = FakeLLM(response)
    with pytest.raises(AgentResponseError) as caught:
        asyncio.run(invoke(role, llm, context, theory, assignments))
    assert private_marker not in str(caught.value)
    assert len(llm.calls) == 1


@pytest.mark.parametrize("role", ROLES)
def test_provider_error_is_propagated_without_retry(
    role: str,
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    failure = RuntimeError("provider unavailable")
    llm = FakeLLM(failure)
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(invoke(role, llm, context, theory, assignments))
    assert caught.value is failure
    assert len(llm.calls) == 1


@pytest.mark.parametrize("role", ROLES)
def test_timeout_cancels_the_provider_without_retry(
    role: str,
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    async def scenario() -> WaitingLLM:
        llm = WaitingLLM()
        with pytest.raises(TimeoutError):
            await invoke(role, llm, context, theory, assignments, timeout_seconds=0.01)
        return llm

    llm = asyncio.run(scenario())
    assert llm.calls == 1
    assert llm.cancelled


@pytest.mark.parametrize("role", ROLES)
def test_caller_cancellation_reaches_provider_without_retry(
    role: str,
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    async def scenario() -> WaitingLLM:
        llm = WaitingLLM()
        task = asyncio.create_task(invoke(role, llm, context, theory, assignments))
        await asyncio.wait_for(llm.started.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return llm

    llm = asyncio.run(scenario())
    assert llm.calls == 1
    assert llm.cancelled


@pytest.mark.parametrize("timeout", (0, -1, float("inf"), float("-inf"), float("nan")))
@pytest.mark.parametrize("agent_type", (TheoryAgent, AssignmentsAgent, ReviewerAgent))
def test_invalid_timeouts_fail_at_construction(timeout: float, agent_type: Any) -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        agent_type(FakeLLM(), timeout_seconds=timeout)


@pytest.mark.parametrize("limit", (0, -1, True, 2.5))
def test_response_size_limit_must_be_a_positive_integer(limit: Any) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        TheoryAgent(FakeLLM(), max_response_chars=limit)


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("as_json", (False, True), ids=("object", "json-string"))
def test_response_size_boundary_is_enforced_before_schema_parsing(
    role: str,
    as_json: bool,
    demo: dict[str, Any],
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    data = response_for(role, demo)
    serialized = json.dumps(data, ensure_ascii=False)
    response = serialized if as_json else data
    accepted = FakeLLM(response)
    result = asyncio.run(
        invoke(role, accepted, context, theory, assignments, max_response_chars=len(serialized))
    )
    assert result.preparation_id == context.brief.preparation_id
    rejected = FakeLLM(response)
    with pytest.raises(AgentResponseError, match="max_response_chars"):
        asyncio.run(
            invoke(
                role, rejected, context, theory, assignments, max_response_chars=len(serialized) - 1
            )
        )
    assert len(accepted.calls) == len(rejected.calls) == 1


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("bad_value", ("set", "cycle", "nan"))
def test_non_json_dictionary_values_fail_as_redacted_response_errors(
    role: str,
    bad_value: str,
    demo: dict[str, Any],
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    response = response_for(role, demo)
    marker = "PRIVATE_DICTIONARY_VALUE"
    if bad_value == "set":
        response[marker] = {marker}
    elif bad_value == "cycle":
        response[marker] = response
    else:
        response[marker] = float("nan")
    llm = FakeLLM(response)
    with pytest.raises(AgentResponseError) as caught:
        asyncio.run(invoke(role, llm, context, theory, assignments))
    assert marker not in str(caught.value)
    assert len(llm.calls) == 1


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("field,value", (("version", 2), ("preparation_id", "other-preparation")))
def test_generated_identity_must_match_current_brief(
    role: str,
    field: str,
    value: Any,
    demo: dict[str, Any],
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    response = response_for(role, demo)
    response[field] = value
    llm = FakeLLM(response)
    with pytest.raises(AgentResponseError):
        asyncio.run(invoke(role, llm, context, theory, assignments))
    assert len(llm.calls) == 1


@pytest.mark.parametrize(
    "role,input_kind",
    (("assignments", "theory"), ("reviewer", "theory"), ("reviewer", "assignments")),
)
@pytest.mark.parametrize("field,value", (("version", 2), ("preparation_id", "other-preparation")))
def test_mismatched_caller_input_is_rejected_before_provider_call(
    role: str,
    input_kind: str,
    field: str,
    value: Any,
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    if input_kind == "theory":
        theory = theory.model_copy(update={field: value})
    else:
        assignments = assignments.model_copy(update={field: value})
    llm = FakeLLM()
    with pytest.raises(ValueError, match="match the current brief") as caught:
        asyncio.run(invoke(role, llm, context, theory, assignments))
    assert type(caught.value) is ValueError
    assert llm.calls == []


@pytest.mark.parametrize("role", ("theory", "assignments"))
@pytest.mark.parametrize("source_ids", (["unknown-source"], ["demo-motion", "demo-motion"]))
def test_authors_reject_unknown_and_duplicate_source_ids(
    role: str,
    source_ids: list[str],
    demo: dict[str, Any],
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    response = response_for(role, demo)
    target = response["sections" if role == "theory" else "lesson_assignments"][0]
    target["source_ids"] = source_ids
    llm = FakeLLM(response)
    with pytest.raises(ContentValidationError) as caught:
        asyncio.run(invoke(role, llm, context, theory, assignments))
    assert any(issue.category == "source" and issue.author == role for issue in caught.value.issues)
    assert len(llm.calls) == 1


def test_assignments_reject_invalid_input_theory_before_provider_call(
    demo: dict[str, Any],
    context: GenerationContext,
    theory: Theory,
) -> None:
    invalid_theory = theory.model_copy(
        update={"sections": (theory.sections[0].model_copy(update={"source_ids": ("unknown",)}),)}
    )
    llm = FakeLLM(demo["assignments"])
    with pytest.raises(ContentValidationError) as caught:
        asyncio.run(AssignmentsAgent(llm).generate(context, invalid_theory))
    assert caught.value.issues[0].author == "theory"
    assert llm.calls == []


@pytest.mark.parametrize("echo_local_issue", (False, True), ids=("waive-all", "echo-one"))
def test_reviewer_cannot_waive_local_findings_and_deduplicates_identical_findings(
    echo_local_issue: bool,
    demo: dict[str, Any],
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    invalid_theory = theory.model_copy(
        update={"sections": (theory.sections[0].model_copy(update={"source_ids": ("unknown",)}),)}
    )
    invalid_assignments = assignments.model_copy(update={"homeworks": ()})
    expected = check_theory(context, invalid_theory) + check_assignments(
        context, invalid_assignments
    )
    response = copy.deepcopy(demo["review"])
    response["issues"] = [expected[0].model_dump(mode="json")] if echo_local_issue else []
    llm = FakeLLM(response)
    reviewed = asyncio.run(ReviewerAgent(llm).review(context, invalid_theory, invalid_assignments))

    assert reviewed.issues == expected
    assert not reviewed.approved
    payload = json.loads(llm.calls[0]["user_prompt"])
    assert payload["contract_issues"] == [item.model_dump(mode="json") for item in expected]
    with pytest.raises(ValidationError, match="blocking review issues"):
        LessonPackage(
            context=context, theory=invalid_theory, assignments=invalid_assignments, review=reviewed
        )


@pytest.mark.parametrize("bad_address", ("unknown-target", "wrong-author", "unknown-author"))
def test_reviewer_rejects_findings_that_cannot_be_routed(
    bad_address: str,
    demo: dict[str, Any],
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    response = copy.deepcopy(demo["review"])
    issue = issue_for("theory", theory.sections[0].section_id).model_dump(mode="json")
    if bad_address == "unknown-target":
        issue["target_id"] = "missing-section"
    elif bad_address == "wrong-author":
        issue["author"] = "assignments"
    else:
        issue["author"] = "orchestrator"
    response["issues"] = [issue]
    llm = FakeLLM(response)
    with pytest.raises(AgentResponseError):
        asyncio.run(ReviewerAgent(llm).review(context, theory, assignments))
    assert len(llm.calls) == 1


@pytest.mark.parametrize("role", ("theory", "assignments"))
@pytest.mark.parametrize("missing", ("previous", "feedback"))
def test_revision_requires_previous_and_feedback_together_before_provider_call(
    role: str,
    missing: str,
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
    review: ReviewResult,
) -> None:
    llm = FakeLLM()
    previous = theory if role == "theory" else assignments
    kwargs = {"previous": previous, "feedback": review}
    del kwargs[missing]
    with pytest.raises(ValueError, match="supplied together"):
        if role == "theory":
            asyncio.run(TheoryAgent(llm).generate(context, **kwargs))
        else:
            asyncio.run(AssignmentsAgent(llm).generate(context, theory, **kwargs))
    assert llm.calls == []


@pytest.mark.parametrize("role", ("theory", "assignments"))
def test_revision_routes_only_findings_for_the_requested_author(
    role: str,
    demo: dict[str, Any],
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
    review: ReviewResult,
) -> None:
    feedback = review_with_issues(review, theory, assignments)
    previous = theory if role == "theory" else assignments
    llm = FakeLLM(response_for(role, demo))
    if role == "theory":
        asyncio.run(TheoryAgent(llm).generate(context, previous=theory, feedback=feedback))
    else:
        asyncio.run(
            AssignmentsAgent(llm).generate(context, theory, previous=assignments, feedback=feedback)
        )
    payload = json.loads(llm.calls[0]["user_prompt"])
    assert payload["previous"] == previous.model_dump(mode="json")
    assert payload["feedback"] == [
        item.model_dump(mode="json") for item in feedback.for_author(role)
    ]
    assert {item["author"] for item in payload["feedback"]} == {role}
    assert len(llm.calls) == 1


@pytest.mark.parametrize("role", ("theory", "assignments"))
@pytest.mark.parametrize("bad_feedback", ("no-own-issues", "unknown-target", "wrong-author"))
def test_revision_refuses_feedback_that_does_not_address_its_existing_content(
    role: str,
    bad_feedback: str,
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
    review: ReviewResult,
) -> None:
    target = (
        theory.sections[0].section_id
        if role == "theory"
        else assignments.lesson_assignments[0].assignment_id
    )
    other_role = "assignments" if role == "theory" else "theory"
    if bad_feedback == "no-own-issues":
        issues = ()
    elif bad_feedback == "unknown-target":
        issues = (issue_for(role, "not-a-current-target"),)
    else:
        issues = (issue_for(other_role, target),)
    feedback = review.model_copy(update={"issues": issues})
    llm = FakeLLM()
    with pytest.raises(ValueError, match="existing content"):
        if role == "theory":
            asyncio.run(TheoryAgent(llm).generate(context, previous=theory, feedback=feedback))
        else:
            asyncio.run(
                AssignmentsAgent(llm).generate(
                    context, theory, previous=assignments, feedback=feedback
                )
            )
    assert llm.calls == []


@pytest.mark.parametrize("role", ("theory", "assignments"))
@pytest.mark.parametrize("change", ("content", "brief", "material", "profile", "digest"))
def test_revision_rejects_review_for_stale_content_or_context(
    role: str,
    change: str,
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
    review: ReviewResult,
) -> None:
    feedback = review_with_issues(review, theory, assignments)
    previous: Theory | AssignmentSet = theory if role == "theory" else assignments
    if change == "content":
        payload = previous.model_dump(mode="json")
        if role == "theory":
            payload["sections"][0]["explanation"]["text"] += " Новый текст."
        else:
            payload["lesson_assignments"][0]["answer"]["text"] += " Новый ответ."
        previous = type(previous).model_validate(payload)
    elif change == "brief":
        context = context.model_copy(
            update={"brief": context.brief.model_copy(update={"teacher_notes": "Новые пожелания"})}
        )
    elif change == "material":
        context = context.model_copy(
            update={
                "materials": (
                    context.materials[0].model_copy(update={"content": "Новый источник"}),
                )
            }
        )
    elif change == "profile":
        context = context.model_copy(
            update={
                "students": (
                    context.students[0].model_copy(update={"common_errors": ("Новая ошибка",)}),
                    *context.students[1:],
                )
            }
        )
    else:
        digest_field = "theory_digest" if role == "theory" else "assignments_digest"
        feedback = feedback.model_copy(update={digest_field: "0" * 64})
    llm = FakeLLM()
    with pytest.raises(ValueError, match="stale"):
        if role == "theory":
            asyncio.run(TheoryAgent(llm).generate(context, previous=previous, feedback=feedback))
        else:
            asyncio.run(
                AssignmentsAgent(llm).generate(
                    context, theory, previous=previous, feedback=feedback
                )
            )
    assert llm.calls == []


@pytest.mark.parametrize("role", ("theory", "assignments"))
@pytest.mark.parametrize("change", ("previous-version", "feedback-version", "feedback-preparation"))
def test_revision_rejects_mismatched_identity_before_provider_call(
    role: str,
    change: str,
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
    review: ReviewResult,
) -> None:
    previous = theory if role == "theory" else assignments
    feedback = review_with_issues(review, theory, assignments)
    if change == "previous-version":
        previous = previous.model_copy(update={"version": context.brief.version + 1})
    elif change == "feedback-version":
        feedback = feedback.model_copy(update={"version": context.brief.version + 1})
    else:
        feedback = feedback.model_copy(update={"preparation_id": "other-preparation"})
    llm = FakeLLM()
    with pytest.raises(ValueError, match="match the current brief"):
        if role == "theory":
            asyncio.run(TheoryAgent(llm).generate(context, previous=previous, feedback=feedback))
        else:
            asyncio.run(
                AssignmentsAgent(llm).generate(
                    context, theory, previous=previous, feedback=feedback
                )
            )
    assert llm.calls == []


@pytest.mark.parametrize("role", ("theory", "assignments"))
def test_rejected_local_generation_can_be_repaired_then_reviewed(
    role: str,
    demo: dict[str, Any],
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    invalid = response_for(role, demo)
    if role == "theory":
        invalid["sections"][0]["source_ids"] = ["invented-source"]
        category = "source"
    else:
        invalid["lesson_assignments"].pop()
        category = "coverage"
    llm = FakeLLM(invalid, response_for(role, demo), demo["review"])

    async def scenario() -> LessonPackage:
        nonlocal theory, assignments
        with pytest.raises(ContentValidationError) as caught:
            await invoke(role, llm, context, theory, assignments)
        error = caught.value
        assert len(llm.calls) == 1
        assert error.content.model_dump(mode="json") == invalid
        assert error.feedback.author == role
        assert error.feedback.issues == error.issues
        assert any(issue.category == category for issue in error.issues)
        assert error.feedback.content_digest == content_digest(context, error.content)
        if role == "theory":
            theory = await TheoryAgent(llm).generate(
                context, previous=error.content, feedback=error.feedback
            )
        else:
            assignments = await AssignmentsAgent(llm).generate(
                context, theory, previous=error.content, feedback=error.feedback
            )
        review = await ReviewerAgent(llm).review(context, theory, assignments)
        return LessonPackage(context=context, theory=theory, assignments=assignments, review=review)

    package = asyncio.run(scenario())
    assert package.review.approved
    assert len(llm.calls) == 3
    repaired_input = json.loads(llm.calls[1]["user_prompt"])
    assert repaired_input["previous"] == invalid
    assert repaired_input["feedback"]
    assert {item["author"] for item in repaired_input["feedback"]} == {role}


@pytest.mark.parametrize("role", ("theory", "assignments"))
@pytest.mark.parametrize("mistake", ("wrong-author", "stale-digest", "unknown-target"))
def test_local_repair_feedback_has_author_digest_and_target_guards(
    role: str,
    mistake: str,
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    previous = theory if role == "theory" else assignments
    target = (
        theory.sections[0].section_id
        if role == "theory"
        else assignments.lesson_assignments[0].assignment_id
    )
    author = role
    digest = content_digest(context, previous)
    expected_message = "existing content"
    if mistake == "wrong-author":
        author = "assignments" if role == "theory" else "theory"
        expected_message = "address this author"
    elif mistake == "stale-digest":
        digest = "0" * 64
        expected_message = "stale"
    else:
        target = "not-a-current-target"
    feedback = RepairFeedback.model_validate(
        {
            "preparation_id": context.brief.preparation_id,
            "version": context.brief.version,
            "author": author,
            "content_digest": digest,
            "issues": [issue_for(author, target).model_dump(mode="json")],
        }
    )
    llm = FakeLLM()
    with pytest.raises(ValueError, match=expected_message):
        if role == "theory":
            asyncio.run(TheoryAgent(llm).generate(context, previous=previous, feedback=feedback))
        else:
            asyncio.run(
                AssignmentsAgent(llm).generate(
                    context, theory, previous=previous, feedback=feedback
                )
            )
    assert llm.calls == []


def test_more_than_100_local_findings_survive_as_actionable_repair_feedback(
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    context, invalid = large_invalid_assignment_set(context, assignments)
    expected = check_assignments(context, invalid)
    assert len(expected) > 100
    corrected_payload = invalid.model_dump(mode="json")
    all_items = corrected_payload["lesson_assignments"] + [
        item for homework in corrected_payload["homeworks"] for item in homework["assignments"]
    ]
    for item in all_items:
        item["topic"] = context.brief.topics[0]
        item["source_ids"] = [context.materials[0].material_id]
    llm = FakeLLM(invalid.model_dump(mode="json"), corrected_payload)

    async def scenario() -> AssignmentSet:
        with pytest.raises(ContentValidationError) as caught:
            await AssignmentsAgent(llm).generate(context, theory)
        error = caught.value
        assert error.content == invalid
        assert error.issues == error.feedback.issues == expected
        assert len(llm.calls) == 1
        return await AssignmentsAgent(llm).generate(
            context, theory, previous=error.content, feedback=error.feedback
        )

    corrected = asyncio.run(scenario())
    assert check_assignments(context, corrected) == ()
    assert len(llm.calls) == 2
    revision_input = json.loads(llm.calls[1]["user_prompt"])
    assert len(revision_input["feedback"]) == len(expected)


def test_reviewer_merges_large_local_and_model_findings_without_losing_evidence(
    demo: dict[str, Any],
    context: GenerationContext,
    theory: Theory,
    assignments: AssignmentSet,
) -> None:
    context, invalid_assignments = large_invalid_assignment_set(context, assignments)
    theory_payload = theory.model_dump(mode="json")
    section = theory_payload["sections"][0]
    section.update({"topic": "other-topic", "source_ids": ["missing"]})
    theory_payload["sections"] = []
    for index in range(32):
        item = copy.deepcopy(section)
        item["section_id"] = f"large-theory-{index}"
        theory_payload["sections"].append(item)
    invalid_theory = Theory.model_validate(theory_payload)
    local_issues = check_theory(context, invalid_theory) + check_assignments(
        context, invalid_assignments
    )
    report = copy.deepcopy(demo["review"])
    model_issues = tuple(
        issue_for(
            "assignments", invalid_assignments.lesson_assignments[0].assignment_id
        ).model_copy(update={"message": f"Отдельное замечание {index}"})
        for index in range(100)
    )
    report["issues"] = [issue.model_dump(mode="json") for issue in model_issues]
    llm = FakeLLM(report)
    result = asyncio.run(ReviewerAgent(llm).review(context, invalid_theory, invalid_assignments))
    assert len(local_issues) > 100
    assert len(result.issues) > 200
    assert result.issues == local_issues + model_issues
    assert not result.approved
    assert len(llm.calls) == 1


def test_recorded_semantic_finding_routes_correction_and_requires_a_fresh_review(
    demo: dict[str, Any],
    context: GenerationContext,
) -> None:
    """Exercise an orchestrator handoff, not an actual model's physics judgement."""
    incorrect = copy.deepcopy(demo["assignments"])
    incorrect["lesson_assignments"][0]["answer"]["text"] = "11 м/с"
    finding = issue_for("assignments", incorrect["lesson_assignments"][0]["assignment_id"])
    rejected_report = copy.deepcopy(demo["review"])
    rejected_report["issues"] = [finding.model_dump(mode="json")]
    llm = FakeLLM(demo["theory"], incorrect, rejected_report, demo["assignments"], demo["review"])

    async def scenario() -> LessonPackage:
        theory = await TheoryAgent(llm).generate(context)
        assignments = await AssignmentsAgent(llm).generate(context, theory)
        # Structural checks deliberately make no claim that 11 м/с is physically correct.
        assert check_assignments(context, assignments) == ()
        rejected = await ReviewerAgent(llm).review(context, theory, assignments)
        assert not rejected.approved
        with pytest.raises(ValidationError, match="blocking review issues"):
            LessonPackage(context=context, theory=theory, assignments=assignments, review=rejected)

        fixed = await AssignmentsAgent(llm).generate(
            context, theory, previous=assignments, feedback=rejected
        )
        with pytest.raises(ValidationError, match="stale"):
            LessonPackage(context=context, theory=theory, assignments=fixed, review=rejected)
        approved = await ReviewerAgent(llm).review(context, theory, fixed)
        return LessonPackage(context=context, theory=theory, assignments=fixed, review=approved)

    package = asyncio.run(scenario())

    assert package.review.approved
    assert package.assignments.lesson_assignments[0].answer.text == "10 м/с"
    revision_input = json.loads(llm.calls[3]["user_prompt"])
    assert revision_input["previous"] == incorrect
    assert revision_input["feedback"] == [finding.model_dump(mode="json")]
    final_review_input = json.loads(llm.calls[4]["user_prompt"])
    assert final_review_input["assignments"] == package.assignments.model_dump(mode="json")
    assert len(llm.calls) == 5
    assert not llm.responses
