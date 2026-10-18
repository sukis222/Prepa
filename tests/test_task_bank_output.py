"""Plain-text output, the Material adapter and the console entry point."""

import json
from collections.abc import Iterable
from typing import Any

import pytest

from prepa.schemas import GenerationContext
from prepa.task_bank import AnswerKind, BankTask, KesTopic, SearchResult, format_result, to_material
from prepa.task_bank import __main__ as cli
from prepa.task_bank.fipi.client import MAX_PAGE_SIZE, Page
from prepa.task_bank.models import Exam
from prepa.task_bank.text import format_task

TOPIC = KesTopic(code="1.1.5", title="Равномерное прямолинейное движение")
SHORT = BankTask(
    exam="ege",
    task_id="1A2B3C",
    url="https://ege.fipi.ru/bank/questions.php?search=1&qid=1A2B3C",
    kes=(TOPIC,),
    answer_kind=AnswerKind.SHORT,
    statement="Найдите путь за $t_1$.\n[рисунок 1]",
    answer_unit="м",
    images=("https://ege.fipi.ru/docs/a.png",),
)
MATCHING = SHORT.model_copy(
    update={
        "task_id": "7A8B9C",
        "kes": (),
        "answer_kind": AnswerKind.MATCHING,
        "matching_keys": ("А", "Б"),
        "answer_unit": "",
        "images": (),
        "options": (),
    }
)
CHOICE = SHORT.model_copy(
    update={
        "task_id": "4D5E6F",
        "answer_kind": AnswerKind.MULTIPLE_CHOICE,
        "options": ("1) да", "2) нет"),
        "answer_unit": "",
        "images": (),
    }
)


def test_format_task_shows_answer_template_pictures_and_source() -> None:
    assert format_task(SHORT, 2).splitlines() == [
        "Задача 2 · EGE · КЭС 1.1.5 · краткий ответ",
        "Найдите путь за $t_1$.",
        "[рисунок 1]",
        "Ответ: ____ м",
        "[рисунок 1] https://ege.fipi.ru/docs/a.png",
        "Источник: открытый банк ФИПИ, задание 1A2B3C — " + SHORT.url,
    ]
    assert "Ответ: А — Б —" in format_task(MATCHING)
    assert format_task(MATCHING).startswith("Задача · EGE · КЭС — · установление соответствия")
    assert "1) да\n2) нет" in format_task(CHOICE)


def test_format_result_states_counts_and_missing_answers() -> None:
    result = SearchResult(exam="ege", topics=(TOPIC,), total_available=13, tasks=(SHORT, CHOICE))
    text = format_result(result)
    assert text.startswith("EGE: 1.1.5 Равномерное прямолинейное движение\n")
    assert "В банке по теме: 13, показано: 2. Ответы и решения банк не публикует." in text
    assert "Задача 1 ·" in text and "Задача 2 ·" in text


def test_to_material_feeds_the_content_agents_contract(demo: dict[str, Any]) -> None:
    topic = demo["context"]["brief"]["topics"][0]
    exam = demo["context"]["brief"]["exam"]
    material = to_material(SHORT.model_copy(update={"exam": exam}), [topic])
    assert material.material_id == f"fipi-{exam}-1A2B3C"
    assert material.source == SHORT.url
    assert material.topics == (topic,)
    assert "Найдите путь" in material.content
    data = json.loads(json.dumps(demo["context"]))
    data["materials"] = [material.model_dump(mode="json")]
    data["brief"]["topics"] = [topic]
    context = GenerationContext.model_validate(data)
    assert context.materials == (material,)


class FakeClient:
    tasks = (SHORT, CHOICE)

    def __init__(self) -> None:
        self.closed = False

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        self.closed = True

    async def topics(self, exam: Exam) -> tuple[KesTopic, ...]:
        return (KesTopic(code="1.1", title="Кинематика"), TOPIC)

    async def page(
        self,
        exam: Exam,
        codes: Iterable[str],
        *,
        kinds: Iterable[AnswerKind] = (),
        page: int = 0,
        page_size: int = MAX_PAGE_SIZE,
    ) -> Page:
        return Page(total=2, tasks=self.tasks)


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "FipiClient", FakeClient)


@pytest.mark.usefixtures("fake_client")
def test_cli_prints_found_tasks_as_text_or_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--topic", "1.1.5", "--limit", "1", "--kind", "short"]) == 0
    out = capsys.readouterr().out
    assert "Задача 1 · EGE · КЭС 1.1.5" in out and "4D5E6F" not in out

    assert cli.main(["--exam", "ege", "--topic", "равномерное движение", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [task["task_id"] for task in data["tasks"]] == ["1A2B3C", "4D5E6F"]


@pytest.mark.usefixtures("fake_client")
def test_cli_lists_topics_and_reports_unknown_ones(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--list-topics"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "1.1 Кинематика",
        "1.1.5 Равномерное прямолинейное движение",
    ]
    assert cli.main(["--list-topics", "кинематика"]) == 0
    assert capsys.readouterr().out.strip() == "1.1 Кинематика"

    assert cli.main(["--topic", "оптика"]) == 1
    assert "Ошибка:" in capsys.readouterr().err


def test_cli_requires_a_topic_or_topic_listing() -> None:
    with pytest.raises(SystemExit) as error:
        cli.main([])
    assert error.value.code == 2
