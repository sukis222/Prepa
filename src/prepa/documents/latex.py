"""Static LaTeX templates, validated math, bounded isolated PDF compilation."""

import asyncio
import math
import os
import re
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path

from prepa.documents.delivery import Attachment
from prepa.schemas import (
    Assignment,
    LessonPackage,
    StudentAssignment,
    StudentLesson,
    TextBlock,
    Theory,
)


class DocumentError(RuntimeError):
    """Safe error code; compiler diagnostics and model content are never logged."""


ESCAPES = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "$": r"\$",
    "&": r"\&",
    "#": r"\#",
    "%": r"\%",
    "_": r"\_",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "⊙": r"\(\odot\)",
    "⊗": r"\(\otimes\)",
    "⊥": r"\(\perp\)",
}
MATH_COMMANDS = frozenset(
    "frac dfrac tfrac sqrt vec overline underline hat bar dot ddot mathrm mathbf mathit "
    "mathsf mathcal text textrm operatorname left right cdot times otimes div pm mp "
    "odot le leq ge geq ne neq "
    "approx equiv sim propto infty degree circ angle perp parallel sin cos tan cot "
    "arcsin arccos arctan ln log exp lim sum prod int iint oint partial nabla Delta "
    "alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda "
    "mu nu xi pi varpi rho varrho sigma varsigma tau upsilon phi varphi chi psi omega "
    "Gamma Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega quad qquad ldots cdots "
    "rightarrow leftarrow Rightarrow Leftrightarrow to in notin subset supset cup cap "
    "emptyset forall exists lvert rvert vert lVert rVert Vert lbrace rbrace langle rangle".split()
)


def escape_text(value: str) -> str:
    """Only ordinary text is accepted here; backslashes cannot introduce commands."""
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
        raise DocumentError("invalid_text")
    return "".join(ESCAPES.get(char, char) for char in value).replace("\n", "\n\n")


def safe_math(value: str) -> str:
    """Small expression language: no environments, definitions, files or catcodes."""
    if not value or len(value) > 2000 or "^^" in value:
        raise DocumentError("unsupported_math")
    depth = 0
    position = 0
    while position < len(value):
        char = value[position]
        if char in "$%#&~" or ord(char) < 32 or char == "\x7f":
            raise DocumentError("unsupported_math")
        if char == "\\":
            match = re.match(r"\\([a-zA-Z]+|[,;:! {}|])", value[position:])
            if match is None:
                raise DocumentError("unsupported_math")
            command = match.group(1)
            if len(command) > 1 and command not in MATH_COMMANDS:
                raise DocumentError("unsupported_math")
            # Single-letter commands must be explicitly listed as well.
            if command.isalpha() and command not in MATH_COMMANDS:
                raise DocumentError("unsupported_math")
            position += len(match.group())
            continue
        if char == "{":
            depth += 1
            if depth > 20:
                raise DocumentError("unsupported_math")
        elif char == "}":
            depth -= 1
            if depth < 0:
                raise DocumentError("unsupported_math")
        position += 1
    if depth:
        raise DocumentError("unsupported_math")
    return cyrillic_math(value)


def cyrillic_math(value: str) -> str:
    """Validated Cyrillic units use the configured body font, not Latin math glyphs."""
    result: list[str] = []
    text_groups: list[bool] = [False]
    next_text = False
    position = 0
    while position < len(value):
        char = value[position]
        if char == "\\":
            command = re.match(r"\\([a-zA-Z]+|.)", value[position:])
            assert command is not None  # Already lexically checked by safe_math.
            result.append(command.group())
            next_text = command.group(1) in ("text", "textrm")
            position += len(command.group())
            continue
        if char == "{":
            text_groups.append(text_groups[-1] or next_text)
            next_text = False
        elif char == "}":
            text_groups.pop()
        elif not char.isspace():
            next_text = False
        if not text_groups[-1]:
            letters = re.match(r"[\u0400-\u052f][\u0300-\u036f\u0400-\u052f]*", value[position:])
            if letters:
                if position and value[position - 1].isspace():
                    result.append(r"\,")
                result.append(r"\text{" + letters.group() + "}")
                position += len(letters.group())
                continue
        result.append(char)
        position += 1
    return "".join(result)


