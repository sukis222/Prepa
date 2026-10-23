"""Source-only worksheets. Text and PNGs come from verified sources, never model TeX."""

import asyncio
import base64
import hashlib
import io
import re
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, UnidentifiedImageError

from prepa.documents.delivery import Attachment
from prepa.documents.latex import PREAMBLE, DocumentError, LatexDocuments, escape_text, safe_math
from prepa.schemas.source import SourceImage, TaskWorksheet

MAX_IMAGE_BYTES = 10_000_000
MAX_IMAGE_PIXELS = 20_000_000


def render_source_text(text: str) -> str:
    """Render source inline math only; unmatched and doubled dollars remain text."""
    parts = []
    end = 0
    for match in re.finditer(r"(?<!\$)\$([^$]+)\$(?!\$)", text):
        parts.append(escape_text(text[end : match.start()]))
        parts.append(r"\(" + safe_math(match.group(1)) + r"\)")
        end = match.end()
    parts.append(escape_text(text[end:]))
    return "".join(parts)


def clean_png(asset: SourceImage) -> bytes:
    """Decode, check identity and dimensions, then strip metadata before TeX sees it."""
    try:
        data = base64.b64decode(asset.data_base64, validate=True)
    except ValueError:
        raise DocumentError("invalid_source_image") from None
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise DocumentError("invalid_source_image")
    if hashlib.sha256(data).hexdigest() != asset.sha256:
        raise DocumentError("source_image_changed")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if (
                image.format != "PNG"
                or image.size != (asset.width, asset.height)
                or image.width * image.height > MAX_IMAGE_PIXELS
            ):
                raise DocumentError("invalid_source_image")
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            converted = image if image.mode in ("L", "RGB", "RGBA") else image.convert("RGB")
            stripped = Image.new(converted.mode, converted.size)
            stripped.paste(converted)
            output = io.BytesIO()
            stripped.save(output, format="PNG")
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
        raise DocumentError("invalid_source_image") from None
    cleaned = output.getvalue()
    if len(cleaned) > MAX_IMAGE_BYTES:
        raise DocumentError("invalid_source_image")
    return cleaned


def source_citation(url: str, page: int | None) -> str:
    parsed = urlparse(url)
    # Local source provenance remains in the stored worksheet, not the public PDF.
    label = "Prepa, проверенный набор" if not parsed.scheme or parsed.scheme == "file" else url
    text = escape_text("Источник: " + label + (f", стр. {page}" if page else ""))
    return text.replace("/", r"/\allowbreak{}").replace(".", r".\allowbreak{}")


def source_worksheet_tex(
    worksheet: TaskWorksheet, image_names: tuple[tuple[str, ...], ...], font: str
) -> str:
    worksheet_font = "Arial" if font == "Times New Roman" else "DejaVu Sans"
    preamble = PREAMBLE.replace("DejaVu Serif", worksheet_font).replace(
        r"\begin{document}",
        r"\usepackage{tikz,graphicx}"
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
        r"{\fontsize{21}{25}\selectfont\bfseries " + escape_text(worksheet.title) + r"\par}",
        r"\vspace{3mm}",
        r"\begingroup\setlength{\fboxsep}{3mm}"
        r"\noindent\colorbox{sheetFill}{\parbox{\dimexpr\linewidth-2\fboxsep\relax}{"
        r"\tikz[baseline=-0.6mm]\fill[sheetAccent] (0,0)--(1.8mm,1.8mm)--"
        r"(3.6mm,0)--(1.8mm,-1.8mm)--cycle;\hspace{3mm}"
        r"\textbf{Задачи из проверенных источников}}}\endgroup\par\vspace{3mm}",
    ]
    for number, (task, names) in enumerate(zip(worksheet.tasks, image_names, strict=True), 1):
        body = [r"\noindent " + str(number) + ". " + render_source_text(task.statement_exact)]
        body.extend(r"\[" + safe_math(math) + r"\]" for math in task.statement_math_exact)
        for name in names:
            body.append(
                r"\par\nopagebreak[4]\begin{center}\includegraphics["
                r"width=0.8\linewidth,height=45mm,keepaspectratio]{" + name + r"}\end{center}"
            )
        body.extend(
            [
                r"\par\nopagebreak[4]{\footnotesize "
                + source_citation(task.source_url, task.page)
                + r"\par}",
                r"\nopagebreak[4]\vspace{2mm}\nopagebreak[4]",
                r"\noindent\begin{tikzpicture}\clip (0,0) rectangle (\linewidth,70mm);"
                r"\draw[sheetGrid,step=5mm,line width=0.2pt](0,0) grid (\linewidth,70mm);"
                r"\end{tikzpicture}\par",
            ]
        )
        task_body = "\n".join(body)
        parts.extend(
            [
                r"\begin{lrbox}{\sheetTask}\begin{minipage}{\linewidth}",
                task_body,
                r"\end{minipage}\end{lrbox}",
                r"\ifdim\dimexpr\ht\sheetTask+\dp\sheetTask\relax<\textheight",
                r"\Needspace{\dimexpr\ht\sheetTask+\dp\sheetTask+5mm\relax}",
                r"\noindent\usebox{\sheetTask}\par",
                r"\else",
                task_body,
                r"\fi\vspace{5mm}",
            ]
        )
    return "\n".join(parts) + "\n" + r"\end{document}" + "\n"


class _SourceCompiler(LatexDocuments):
    def __init__(
        self,
        images: dict[str, bytes],
        *,
        engine: str,
        font: str,
        output_dir: Path,
        timeout_seconds: float,
    ) -> None:
        super().__init__(
            engine=engine, font=font, output_dir=output_dir, timeout_seconds=timeout_seconds
        )
        self.images = images

    def _write_source(self, source: str, preparation_id: str, version: int, name: str) -> Path:
        directory = super()._write_source(source, preparation_id, version, name)
        for filename, content in self.images.items():
            (directory / filename).write_bytes(content)
        return directory


class SourceDocuments:
    def __init__(
        self,
        *,
        engine: str = "xelatex",
        font: str = "DejaVu Serif",
        output_dir: str | Path = "output/pdf",
        timeout_seconds: float = 30,
    ) -> None:
        # Reuse the same allowlisted engines/fonts and bounds as legacy documents.
        self.compiler = LatexDocuments(
            engine=engine, font=font, output_dir=output_dir, timeout_seconds=timeout_seconds
        )

    async def worksheet(self, worksheet: TaskWorksheet) -> Attachment:
        if not isinstance(worksheet, TaskWorksheet):
            raise TypeError("Source renderer requires TaskWorksheet")
        worksheet = TaskWorksheet.model_validate(worksheet.model_dump(mode="json"))
        images: dict[str, bytes] = {}
        names: list[tuple[str, ...]] = []
        for task in worksheet.tasks:
            task_names = []
            for asset in task.images:
                content = await asyncio.to_thread(clean_png, asset)
                filename = "source-" + hashlib.sha256(content).hexdigest() + ".png"
                images[filename] = content
                task_names.append(filename)
            names.append(tuple(task_names))
        if sum(len(data) for data in images.values()) > 20_000_000:
            raise DocumentError("source_images_too_large")
        source = source_worksheet_tex(worksheet, tuple(names), self.compiler.font)
        compiler = _SourceCompiler(
            images,
            engine=self.compiler.engine,
            font=self.compiler.font,
            output_dir=self.compiler.output_dir,
            timeout_seconds=self.compiler.timeout_seconds,
        )
        return await compiler._compile(source, worksheet.preparation_id, worksheet.version, "tasks")
