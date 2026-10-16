"""Replay the public API offline; this is not evidence of live model quality.

Run from the repository after installing it:
    python examples/content_agents.py --output-dir output/content-demo
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from prepa.agents.assignments import AssignmentsAgent
from prepa.agents.reviewer import ReviewerAgent
from prepa.agents.theory import TheoryAgent
from prepa.schemas import GenerationContext, LessonPackage


class ReplayLLM:
    """Explicitly scripted answers from a hand-authored fixture, without a model."""

    def __init__(self, demo: dict[str, Any]) -> None:
        self.demo = demo

    async def generate(
        self, *, system_prompt: str, user_prompt: str, response_schema: dict[str, Any]
    ) -> dict[str, Any]:
        role = {"Theory": "theory", "AssignmentSet": "assignments", "ReviewReport": "review"}[
            response_schema["title"]
        ]
        return dict(self.demo[role])


async def replay(demo: dict[str, Any]) -> LessonPackage:
    context = GenerationContext.model_validate(demo["context"])
    llm = ReplayLLM(demo)
    theory = await TheoryAgent(llm).generate(context)
    assignments = await AssignmentsAgent(llm).generate(context, theory)
    review = await ReviewerAgent(llm).review(context, theory, assignments)
    return LessonPackage(context=context, theory=theory, assignments=assignments, review=review)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("output/content-demo"))
    args = parser.parse_args()
    fixture = Path(__file__).resolve().parents[1] / "data/demo/content_agents.json"
    demo = json.loads(fixture.read_text(encoding="utf-8"))
    package = asyncio.run(replay(demo))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "teacher.json").write_text(
        package.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    for student_id in package.context.brief.student_ids:
        (args.output_dir / f"{student_id}.json").write_text(
            package.for_student(student_id).model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    print(f"Offline replay: approved={package.review.approved}; output={args.output_dir}")
    print("Scripted fixture only: no LLM, Telegram, database or PDF compilation was used.")


if __name__ == "__main__":
    main()
