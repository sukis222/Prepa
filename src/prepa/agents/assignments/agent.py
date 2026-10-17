"""Shared lesson practice and individually motivated homework."""

from prepa.agents.runtime import (
    AgentResponseError,
    ContentValidationError,
    StructuredAgent,
    revision_payload,
)
from prepa.schemas import AssignmentSet, GenerationContext, RepairFeedback, ReviewResult, Theory
from prepa.schemas.validation import check_assignments, check_theory


class AssignmentsAgent(StructuredAgent):
    async def generate(
        self,
        context: GenerationContext,
        theory: Theory,
        *,
        previous: AssignmentSet | None = None,
        feedback: ReviewResult | RepairFeedback | None = None,
    ) -> AssignmentSet:
        revision = revision_payload(
            context,
            "assignments",
            previous,
            feedback,
            {a.assignment_id for a in previous.all_assignments()} if previous else set(),
        )
        theory_issues = check_theory(context, theory)
        if theory_issues:
            raise ContentValidationError(context, theory, theory_issues)
        assignments = await self.request(
            "assignments",
            {
                "context": context.model_dump(mode="json"),
                "theory": theory.model_dump(mode="json"),
                **revision,
            },
            AssignmentSet,
        )
        try:
            issues = check_assignments(context, assignments)
        except ValueError:
            raise AgentResponseError(
                "assignments returned mismatched preparation_id or version"
            ) from None
        if issues:
            raise ContentValidationError(context, assignments, issues)
        return assignments
