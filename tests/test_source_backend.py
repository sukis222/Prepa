"""Source snapshots, one-call selection, capacity failures and persistent worker boundary."""

import asyncio
import base64
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image
from pydantic import ValidationError

from prepa.documents.delivery import Attachment
from prepa.preparation.jobs import Job
from prepa.preparation.source import (
    SourceCapacityError,
    SourceCorpusError,
    SourceSelectionBackend,
    topic_matches,
)
from prepa.preparation.worker import failure_message, process_one
from prepa.schemas import LessonBrief, SourceImage, SourceTask, TaskWorksheet


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def source_case(tmp_path, context):
    brief = LessonBrief.model_validate(
        {
            **context.brief.model_dump(),
            "homework_task_count": 0,
            "homework_minutes": 0,
            "lesson_task_count": 2,
        }
    )
    tasks = [
        dict(
            id=f"t{i}",
            statement_exact=f"  Исходное условие {chr(0x4E00 + i)} Ω  ",
            statement_math_exact=[r"s=vt"],
            source_url="https://example.test/source.pdf",
            page=3,
            images=[],
            topic=brief.topics[0],
            tags=["motion"],
            exam=brief.exam,
            statement_sha256=hashlib.sha256(
                f"  Исходное условие {chr(0x4E00 + i)} Ω  ".encode()
            ).hexdigest(),
        )
        for i in range(2)
    ]
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(dict(rights="ours", llm_use_permitted=True, tasks=tasks)))
    llm = SimpleNamespace(generate=AsyncMock(return_value={"ids": ["t1", "t0"]}))
    check = AsyncMock()
    backend = SourceSelectionBackend(llm, corpus_path=path, check_model=check)
    return backend, brief, context.students, llm, check, path, tasks


def test_exact_snapshot_roundtrip_one_selector_and_no_profiles(source_case):
    backend, brief, students, llm, check, _, tasks = source_case
    result = run(backend.prepare(1, brief, students))
    assert isinstance(result, TaskWorksheet)
    assert result.tasks[0].statement_exact == tasks[1]["statement_exact"]
    assert result.tasks[0].statement_math_exact == tuple(tasks[1]["statement_math_exact"])
    assert TaskWorksheet.model_validate_json(result.model_dump_json()) == result
    assert result.student_ids == brief.student_ids
    check.assert_awaited_once()
    llm.generate.assert_awaited_once()
    prompt = json.loads(llm.generate.call_args.kwargs["user_prompt"])
    assert set(prompt) == {"exam", "topics", "teacher_notes", "count", "tasks"}
    assert all("source_url" not in t and "answer" not in t for t in prompt["tasks"])
    assert "students" not in prompt and "student_ids" not in prompt
    with pytest.raises(ValidationError):
        result.tasks[0].statement_exact = "changed"
    with pytest.raises(ValidationError, match="digest"):
        SourceTask.model_validate(
            {**result.tasks[0].model_dump(), "statement_math_exact": ["v=s/t"]}
        )


def test_capacity_no_model_for_15_and_safe_message(source_case):
    backend, brief, students, llm, check, *_ = source_case
    brief = LessonBrief.model_validate({**brief.model_dump(), "lesson_task_count": 15})
    with pytest.raises(SourceCapacityError) as error:
        run(backend.prepare(1, brief, students))
    assert (error.value.requested, error.value.available) == (15, 2)
    assert "2" in failure_message(error.value)[1] and "15" in failure_message(error.value)[1]
    llm.generate.assert_not_awaited()
    check.assert_not_awaited()


