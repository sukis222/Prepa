"""PDF trust boundary and compiler lifecycle; offline tests never require TeX."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from prepa.documents.latex import (
    DocumentError,
    LatexDocuments,
    escape_text,
    safe_math,
    student_tex,
    teacher_tex,
)


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize(
    "value",
    [
        "^^5cinput{/etc/passwd}",
        "^^5cwrite18{touch pwned}",
        "^^^^005cinput{x}",
        r"\input{/etc/passwd}",
        r"\write18{touch pwned}",
        r"\csname input\endcsname",
        r"\def\x{\x}\x",
        r"\begin{document}",
        r"\catcode1=0",
        r"\special{pdf:literal}",
        r"\includegraphics{file}",
        r"\tikz{\draw (0,0)--(1,1);}",
        r"\href{run:file}{x}",
        "x$bad",
        "x%comment",
        "x#1",
        "{x",
        "x}",
        "{" * 21 + "x" + "}" * 21,
        "x\n",
        "x" * 2001,
        "",
        r"\a",
        "\\",
        "a&b",
        "a~b",
        "a\x00b",
        "a\x7fb",
        r"\\input{x}",
    ],
)
def test_untrusted_math_rejected(value):
    with pytest.raises(DocumentError, match="unsupported_math"):
        safe_math(value)


@pytest.mark.parametrize(
    "value",
    [
        r"v=\frac{s}{t}",
        r"\sqrt{x^2+y_1^2}",
        r"F=m\cdot a",
        r"\Delta t=2\,\mathrm{s}",
        r"\text{скорость}=10",
        r"\left\{x\right\}",
        "E=mc^2",
    ],
)
def test_physics_math(value):
    assert safe_math(value) == value


def test_plain_text_never_becomes_commands():
    text = escape_text(r"100% & a_b $x$ {z} #1 ~ ^ \input{secret}")
    assert r"\input{secret}" not in text
    assert r"\textbackslash{}input\{secret\}" in text
    assert r"100\% \& a\_b \$x\$" in text
    assert escape_text("a\nb") == "a\n\nb"
    assert escape_text("⊙ ⊗") == r"\(\odot\) \(\otimes\)"
    with pytest.raises(DocumentError, match="invalid_text"):
        escape_text("a\x00b")


def test_student_boundary_and_teacher_answers(package):
    student_id = package.context.brief.student_ids[0]
    lesson = package.for_student(student_id)
    student = student_tex(lesson)
    teacher = teacher_tex(package)
    assert "Теория" in student and "Домашнее задание" in student
    assert "Не передавайте этот документ ученикам" in teacher
    # Worked examples intentionally contain solutions; practice answers must not leak.
    assert "450" in teacher and "450" not in student
    assert package.context.brief.student_ids[1] not in student
    with pytest.raises(TypeError, match="StudentLesson"):
        run(LatexDocuments().student(package))


def test_no_homework_document(package):
    lesson = package.for_student(package.context.brief.student_ids[0])
    lesson = type(lesson).model_validate({**lesson.model_dump(), "homework": []})
    assert "Не задано" in student_tex(lesson)


@pytest.mark.parametrize("engine,timeout", [("sh", 30), ("xelatex", 0), ("xelatex", float("nan"))])
def test_renderer_configuration(engine, timeout):
    with pytest.raises(ValueError):
        LatexDocuments(engine=engine, timeout_seconds=timeout)


def test_compiler_missing_and_input_limit(tmp_path, monkeypatch):
    docs = LatexDocuments(output_dir=tmp_path)
    monkeypatch.setattr("prepa.documents.latex.shutil.which", lambda _: None)
    with pytest.raises(DocumentError, match="latex_engine_unavailable"):
        run(docs._compile("safe", "p", 1, "student"))
    with pytest.raises(DocumentError, match="document_too_large"):
        run(docs._compile("x" * 500001, "p", 1, "student"))


@pytest.mark.parametrize("engine", ["xelatex", "tectonic"])
def test_isolated_compilation_and_flags(engine, tmp_path, monkeypatch, package):
    docs = LatexDocuments(engine=engine, output_dir=tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "never-forward")
    monkeypatch.setattr("prepa.documents.latex.shutil.which", lambda name: "/bin/" + name)
    directories = []

    async def create(*command, **kwargs):
        directory = kwargs["cwd"]
        directories.append(directory)
        assert "OPENROUTER_API_KEY" not in kwargs["env"]
        assert kwargs["env"]["openin_any"] == "p"
        assert kwargs["env"]["shell_escape"] == "f"
        assert ("--untrusted" if engine == "tectonic" else "-no-shell-escape") in command
        (directory / "document.pdf").write_bytes(b"%PDF-1.5\nsynthetic")
        return type("Process", (), {"returncode": 0, "wait": AsyncMock(return_value=0)})()

    monkeypatch.setattr("prepa.documents.latex.asyncio.create_subprocess_exec", create)
    teacher = run(docs.teacher(package))
    student = run(docs.student(package.for_student(package.context.brief.student_ids[0])))
    assert teacher.name == "teacher-v1.pdf"
    assert student.name.endswith("-v1.pdf")
    assert teacher.content.startswith(b"%PDF-")
    assert len(set(directories)) == 2
    assert all(directory.parent.name == "v1" for directory in directories)


def test_compiler_errors_are_sanitized(tmp_path, monkeypatch):
    docs = LatexDocuments(output_dir=tmp_path)
    monkeypatch.setattr("prepa.documents.latex.shutil.which", lambda _: "/bin/xelatex")
    create = AsyncMock(side_effect=OSError("contains secret"))
    monkeypatch.setattr("prepa.documents.latex.asyncio.create_subprocess_exec", create)
    with pytest.raises(DocumentError, match="^latex_engine_unavailable$"):
        run(docs._compile("safe", "p", 1, "student"))
    create.side_effect = None
    create.return_value = type("Process", (), {"returncode": 1, "wait": AsyncMock()})()
    with pytest.raises(DocumentError, match="latex_compilation_failed"):
        run(docs._compile("safe", "p", 1, "student"))


@pytest.mark.parametrize("cancel", [False, True])
def test_timeout_and_cancellation_kill_child(tmp_path, monkeypatch, cancel):
    docs = LatexDocuments(output_dir=tmp_path)
    monkeypatch.setattr("prepa.documents.latex.shutil.which", lambda _: "/bin/xelatex")

    class Process:
        returncode = None
        killed = False

        async def wait(self):
            return 0

        def kill(self):
            self.killed = True
            self.returncode = -9

    process = Process()
    monkeypatch.setattr(
        "prepa.documents.latex.asyncio.create_subprocess_exec", AsyncMock(return_value=process)
    )

    async def wait_for(coro, **kwargs):
        coro.close()
        raise asyncio.CancelledError() if cancel else TimeoutError()

    monkeypatch.setattr("prepa.documents.latex.asyncio.wait_for", wait_for)
    with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
        run(docs._compile("safe", "p", 1, "student"))
    assert process.killed


@pytest.mark.parametrize("contents", [None, b"", b"not PDF", b"x" * 10000001])
def test_invalid_pdf(tmp_path, contents):
    if contents is not None:
        (tmp_path / "document.pdf").write_bytes(contents)
    with pytest.raises(DocumentError, match="invalid_pdf"):
        LatexDocuments._read_pdf(tmp_path)


def test_missing_glyph_is_failure(tmp_path):
    (tmp_path / "document.pdf").write_bytes(b"%PDF-1.5")
    (tmp_path / "document.log").write_text("Missing character: nonexistent glyph")
    with pytest.raises(DocumentError, match="missing_glyph"):
        LatexDocuments._read_pdf(tmp_path)


def test_tasks_sheet_only_conditions(package):
    from prepa.documents.latex import task_sheet_tex

    lesson = package.for_student(package.context.brief.student_ids[0])
    text = task_sheet_tex(lesson)
    assert escape_text(lesson.lesson_assignments[0].topic) in text
    for task in lesson.lesson_assignments:
        assert escape_text(task.statement.text) in text
    assert "Теория" not in text
    assert "Домашнее задание" not in text
    assert "Ответ" not in text
    assert "Решение" not in text
    assert lesson.student_id not in text
    assert lesson.preparation_id not in text
    assert "450" not in text and "300" not in text
    assert escape_text(lesson.homework[0].statement.text) not in text
    assert "estimated_minutes" not in text and "basic" not in text
    assert escape_text(lesson.theory.sections[0].explanation.text) not in text


def test_tasks_renderer_requires_projection(package, tmp_path, monkeypatch):
    docs = LatexDocuments(output_dir=tmp_path)
    compiled = AsyncMock(return_value=type("File", (), {"name": "tasks-v1.pdf"})())
    monkeypatch.setattr(docs, "_compile", compiled)
    lesson = package.for_student(package.context.brief.student_ids[0])
    attachment = run(docs.tasks(lesson))
    assert attachment.name == "tasks-v1.pdf"
    assert compiled.call_args.args[3] == "tasks"
    assert "Ответ" not in compiled.call_args.args[0]
    with pytest.raises(TypeError, match="StudentLesson"):
        run(docs.tasks(package))


def test_worksheet_space_and_demo_marker(package, tmp_path, monkeypatch):
    from prepa.documents.latex import task_sheet_tex

    lesson = package.for_student(package.context.brief.student_ids[0])
    source = task_sheet_tex(lesson)
    assert source.count(r"step=5mm") == 2 * len(lesson.lesson_assignments)
    assert source.count(r"grid (\linewidth,70mm)") == 2 * len(lesson.lesson_assignments)
    assert r"\colorbox{sheetFill}" in source
    assert "278757" in source and "EDF7F0" in source
    assert "Блок 1. Задачи по теме" in source
    assert source.count(r"\Needspace{\dimexpr\ht\sheetTask+") == len(lesson.lesson_assignments)
    assert source.count(r"\begin{minipage}") == len(lesson.lesson_assignments)
    assert source.count(r"\else") == len(lesson.lesson_assignments)
    assert source.count(r"\nopagebreak[4]") == 4 * len(lesson.lesson_assignments)
    assert source.count(r"\begingroup") == source.count(r"\endgroup")
    assert "ДЕМО" not in source
    assert "ДЕМО: вымышленные задания" in task_sheet_tex(lesson, demo=True)
    docs = LatexDocuments(output_dir=tmp_path)
    compiled = AsyncMock(return_value=type("File", (), {"name": "DEMO-tasks-v1.pdf"})())
    monkeypatch.setattr(docs, "_compile", compiled)
    assert run(docs.tasks(lesson, demo=True)).name == "DEMO-tasks-v1.pdf"
    assert compiled.call_args.args[3] == "DEMO-tasks"
    assert "ДЕМО: вымышленные задания" in compiled.call_args.args[0]


@pytest.mark.parametrize(
    "source,rendered",
    [
        ("x_0 = 10 м", r"x_0 = 10 \,\text{м}"),
        ("v=4 м/с", r"v=4 \,\text{м}/\text{с}"),
        (r"v=4\mathrm{м/с}", r"v=4\mathrm{\text{м}/\text{с}}"),
        (r"\frac{м}{с}", r"\frac{\text{м}}{\text{с}}"),
        (r"\text{скорость}", r"\text{скорость}"),
        (r"\textrm{м/с}", r"\textrm{м/с}"),
        (r"\text{м/{с}}+с", r"\text{м/{с}}+\text{с}"),
        (r"\{м\}", r"\{\text{м}\}"),
    ],
)
def test_cyrillic_math_uses_text_font(source, rendered):
    assert safe_math(source) == rendered
    assert safe_math(rendered) == rendered


def test_worksheet_title_override_is_presentation_only(package, tmp_path, monkeypatch):
    from prepa.documents.latex import task_sheet_tex

    lesson = package.for_student(package.context.brief.student_ids[0])
    snapshot = lesson.model_dump_json()
    text = task_sheet_tex(lesson, title=r"Термодинамика \input{secret}")
    assert r"\textbackslash{}input\{secret\}" in text
    assert r"\input{secret}" not in text
    assert lesson.model_dump_json() == snapshot
    docs = LatexDocuments(output_dir=tmp_path)
    compiled = AsyncMock()
    monkeypatch.setattr(docs, "_compile", compiled)
    run(docs.tasks(lesson, title="Термодинамика. Циклы и изопроцессы"))
    assert "Термодинамика. Циклы и изопроцессы" in compiled.call_args.args[0]
    for title in ("", " ", "x" * 301):
        with pytest.raises(ValueError, match="Worksheet title"):
            run(docs.tasks(lesson, title=title))
