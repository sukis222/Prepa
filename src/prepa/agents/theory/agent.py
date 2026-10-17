"""Theory author. Search and teacher confirmation are provided by the orchestrator."""

from prepa.agents.runtime import (
    AgentResponseError,
    ContentValidationError,
    StructuredAgent,
    revision_payload,
)
from prepa.schemas import GenerationContext, RepairFeedback, ReviewResult, Theory
from prepa.schemas.validation import check_theory


class TheoryAgent(StructuredAgent):
    async def generate(
        self,
        context: GenerationContext,
        *,
        previous: Theory | None = None,
        feedback: ReviewResult | RepairFeedback | None = None,
    ) -> Theory:
        revision = revision_payload(
            context,
            "theory",
            previous,
            feedback,
            {s.section_id for s in previous.sections} if previous else set(),
        )
        theory = await self.request(
            "theory", {"context": context.model_dump(mode="json"), **revision}, Theory
        )
        try:
            issues = check_theory(context, theory)
        except ValueError:
            raise AgentResponseError(
                "theory returned mismatched preparation_id or version"
            ) from None
        if issues:
            raise ContentValidationError(context, theory, issues)
        return theory
