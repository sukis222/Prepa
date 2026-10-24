"""Synthetic transcripts only; autonomous tests do not evaluate real model quality."""

import asyncio
import json
from typing import Any

import pytest
from pydantic import ValidationError

from prepa.agents.runtime import AgentResponseError
from prepa.agents.summarizer import LessonSummarizerAgent
from prepa.schemas.lesson_summary import LessonSummary, LessonSummaryInput


class FakeLLM:
    def __init__(self, response: Any = None) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def generate(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response


def context() -> LessonSummaryInput:
    return LessonSummaryInput.model_validate(
        {
            "preparation_id": "lesson",
            "version": 1,
            "student_id": "anonymous",
            "tasks": [{"task_id": "task1", "statement": "Найти работу газа."}],
            "transcript": [
                {"turn_id": "t1", "speaker": "student", "text": "Я перепутал работу и теплоту."},
                {
                    "turn_id": "t2",
                    "speaker": "teacher",
                    "text": "Работа равна площади под графиком.",
                },
                {
                    "turn_id": "t3",
                    "speaker": "student",
                    "text": "При постоянном объеме работа ноль.",
                },
            ],
        }
    )


def response() -> dict:
    return {
        "preparation_id": "lesson",
        "version": 1,
        "student_id": "anonymous",
        "input_digest": context().digest(),
        "overview": "Обсудили работу газа.",
        "observations": [
            {
                "topic": "Работа газа",
                "status": "difficulty",
                "finding": "Путает работу и теплоту.",
                "task_ids": ["task1"],
                "evidence": [{"turn_id": "t1", "quote": "перепутал работу и теплоту"}],
            }
        ],
        "next_steps": [
            {
                "topic": "Работа газа",
                "action": "Повторить различие величин.",
                "basis_turn_ids": ["t1"],
            }
        ],
        "insufficient_evidence": False,
        "uncertainty": [],
        "requires_teacher_confirmation": True,
    }


def test_summary_round_trip_and_prompt() -> None:
    llm = FakeLLM(response())
    result = asyncio.run(LessonSummarizerAgent(llm).summarize(context()))
    assert LessonSummary.model_validate_json(result.model_dump_json()) == result
    assert result.requires_teacher_confirmation
    payload = json.loads(llm.calls[0]["user_prompt"])
    assert payload["input_digest"] == context().digest()
    assert "не выдумывай" in llm.calls[0]["system_prompt"]
    with pytest.raises(ValidationError):
        result.version = 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("preparation_id", "other"),
        ("version", 2),
        ("student_id", "other"),
        ("input_digest", "0" * 64),
        ("requires_teacher_confirmation", False),
    ],
)
def test_reject_wrong_identity_and_confirmation(field: str, value: object) -> None:
    data = response()
    data[field] = value
    with pytest.raises(AgentResponseError):
        asyncio.run(LessonSummarizerAgent(FakeLLM(data)).summarize(context()))


@pytest.mark.parametrize("mutation", ["quote", "turn", "task", "teacher", "step", "empty"])
def test_reject_ungrounded_response(mutation: str) -> None:
    data = response()
    observation = data["observations"][0]
    if mutation == "quote":
        observation["evidence"][0]["quote"] = "выдуманная цитата"
    elif mutation == "turn":
        observation["evidence"][0]["turn_id"] = "missing"
    elif mutation == "task":
        observation["task_ids"] = ["missing"]
    elif mutation == "teacher":
        observation["status"] = "understood"
        observation["evidence"] = [{"turn_id": "t2", "quote": "Работа равна площади"}]
    elif mutation == "step":
        data["next_steps"][0]["basis_turn_ids"] = ["missing"]
    else:
        data["observations"] = []
    with pytest.raises(AgentResponseError):
        asyncio.run(LessonSummarizerAgent(FakeLLM(data)).summarize(context()))


def test_insufficient_transcript_does_not_invent_progress() -> None:
    data = response()
    data.update(
        observations=[],
        next_steps=[],
        insufficient_evidence=True,
        uncertainty=["Нет самостоятельного объяснения ученика."],
    )
    result = asyncio.run(LessonSummarizerAgent(FakeLLM(json.dumps(data))).summarize(context()))
    assert not result.observations


@pytest.mark.parametrize("data", ["not json", [], {"unexpected": 1}])
def test_invalid_output(data: object) -> None:
    with pytest.raises(AgentResponseError):
        asyncio.run(LessonSummarizerAgent(FakeLLM(data)).summarize(context()))


def test_limits_and_uniqueness() -> None:
    data = context().model_dump(mode="json")
    data["transcript"].append(data["transcript"][0])
    with pytest.raises(ValidationError):
        LessonSummaryInput.model_validate(data)
    data = context().model_dump(mode="json")
    data["transcript"] = [
        {"turn_id": f"t{i}", "speaker": "unknown", "text": "x" * 6000} for i in range(17)
    ]
    with pytest.raises(ValidationError):
        LessonSummaryInput.model_validate(data)


def test_max_response_and_timeout() -> None:
    with pytest.raises(AgentResponseError):
        asyncio.run(
            LessonSummarizerAgent(FakeLLM(response()), max_response_chars=1).summarize(context())
        )

    class SlowLLM(FakeLLM):
        async def generate(self, **kwargs: object) -> str:
            await asyncio.sleep(1)
            return "{}"

    with pytest.raises(TimeoutError):
        asyncio.run(LessonSummarizerAgent(SlowLLM(), timeout_seconds=0.001).summarize(context()))


@pytest.mark.parametrize("status", ["understood", "difficulty", "unclear"])
def test_unknown_speaker_cannot_be_attributed(status: str) -> None:
    data = context().model_dump(mode="json")
    for turn in data["transcript"]:
        turn["speaker"] = "unknown"
    unknown = LessonSummaryInput.model_validate(data)
    output = response()
    output["input_digest"] = unknown.digest()
    output["observations"][0]["status"] = status
    with pytest.raises(AgentResponseError):
        asyncio.run(LessonSummarizerAgent(FakeLLM(output)).summarize(unknown))
    output["insufficient_evidence"] = True
    if status == "unclear":
        result = asyncio.run(LessonSummarizerAgent(FakeLLM(output)).summarize(unknown))
        assert result.insufficient_evidence
    else:
        with pytest.raises(AgentResponseError):
            asyncio.run(LessonSummarizerAgent(FakeLLM(output)).summarize(unknown))


def test_oversize_task_statements() -> None:
    data = context().model_dump(mode="json")
    data["tasks"] = [{"task_id": f"t{i}", "statement": "x" * 20000} for i in range(6)]
    with pytest.raises(ValidationError):
        LessonSummaryInput.model_validate(data)