@pytest.mark.parametrize("change", ["confirmation", "teacher", "profiles", "exam", "homework"])
def test_reject_before_source_and_model(source_case, change):
    backend, brief, students, llm, check, path, _ = source_case
    teacher = 1
    if change == "confirmation":
        brief = LessonBrief.model_validate({**brief.model_dump(), "confirmed": False})
    if change == "teacher":
        teacher = 0
    if change == "profiles":
        students = ()
    if change == "exam":
        students = tuple(
            type(s).model_validate({**s.model_dump(), "exam": "ege"}) for s in students
        )
    if change == "homework":
        brief = LessonBrief.model_validate(
            {**brief.model_dump(), "homework_task_count": 1, "homework_minutes": 5}
        )
    path.unlink()
    with pytest.raises(ValueError):
        run(backend.prepare(teacher, brief, students))
    llm.generate.assert_not_awaited()
    check.assert_not_awaited()


@pytest.mark.parametrize(
    "mode", ["missing", "json", "rights", "llm", "text_digest", "duplicate", "math"]
)
def test_bad_source_never_goes_to_model(source_case, mode):
    backend, brief, students, llm, check, path, _ = source_case
    data = json.loads(path.read_text())
    if mode == "missing":
        path.unlink()
    elif mode == "json":
        path.write_text("{bad")
    else:
        if mode == "rights":
            data.pop("rights")
        if mode == "llm":
            data["llm_use_permitted"] = False
        if mode == "text_digest":
            data["tasks"][0]["statement_exact"] = "changed"
        if mode == "duplicate":
            data["tasks"][1]["id"] = "t0"
        if mode == "math":
            data["tasks"][0]["statement_math_exact"] = [""]
        path.write_text(json.dumps(data))
    with pytest.raises(SourceCorpusError):
        run(backend.prepare(1, brief, students))
    assert failure_message(SourceCorpusError("secret"))[0] == "source_corpus"
    assert "secret" not in failure_message(SourceCorpusError("secret"))[1]
    llm.generate.assert_not_awaited()
    check.assert_not_awaited()


@pytest.mark.parametrize(
    "response",
    [
        {"ids": ["t0", "t0"]},
        {"ids": ["t0", "foreign"]},
        {"ids": ["t0"]},
        {"ids": [{}, "t0"]},
        {"ids": ["t0", "t1"], "conditions": "invented"},
        [],
    ],
)
def test_model_cannot_invent_modify_or_duplicate_conditions(source_case, response):
    backend, brief, students, llm, *_ = source_case
    llm.generate.return_value = response
    with pytest.raises(SourceCorpusError):
        run(backend.prepare(1, brief, students))
    llm.generate.assert_awaited_once()


def test_model_and_timeout_errors_are_not_retried(source_case):
    from prepa.llm import LLMError

    backend, brief, students, llm, *_ = source_case
    llm.generate.side_effect = LLMError("incomplete_response", finish_reason="length")
    with pytest.raises(LLMError):
        run(backend.prepare(1, brief, students))
    llm.generate.assert_awaited_once()


def test_missing_figure_different_exam_or_topic_not_counted(source_case):
    backend, brief, students, llm, check, path, _ = source_case
    data = json.loads(path.read_text())
    data["tasks"][0]["requires_figure"] = True
    data["tasks"][1]["exam"] = "ege"
    path.write_text(json.dumps(data))
    with pytest.raises(SourceCapacityError) as error:
        run(backend.prepare(1, brief, students))
    assert error.value.available == 0
    llm.generate.assert_not_awaited()
    check.assert_not_awaited()
    assert topic_matches("Термодинамика, 2 часть егэ, циклы", "Thermodynamics", ["thermodynamics"])
    assert topic_matches("Циклы идеального газа", "Thermodynamics", ["thermodynamics"])
    assert not topic_matches("циклы электрических машин", "Thermodynamics", ["thermodynamics"])
    assert not topic_matches("оптика", "Thermodynamics", ["thermodynamics"])