def block(value: TextBlock) -> str:
    return (
        escape_text(value.text)
        + "\n\n"
        + "\n".join(r"\[" + safe_math(expression) + r"\]" for expression in value.math)
    )


def theory_tex(theory: Theory) -> str:
    parts = [r"\section*{Теория}"]
    for section in theory.sections:
        parts.extend(
            [r"\subsection*{" + escape_text(section.title) + "}", block(section.explanation)]
        )
        for formula in section.formulas:
            parts.extend(
                [
                    r"\[" + safe_math(formula.expression) + r"\]",
                    escape_text(formula.meaning),
                    "\n\nУсловия: " + escape_text(formula.conditions),
                    "\n\nЕдиницы СИ: " + escape_text(formula.units),
                ]
            )
        for example in section.worked_examples:
            parts.extend([r"\paragraph{Разобранный пример}", block(example.statement)])
            parts.extend(block(step) for step in example.solution)
            parts.extend([r"\paragraph{Ответ примера}", block(example.answer)])
    return "\n\n".join(parts)


def tasks_tex(tasks: Sequence[StudentAssignment | Assignment], title: str) -> str:
    parts = [r"\section*{" + escape_text(title) + "}"]
    if not tasks:
        parts.append("Не задано.")
    for number, task in enumerate(tasks, 1):
        parts.extend(
            [
                r"\subsection*{Задание " + str(number) + "}",
                block(task.statement),
            ]
        )
    return "\n\n".join(parts)


def answers_tex(tasks: tuple[Assignment, ...], title: str) -> str:
    parts = [r"\section*{" + escape_text(title) + "}"]
    for number, task in enumerate(tasks, 1):
        parts.extend(
            [
                r"\subsection*{Задание " + str(number) + "}",
                block(task.statement),
                r"\paragraph{Ответ}",
                block(task.answer),
                r"\paragraph{Решение}",
            ]
        )
        parts.extend(block(step) for step in task.solution)
    return "\n\n".join(parts)


PREAMBLE = r"""\documentclass[11pt,a4paper]{article}
\usepackage{fontspec}
\setmainfont{DejaVu Serif}
\usepackage{amsmath,amssymb}
\usepackage{xcolor,needspace}
\usepackage[margin=22mm]{geometry}
\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt}
\setlength{\emergencystretch}{3em}
\sloppy
\begin{document}
"""


def student_tex(lesson: StudentLesson, font: str = "DejaVu Serif") -> str:
    parts = [
        PREAMBLE.replace("DejaVu Serif", font),
        r"\section*{Prepa: материалы занятия}",
        escape_text(
            f"Подготовка {lesson.preparation_id}, версия {lesson.version}. "
            f"Ученик {lesson.student_id}."
        ),
        theory_tex(lesson.theory),
        tasks_tex(lesson.lesson_assignments, "Практика на урок"),
        tasks_tex(lesson.homework, "Домашнее задание"),
        r"\section*{Источники}",
    ]
    parts.extend(escape_text(source.title + ": " + source.source) for source in lesson.sources)
    return "\n\n".join(parts) + "\n" + r"\end{document}" + "\n"


