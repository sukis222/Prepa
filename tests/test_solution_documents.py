"""Teacher-only source explanations never enter the student worksheet."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from prepa.documents.delivery import Attachment
from prepa.documents.latex import DocumentError
from prepa.documents.solutions import solution_document
from prepa.documents.source import SourceDocuments, source_worksheet_tex
from prepa.schemas import SourceSolution, SourceTask, TaskWorksheet
from prepa.schemas.source import source_task_digest


def worksheet(solution=True):
    text = "Впишите правильный ответ. Тело движется."
    task = SourceTask(
        id="one",
        statement_exact=text,
        sha256=source_task_digest(text),
        source_url="https://reshai.online/ege/subjects/physics/tasks/ABC123",
        solution=SourceSolution(
            text="SECRET SOLUTION $v=2$",
            source_url="https://reshai.online/solution",
            sha256=source_task_digest("SECRET SOLUTION $v=2$"),
        )
        if solution
        else None,
    )
    return TaskWorksheet(
        preparation_id="test",
        version=1,
        student_ids=("one",),
        exam="ege",
        topics=("Движение",),
        title="Движение",
        tasks=(task,),
    )


def test_source_solution_digest_and_roundtrip():
    sheet = worksheet()
    assert TaskWorksheet.model_validate_json(sheet.model_dump_json()) == sheet
    with pytest.raises(ValueError, match="digest"):
        SourceSolution(text="tamper", source_url="test", sha256="0" * 64)
    assert "SECRET" not in source_worksheet_tex(sheet, ((),), "DejaVu Serif")


def test_solution_pdf_optional_and_teacher_content(monkeypatch):
    compile = AsyncMock(return_value=Attachment("solutions.pdf", b"%PDF-test"))
    monkeypatch.setattr("prepa.documents.solutions._SourceCompiler._compile", compile)
    docs = SourceDocuments()
    assert asyncio.run(solution_document(docs, worksheet(False))) is None
    compile.assert_not_awaited()
    result = asyncio.run(solution_document(docs, worksheet()))
    assert result and result.name == "solutions.pdf"
    source = compile.call_args.args[0]
    assert "SECRET SOLUTION" in source and "Впишите" not in source
    assert r"\setmainfont{DejaVu Serif}" in source
    assert "Arial" not in source and "DejaVu Sans" not in source
    assert compile.call_args.args[-1] == "solutions"


def test_solution_renderer_failure(monkeypatch):
    compile = AsyncMock(side_effect=DocumentError("failed"))
    monkeypatch.setattr("prepa.documents.solutions._SourceCompiler._compile", compile)
    with pytest.raises(DocumentError):
        asyncio.run(solution_document(SourceDocuments(), worksheet()))
