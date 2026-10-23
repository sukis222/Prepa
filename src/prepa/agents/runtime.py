"""Shared structured-call mechanics, without provider calls or orchestration state."""

import asyncio
import json
import math
from importlib.resources import files
from typing import Any, cast

from pydantic import BaseModel, TypeAdapter, ValidationError

from prepa.schemas import (
    AssignmentSet,
    GenerationContext,
    GenerationFailure,
    RepairFeedback,
    ReviewIssue,
    ReviewResult,
    Theory,
)
from prepa.schemas.content import Author, Versioned
from prepa.schemas.validation import content_digest, ensure_identity

from .contracts import StructuredLLM


class AgentResponseError(ValueError):
    """The provider returned invalid JSON, schema or review addressing."""


class InsufficientMaterialsError(ValueError):
    """No successful content was produced. The caller may fetch a better source set."""

    def __init__(self, failure: GenerationFailure) -> None:
        self.failure = failure
        super().__init__("Supplied materials are insufficient; no content was approved")


class ContentValidationError(ValueError):
    """Generated content failed deterministic checks; issues are safe to route."""

    def __init__(
        self,
        context: GenerationContext,
        content: Theory | AssignmentSet,
        issues: tuple[ReviewIssue, ...],
    ) -> None:
        self.issues = issues
        self.content = content
        self.feedback = RepairFeedback(
            preparation_id=content.preparation_id,
            version=content.version,
            author="theory" if isinstance(content, Theory) else "assignments",
            content_digest=content_digest(context, content),
            issues=issues,
        )
        super().__init__(f"Generated content has {len(issues)} contract issue(s)")


def require_confirmed(context: GenerationContext) -> None:
    if not context.brief.confirmed:
        raise ValueError("teacher confirmation is required before any model call")


def revision_payload(
    context: GenerationContext,
    author: Author,
    previous: Versioned | None,
    feedback: ReviewResult | RepairFeedback | None,
    targets: set[str],
) -> dict[str, Any]:
    require_confirmed(context)
    if previous is None and feedback is None:
        return {}
    if previous is None or feedback is None:
        raise ValueError("previous content and feedback must be supplied together")
    ensure_identity(context, previous)
    ensure_identity(context, feedback)
    if isinstance(feedback, RepairFeedback):
        if feedback.author != author:
            raise ValueError("repair feedback must address this author")
        expected_digest = feedback.content_digest
        issues = feedback.issues
    else:
        expected_digest = (
            feedback.theory_digest if author == "theory" else feedback.assignments_digest
        )
        issues = feedback.for_author(author)
    if expected_digest != content_digest(context, previous):
        raise ValueError("feedback is stale: previous content or context has changed")
    if not issues or any(issue.target_id not in targets for issue in issues):
        raise ValueError("feedback must address existing content by this author")
    return {
        "previous": previous.model_dump(mode="json"),
        "feedback": [issue.model_dump(mode="json") for issue in issues],
    }


class StructuredAgent:
    def __init__(
        self,
        llm: StructuredLLM,
        *,
        timeout_seconds: float = 120,
        max_response_chars: int = 200_000,
    ) -> None:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        self.llm = llm
        self.timeout_seconds = timeout_seconds
        if type(max_response_chars) is not int or max_response_chars < 1:
            raise ValueError("max_response_chars must be a positive integer")
        self.max_response_chars = max_response_chars

    async def request[Result: BaseModel](
        self, role: str, payload: dict[str, Any], response_model: type[Result]
    ) -> Result:
        prompt = files(f"prepa.agents.{role}").joinpath("prompt.md").read_text(encoding="utf-8")
        # The response class is selected at runtime; validation restores the generic result type.
        adapter = TypeAdapter[Result | GenerationFailure](
            cast(Any, response_model | GenerationFailure)
        )
        schema = adapter.json_schema()
        schema["title"] = response_model.__name__
        response = await asyncio.wait_for(
            self.llm.generate(
                system_prompt=prompt,
                user_prompt=json.dumps(payload, ensure_ascii=False),
                response_schema=schema,
            ),
            timeout=self.timeout_seconds,
        )
        try:
            if isinstance(response, dict):
                response = json.dumps(response, ensure_ascii=False, allow_nan=False)
            if isinstance(response, str):
                if len(response) > self.max_response_chars:
                    raise AgentResponseError(f"{role} response exceeds max_response_chars")
                result = adapter.validate_json(response)
                if isinstance(result, GenerationFailure):
                    if not set(result.missing_topics) <= set(payload["context"]["brief"]["topics"]):
                        raise AgentResponseError(f"{role} refusal names unconfirmed topics")
                    raise InsufficientMaterialsError(result)
                return result
        except (ValidationError, TypeError, ValueError, RecursionError) as error:
            if isinstance(error, (AgentResponseError, InsufficientMaterialsError)):
                raise
            # Do not expose raw provider output, student context or input values in errors.
            raise AgentResponseError(f"{role} returned JSON that violates the schema") from None
        raise AgentResponseError(f"{role} must return a JSON object or JSON string")
