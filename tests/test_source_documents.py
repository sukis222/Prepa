"""Source worksheet trust boundary; synthetic images, never real pupils or paid models."""

import asyncio
import base64
import hashlib
import io
from unittest.mock import AsyncMock

import pytest
from PIL import Image, PngImagePlugin

from prepa.documents.delivery import Attachment
from prepa.documents.latex import DocumentError, escape_text
from prepa.documents.source import (
    SourceDocuments,
    _SourceCompiler,
    clean_png,
    display_statement,
    render_source_text,
    source_worksheet_tex,
)
from prepa.schemas.source import SourceImage, SourceTask, TaskWorksheet, source_task_digest


def run(coro):
    return asyncio.run(coro)


def png_asset(mode="RGB"):
    image = Image.new(mode, (40, 30), "white")
    meta = PngImagePlugin.PngInfo()
    meta.add_text("do-not-forward", "synthetic metadata")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", pnginfo=meta)
    data = buffer.getvalue()
    return SourceImage(
        data_base64=base64.b64encode(data).decode(),
        sha256=hashlib.sha256(data).hexdigest(),
        width=40,
        height=30,
    )


def worksheet(images=(), math=()):
    text = "  Технический тест. Это синтетическая диаграмма, не рисунок ФИПИ.\n100% & x_y.  "
    task = SourceTask(
        id="synthetic-task",
        statement_exact=text,
        statement_math_exact=math,
        source_url="/private/test/prepa-source.pdf#page=2",
        page=2,
        images=images,
        sha256=source_task_digest(text, math),
    )
    return TaskWorksheet(
        preparation_id="synthetic-worksheet",
        version=2,
        student_ids=("synthetic-student",),
        exam="ege",
        topics=("Технический тест",),
        title="Проверка PDF",
        tasks=(task,),
    )


@pytest.mark.parametrize("mode", ["RGB", "L", "RGBA", "P"])
def test_png_verified_and_metadata_removed(mode):
    cleaned = clean_png(png_asset(mode))
    with Image.open(io.BytesIO(cleaned)) as image:
        assert image.size == (40, 30)
        assert image.format == "PNG" and image.info == {}


@pytest.mark.parametrize(
    "mutation,code",
    [
        ({"data_base64": "!"}, "invalid_source_image"),
        ({"sha256": "0" * 64}, "source_image_changed"),
        ({"width": 41}, "invalid_source_image"),
    ],
)
def test_image_tampering_rejected(mutation, code):
    asset = png_asset()
    forged = SourceImage.model_construct(**{**asset.model_dump(), **mutation})
    with pytest.raises(DocumentError, match=code):
        clean_png(forged)


def test_corrupt_png_even_with_valid_digest():
    data = b"not a PNG"
    asset = SourceImage(
        data_base64=base64.b64encode(data).decode(),
        sha256=hashlib.sha256(data).hexdigest(),
        width=1,
        height=1,
    )
    with pytest.raises(DocumentError, match="invalid_source_image"):
        clean_png(asset)


def test_png_pixel_and_byte_limits(monkeypatch):
    asset = png_asset()
    monkeypatch.setattr("prepa.documents.source.MAX_IMAGE_PIXELS", 10)
    with pytest.raises(DocumentError, match="invalid_source_image"):
        clean_png(asset)
    monkeypatch.setattr("prepa.documents.source.MAX_IMAGE_PIXELS", 20_000_000)
    monkeypatch.setattr("prepa.documents.source.MAX_IMAGE_BYTES", 5)
    with pytest.raises(DocumentError, match="invalid_source_image"):
        clean_png(asset)


def test_source_text_and_public_metadata():
    sheet = worksheet()
    source = source_worksheet_tex(sheet, ((),), "DejaVu Serif")
    assert escape_text(sheet.tasks[0].statement_exact.strip()) in source
    assert "100\\% \\& x\\_y" in source
    assert "synthetic-student" not in source
    assert "synthetic-worksheet" not in source
    assert "/private/test" not in source
    assert "Источник:" not in source
    assert "step=5mm" not in source and "70mm" not in source
    assert r"\begin{minipage}" not in source
    assert r"\bfseries 1." in source
    assert r"\setmainfont{DejaVu Sans}" in source
    assert "Ответ" not in source and "Решение" not in source
    assert source.count(r"\begingroup") == source.count(r"\endgroup")


def test_inline_source_math_mixed_text_punctuation_and_snapshot():
    text = r"Скорость $v=\frac{s}{t}$, время $t=2$ с. 100% & x_y."
    rendered = render_source_text(text)
    assert rendered == r"Скорость \(v=\frac{s}{t}\), время \(t=2\) с. 100\% \& x\_y."
    sheet = worksheet()
    task = sheet.tasks[0]
    task = SourceTask.model_validate(
        {**task.model_dump(), "statement_exact": text, "sha256": source_task_digest(text)}
    )
    sheet = TaskWorksheet.model_validate({**sheet.model_dump(), "tasks": [task.model_dump()]})
    source = source_worksheet_tex(sheet, ((),), "Times New Roman")
    assert rendered in source
    assert sheet.tasks[0].statement_exact == text
    assert sheet.tasks[0].sha256 == source_task_digest(text)
    assert r"\[" not in source


@pytest.mark.parametrize("text", ["Цена $5", "$$", "Обычный текст", ""])
def test_unmatched_and_doubled_dollars_are_literal(text):
    assert render_source_text(text) == escape_text(text)


def test_display_math_from_published_solution():
    assert render_source_text(r"$$\mathcal{E}=\frac{Q}{t}$$") == r"\[\mathcal{E}=\frac{Q}{t}\]"
    assert render_source_text(r"$U=2~\text{кВ}$") == r"\(U=2\ \text{кВ}\)"
    assert render_source_text("$ℰ=2$") == r"\(\mathcal{E}=2\)"
    assert render_source_text("Поле ⊗") == r"Поле \(\otimes\)"


