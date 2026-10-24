"""Teacher copy: existing source explanations only, never generated solutions."""

import asyncio
import hashlib

from prepa.documents.delivery import Attachment
from prepa.documents.latex import PREAMBLE, DocumentError, escape_text, safe_math
from prepa.documents.source import (
    SourceDocuments,
    _SourceCompiler,
    clean_png,
    display_statement,
    render_source_text,
    worksheet_title,
)
from prepa.schemas import TaskWorksheet


async def solution_document(
    documents: SourceDocuments, worksheet: TaskWorksheet
) -> Attachment | None:
    worksheet = TaskWorksheet.model_validate(worksheet.model_dump(mode="json"))
    if not any(task.solution for task in worksheet.tasks):
        return None
    font = documents.compiler.font
    preamble = PREAMBLE.replace("DejaVu Serif", font).replace(
        r"\begin{document}", r"\usepackage{graphicx}" + "\n" + r"\begin{document}"
    )
    parts = [
        preamble,
        r"{\Large\bfseries " + escape_text(worksheet_title(worksheet.title)) + r". Решения\par}",
        r"\smallskip Разборы взяты из источника; требуется проверка преподавателем.\par",
    ]
    images: dict[str, bytes] = {}
    for number, task in enumerate(worksheet.tasks, 1):
        parts.extend(
            [
                r"\Needspace{4\baselineskip}\medskip\noindent\textbf{"
                + str(number)
                + r".} "
                + render_source_text(display_statement(task.statement_exact)),
            ]
        )
        parts.extend(r"\[" + safe_math(math) + r"\]" for math in task.statement_math_exact)
        for asset in task.images:
            content = await asyncio.to_thread(clean_png, asset)
            name = "condition-" + hashlib.sha256(content).hexdigest() + ".png"
            images[name] = content
            parts.append(
                r"\par\includegraphics[width=.6\linewidth,height=38mm,keepaspectratio]{"
                + name
                + "}"
            )
        if task.solution is None:
            parts.append(r"\par\textit{Подходящее решение в источнике не найдено.}\par")
            continue
        parts.append(r"\par\smallskip\textbf{Решение.} " + render_source_text(task.solution.text))
        for asset in task.solution.images:
            content = await asyncio.to_thread(clean_png, asset)
            name = "solution-" + hashlib.sha256(content).hexdigest() + ".png"
            images[name] = content
            parts.append(
                r"\par\includegraphics[width=.7\linewidth,height=45mm,keepaspectratio]{"
                + name
                + "}"
            )
        parts.append(r"\par")
    if sum(map(len, images.values())) > 20_000_000:
        raise DocumentError("source_images_too_large")
    compiler = _SourceCompiler(
        images,
        engine=documents.compiler.engine,
        font=documents.compiler.font,
        output_dir=documents.compiler.output_dir,
        timeout_seconds=documents.compiler.timeout_seconds,
    )
    return await compiler._compile(
        "\n".join(parts) + "\n" + r"\end{document}",
        worksheet.preparation_id,
        worksheet.version,
        "solutions",
    )
