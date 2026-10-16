"""Hand-authored, synthetic physics inputs; no network calls or real pupils."""

import json
from pathlib import Path
from typing import Any

import pytest

from prepa.schemas import (
    AssignmentSet,
    GenerationContext,
    LessonPackage,
    ReviewResult,
    Theory,
)
from prepa.schemas.validation import content_digest


@pytest.fixture
def demo() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data/demo/content_agents.json"
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


@pytest.fixture
def context(demo: dict[str, Any]) -> GenerationContext:
    return GenerationContext.model_validate(demo["context"])


@pytest.fixture
def theory(demo: dict[str, Any]) -> Theory:
    return Theory.model_validate(demo["theory"])


@pytest.fixture
def assignments(demo: dict[str, Any]) -> AssignmentSet:
    return AssignmentSet.model_validate(demo["assignments"])


@pytest.fixture
def review(
    demo: dict[str, Any], context: GenerationContext, theory: Theory, assignments: AssignmentSet
) -> ReviewResult:
    return ReviewResult(
        **demo["review"],
        theory_digest=content_digest(context, theory),
        assignments_digest=content_digest(context, assignments),
    )


@pytest.fixture
def package(
    context: GenerationContext, theory: Theory, assignments: AssignmentSet, review: ReviewResult
) -> LessonPackage:
    return LessonPackage(context=context, theory=theory, assignments=assignments, review=review)