@pytest.mark.parametrize("math", [r"\input{secret}", r"^^5cinput{secret}", r"\write18{bad}"])
def test_unsafe_inline_source_math_rejected(math):
    with pytest.raises(DocumentError, match="unsupported_math"):
        render_source_text("До $" + math + "$ после")


def test_tex_outside_inline_math_is_plain_text():
    text = r"\input{secret} и $x^2$, затем \write18{bad}"
    rendered = render_source_text(text)
    assert r"\input{secret}" not in rendered and r"\write18{bad}" not in rendered
    assert r"\textbackslash{}input\{secret\}" in rendered
    assert r"\(x^2\)" in rendered


@pytest.mark.parametrize(
    "instruction", ["Впишите правильный ответ.", "Введите правильный ответ:", "Запишите ответ."]
)
def test_source_website_labels_hidden_only_in_display(instruction):
    text = instruction + "\n[рисунок 1]\nРамка в поле (см. рисунок). [рисунок 2]"
    assert display_statement(text) == "Рамка в поле (см. рисунок)."
    sheet = worksheet()
    original = SourceTask.model_validate(
        {**sheet.tasks[0].model_dump(), "statement_exact": text, "sha256": source_task_digest(text)}
    )
    sheet = TaskWorksheet.model_validate({**sheet.model_dump(), "tasks": [original.model_dump()]})
    source = source_worksheet_tex(sheet, ((),), "Times New Roman")
    assert instruction not in source and "[рисунок" not in source
    assert sheet.tasks[0].statement_exact == text
    assert sheet.tasks[0].sha256 == source_task_digest(text)
    assert (
        display_statement("Объясните ответ. Введите ток в амперах.")
        == "Объясните ответ. Введите ток в амперах."
    )


def test_model_tex_rejected_and_ordinary_text_escaped():
    sheet = worksheet(math=(r"\input{secret}",))
    with pytest.raises(DocumentError, match="unsupported_math"):
        source_worksheet_tex(sheet, ((),), "Times New Roman")
    task = sheet.tasks[0]
    text = r"Текст \input{secret}"
    task = SourceTask.model_validate(
        {
            **task.model_dump(),
            "statement_exact": text,
            "statement_math_exact": [],
            "sha256": source_task_digest(text),
        }
    )
    safe = TaskWorksheet.model_validate({**sheet.model_dump(), "tasks": [task.model_dump()]})
    source = source_worksheet_tex(safe, ((),), "Times New Roman")
    assert r"\input{secret}" not in source
    assert r"\setmainfont{Arial}" in source


def test_asset_written_under_generated_name(tmp_path, monkeypatch):
    sheet = worksheet(images=(png_asset(),))
    compiled = AsyncMock(return_value=Attachment("tasks-v2.pdf", b"%PDF-synthetic"))
    monkeypatch.setattr(_SourceCompiler, "_compile", compiled)
    renderer = SourceDocuments(engine="tectonic", font="Times New Roman", output_dir=tmp_path)
    result = run(renderer.worksheet(sheet))
    assert result.name == "tasks-v2.pdf"
    source = compiled.call_args.args[0]
    assert r"\includegraphics[" in source
    assert "source-" in source and ".png}" in source
    assert sheet.tasks[0].images[0].data_base64 not in source
    assert compiled.call_args.args[1:3] == (sheet.preparation_id, sheet.version)
    with pytest.raises(TypeError, match="TaskWorksheet"):
        run(renderer.worksheet({}))


def test_whole_snapshot_revalidated(tmp_path):
    sheet = worksheet()
    forged_task = SourceTask.model_construct(
        **{
            **sheet.tasks[0].model_dump(),
            "statement_exact": "tampered source",
        }
    )
    forged = TaskWorksheet.model_construct(**{**sheet.model_dump(), "tasks": (forged_task,)})
    with pytest.raises(ValueError, match="digest"):
        run(SourceDocuments(output_dir=tmp_path).worksheet(forged))


def test_source_compiler_copies_only_generated_assets(tmp_path):
    compiler = _SourceCompiler(
        {"source-abc.png": b"verified synthetic PNG"},
        engine="tectonic",
        font="Times New Roman",
        output_dir=tmp_path,
        timeout_seconds=30,
    )
    directory = compiler._write_source("trusted template", "prep", 1, "tasks")
    assert (directory / "source-abc.png").read_bytes() == b"verified synthetic PNG"
    assert (directory / "document.tex").read_text() == "trusted template"


def test_total_cleaned_image_budget(tmp_path, monkeypatch):
    sheet = worksheet(images=(png_asset(), png_asset()))
    values = iter([b"a" * 10_000_001, b"b" * 10_000_001])
    monkeypatch.setattr("prepa.documents.source.clean_png", lambda asset: next(values))
    with pytest.raises(DocumentError, match="source_images_too_large"):
        run(SourceDocuments(output_dir=tmp_path).worksheet(sheet))


@pytest.mark.parametrize(
    "part,color", [(1, "sheetAccent"), (2, "sheetAdvanced"), (None, "sheetAccent")]
)
def test_task_number_color_uses_source_exam_part(part, color):
    sheet = worksheet()
    task = SourceTask.model_validate({**sheet.tasks[0].model_dump(), "exam_part": part})
    sheet = TaskWorksheet.model_validate({**sheet.model_dump(), "tasks": [task.model_dump()]})
    source = source_worksheet_tex(sheet, ((),), "Times New Roman")
    assert r"\noindent{\color{" + color + r"}\bfseries 1.}" in source
    assert "newpage" not in source and "clearpage" not in source