def task_sheet_tex(
    lesson: StudentLesson,
    font: str = "DejaVu Serif",
    *,
    demo: bool = False,
    title: str | None = None,
) -> str:
    """Shared worksheet with a green section band and a static 5 mm writing grid."""
    topics = tuple(dict.fromkeys(task.topic for task in lesson.lesson_assignments))
    worksheet_font = font
    preamble = PREAMBLE.replace("DejaVu Serif", worksheet_font).replace(
        r"\begin{document}",
        r"\usepackage{tikz}"
        "\n"
        r"\definecolor{sheetAccent}{HTML}{278757}"
        "\n"
        r"\definecolor{sheetFill}{HTML}{EDF7F0}"
        "\n"
        r"\definecolor{sheetGrid}{HTML}{DDEAE1}"
        "\n"
        r"\newsavebox{\sheetTask}"
        "\n"
        r"\begin{document}",
    )
    parts = [
        preamble,
        r"{\fontsize{21}{25}\selectfont\bfseries "
        + escape_text(title if title is not None else "; ".join(topics))
        + r"\par}",
        r"\vspace{3mm}",
        r"\begingroup\setlength{\fboxsep}{3mm}"
        r"\noindent\colorbox{sheetFill}{\parbox{\dimexpr\linewidth-2\fboxsep\relax}{"
        r"\tikz[baseline=-0.6mm]\fill[sheetAccent] (0,0)--(1.8mm,1.8mm)--"
        r"(3.6mm,0)--(1.8mm,-1.8mm)--cycle;\hspace{3mm}"
        r"\textbf{Блок 1. Задачи по теме}}}\endgroup\par\vspace{3mm}",
    ]
    if demo:
        parts.append(r"\textbf{ДЕМО: вымышленные задания для проверки работы бота.}\par")
    for number, task in enumerate(lesson.lesson_assignments, 1):
        body = "\n".join(
            [
                r"\noindent " + str(number) + ". " + block(task.statement),
                r"\par\nopagebreak[4]\vspace{2mm}\nopagebreak[4]",
                r"\noindent\begin{tikzpicture}"
                r"\clip (0,0) rectangle (\linewidth,70mm);"
                r"\draw[sheetGrid,step=5mm,line width=0.2pt]"
                r"(0,0) grid (\linewidth,70mm);"
                r"\end{tikzpicture}\par",
            ]
        )
        parts.extend(
            [
                r"\begin{lrbox}{\sheetTask}\begin{minipage}{\linewidth}",
                body,
                r"\end{minipage}\end{lrbox}",
                r"\ifdim\dimexpr\ht\sheetTask+\dp\sheetTask\relax<\textheight",
                r"\Needspace{\dimexpr\ht\sheetTask+\dp\sheetTask+5mm\relax}",
                r"\noindent\usebox{\sheetTask}\par",
                r"\else",
                # An unusually long statement must be able to flow over page boundaries.
                body,
                r"\fi\vspace{5mm}",
            ]
        )
    return "\n".join(parts) + "\n" + r"\end{document}" + "\n"


def teacher_tex(package: LessonPackage, font: str = "DejaVu Serif") -> str:
    brief = package.context.brief
    parts = [
        PREAMBLE.replace("DejaVu Serif", font),
        r"\section*{Prepa: ответы преподавателю}",
        "Не передавайте этот документ ученикам.",
        escape_text(f"Подготовка {brief.preparation_id}, версия {brief.version}."),
        answers_tex(package.assignments.lesson_assignments, "Практика на урок: ответы"),
    ]
    for homework in package.assignments.homeworks:
        parts.append(answers_tex(homework.assignments, f"ДЗ ученика {homework.student_id}: ответы"))
    parts.extend([r"\section*{Проверка материалов}", escape_text(package.review.summary)])
    return "\n\n".join(parts) + "\n" + r"\end{document}" + "\n"


