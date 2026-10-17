"""Combine code-enforced checks with independent semantic model review."""

from prepa.agents.runtime import AgentResponseError, StructuredAgent, require_confirmed
from prepa.schemas import AssignmentSet, GenerationContext, ReviewReport, ReviewResult, Theory
from prepa.schemas.validation import check_assignments, check_review, check_theory, content_digest


class ReviewerAgent(StructuredAgent):
    async def review(
        self, context: GenerationContext, theory: Theory, assignments: AssignmentSet
    ) -> ReviewResult:
        require_confirmed(context)
        local_issues = check_theory(context, theory) + check_assignments(context, assignments)
        result = await self.request(
            "reviewer",
            {
                "context": context.model_dump(mode="json"),
                "theory": theory.model_dump(mode="json"),
                "assignments": assignments.model_dump(mode="json"),
                "contract_issues": [issue.model_dump(mode="json") for issue in local_issues],
            },
            ReviewReport,
        )
        try:
            check_review(context, theory, assignments, result)
        except ValueError:
            raise AgentResponseError(
                "reviewer returned mismatched version or unknown targets"
            ) from None
        # A model cannot waive code-enforced findings by returning an empty issues array.
        issues = tuple(dict.fromkeys(local_issues + result.issues))
        return ReviewResult(
            preparation_id=result.preparation_id,
            version=result.version,
            summary=result.summary,
            issues=issues,
            theory_digest=content_digest(context, theory),
            assignments_digest=content_digest(context, assignments),
        )