def test_source_png_snapshot_and_hash_failures(source_case):
    backend, brief, students, _, _, path, _ = source_case
    data = json.loads(path.read_text())
    picture = path.parent / "graph.png"
    Image.new("RGB", (12, 8), "white").save(picture)
    data["tasks"][0]["images"] = ["graph.png"]
    path.write_text(json.dumps(data))
    result = run(backend.prepare(1, brief, students))
    asset = result.tasks[1].images[0]
    assert (asset.width, asset.height) == (12, 8)
    assert base64.b64decode(asset.data_base64) == picture.read_bytes()
    with pytest.raises(ValidationError):
        SourceImage.model_validate({**asset.model_dump(), "sha256": "0" * 64})
    with pytest.raises(ValidationError):
        SourceImage.model_validate({**asset.model_dump(), "data_base64": "!bad"})
    data["tasks"][0]["images"] = [asset.model_dump()]
    path.write_text(json.dumps(data))
    assert run(backend.prepare(1, brief, students)).tasks[1].images == (asset,)
    data["tasks"][0]["images"] = ["../outside.png"]
    path.write_text(json.dumps(data))
    with pytest.raises(SourceCorpusError):
        run(backend.prepare(1, brief, students))


def test_worker_source_result_saved_then_delivered_without_legacy_projection(source_case):
    backend, brief, students, _, _, _, _ = source_case
    queue = SimpleNamespace(
        claim=AsyncMock(return_value=Job(1, brief, students, "token", "real")),
        finish=AsyncMock(return_value=True),
    )
    docs = SimpleNamespace(
        worksheet=AsyncMock(return_value=Attachment("tasks.pdf", b"%PDF-existing"))
    )
    deliver = AsyncMock()
    assert run(process_one(queue, backend, docs, deliver, None))
    worksheet = queue.finish.call_args.args[1]
    assert isinstance(worksheet, TaskWorksheet)
    assert deliver.call_args.args[1].attachments[0].content == b"%PDF-existing"
    assert docs.worksheet.call_args.args[0] == worksheet
    wrong = TaskWorksheet.model_validate({**worksheet.model_dump(), "version": brief.version + 1})
    backend.prepare = AsyncMock(return_value=wrong)
    run(process_one(queue, backend, docs, deliver, None))
    assert queue.finish.call_args.kwargs["error"] == "preparation_failed"


def test_fifty_source_tasks_select_and_roundtrip_without_truncation(source_case):
    backend, brief, students, llm, _, path, tasks = source_case
    corpus = json.loads(path.read_text())
    corpus["tasks"] = [
        {
            **tasks[0],
            "id": f"t{i}",
            "statement_exact": f"Условие {chr(0x4E00 + i)}",
            "statement_sha256": hashlib.sha256(f"Условие {chr(0x4E00 + i)}".encode()).hexdigest(),
        }
        for i in range(50)
    ]
    path.write_text(json.dumps(corpus))
    ids = [f"t{i}" for i in range(50)]
    llm.generate.return_value = {"ids": ids}
    brief = LessonBrief.model_validate(
        {**brief.model_dump(), "lesson_task_count": 50, "duration_minutes": 180}
    )
    worksheet = run(backend.prepare(1, brief, students))
    assert tuple(t.id for t in worksheet.tasks) == tuple(ids)
    assert TaskWorksheet.model_validate_json(worksheet.model_dump_json()) == worksheet
    with pytest.raises(ValidationError):
        LessonBrief.model_validate({**brief.model_dump(), "lesson_task_count": 51})
    with pytest.raises(ValidationError):
        TaskWorksheet.model_validate(
            {**worksheet.model_dump(), "tasks": [*worksheet.tasks, worksheet.tasks[0]]}
        )


def test_numerical_clones_removed_before_model(source_case):
    backend, brief, students, llm, check, path, tasks = source_case
    corpus = json.loads(path.read_text())
    for i, raw in enumerate(corpus["tasks"]):
        text = f"Тело движется со скоростью {i + 2} м/с. Найдите путь за 5 с."
        raw.update(statement_exact=text, statement_sha256=hashlib.sha256(text.encode()).hexdigest())
    path.write_text(json.dumps(corpus))
    with pytest.raises(SourceCapacityError) as error:
        run(backend.prepare(1, brief, students))
    assert error.value.available == 1
    llm.generate.assert_not_awaited()