class LatexDocuments:
    """DocumentRenderer. Requires XeLaTeX or Tectonic and DejaVu Serif installed."""

    def __init__(
        self,
        *,
        engine: str = "xelatex",
        font: str = "DejaVu Serif",
        output_dir: str | Path = "output/pdf",
        timeout_seconds: float = 30,
    ) -> None:
        if engine not in ("xelatex", "tectonic"):
            raise ValueError("LATEX_ENGINE must be xelatex or tectonic")
        if not math.isfinite(timeout_seconds) or not 1 <= timeout_seconds <= 120:
            raise ValueError("PDF timeout must be between 1 and 120 seconds")
        if font not in ("DejaVu Serif", "Times New Roman"):
            raise ValueError("PDF font must be DejaVu Serif or Times New Roman")
        self.font = font
        self.engine, self.output_dir, self.timeout_seconds = (
            engine,
            Path(output_dir),
            timeout_seconds,
        )

    async def tasks(
        self, lesson: StudentLesson, *, demo: bool = False, title: str | None = None
    ) -> Attachment:
        if not isinstance(lesson, StudentLesson):
            raise TypeError("Task renderer requires StudentLesson, never LessonPackage")
        lesson = StudentLesson.model_validate(lesson.model_dump(mode="json"))
        if title is not None and (not title.strip() or len(title) > 300):
            raise ValueError("Worksheet title must contain 1 to 300 characters")
        return await self._compile(
            task_sheet_tex(lesson, self.font, demo=demo, title=title),
            lesson.preparation_id,
            lesson.version,
            "DEMO-tasks" if demo else "tasks",
        )

    async def teacher(self, package: LessonPackage) -> Attachment:
        package = LessonPackage.model_validate(package.model_dump(mode="json"))
        brief = package.context.brief
        return await self._compile(
            teacher_tex(package, self.font), brief.preparation_id, brief.version, "teacher"
        )

    async def student(self, lesson: StudentLesson) -> Attachment:
        if not isinstance(lesson, StudentLesson):
            raise TypeError("Student renderer requires StudentLesson, never LessonPackage")
        lesson = StudentLesson.model_validate(lesson.model_dump(mode="json"))
        return await self._compile(
            student_tex(lesson, self.font),
            lesson.preparation_id,
            lesson.version,
            "student-" + lesson.student_id,
        )

    async def _compile(
        self, source: str, preparation_id: str, version: int, name: str
    ) -> Attachment:
        if len(source.encode()) > 500_000:
            raise DocumentError("document_too_large")
        executable = shutil.which(self.engine)
        if executable is None:
            raise DocumentError("latex_engine_unavailable")
        directory = await asyncio.to_thread(
            self._write_source, source, preparation_id, version, name
        )
        command = (
            [executable, "--untrusted", "--keep-logs", "--outdir", str(directory), "document.tex"]
            if self.engine == "tectonic"
            else [
                executable,
                "-no-shell-escape",
                "-halt-on-error",
                "-interaction=nonstopmode",
                "document.tex",
            ]
        )
        # No API keys, DATABASE_URL or TeX override variables reach the child process.
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "TMPDIR": str(directory),
            "openin_any": "p",
            "openout_any": "p",
            "shell_escape": "f",
            "TECTONIC_UNTRUSTED_MODE": "1",
        }
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=directory,
                env=environment,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError:
            raise DocumentError("latex_engine_unavailable") from None
        try:
            await asyncio.wait_for(process.wait(), timeout=self.timeout_seconds)
        except (TimeoutError, asyncio.CancelledError):
            if process.returncode is None:
                process.kill()
            await process.wait()
            raise
        if process.returncode:
            raise DocumentError("latex_compilation_failed")
        content = await asyncio.to_thread(self._read_pdf, directory)
        return Attachment(f"{name}-v{version}.pdf", content)

    def _write_source(self, source: str, preparation_id: str, version: int, name: str) -> Path:
        parent = self.output_dir / preparation_id / f"v{version}"
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory = Path(tempfile.mkdtemp(prefix=name + "-", dir=parent)).resolve()
        (directory / "document.tex").write_text(source, encoding="utf-8")
        return directory

    @staticmethod
    def _read_pdf(directory: Path) -> bytes:
        pdf = directory / "document.pdf"
        try:
            if not 0 < pdf.stat().st_size <= 10_000_000:
                raise DocumentError("invalid_pdf")
            content = pdf.read_bytes()
            log = directory / "document.log"
            if log.exists() and "Missing character:" in log.read_text(errors="replace"):
                raise DocumentError("missing_glyph")
        except OSError:
            raise DocumentError("invalid_pdf") from None
        if not content.startswith(b"%PDF-"):
            raise DocumentError("invalid_pdf")
        return content
