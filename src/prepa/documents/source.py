"""Source-only worksheets. Text and PNGs come from verified sources, never model TeX."""

import asyncio
import base64
import hashlib
import io
import re
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from prepa.documents.delivery import Attachment
from prepa.documents.latex import PREAMBLE, DocumentError, LatexDocuments, escape_text, safe_math
from prepa.schemas.source import SourceImage, TaskWorksheet

MAX_IMAGE_BYTES = 10_000_000
MAX_IMAGE_PIXELS = 20_000_000


def render_source_text(text: str) -> str:
    """Render explicit source inline/display math through the same safe formula boundary."""
    parts = []
    end = 0
    for match in re.finditer(r"(?<!\$)(\$\$|\$)([^$]+)\1(?!\$)", text):
        parts.append(escape_text(text[end : match.start()]).replace("⊗", r"\(\otimes\)"))
        formula = safe_math(
            match.group(2)
            .replace("\n", " ")
            .replace("~", r"\ ")
            .replace("ℰ", r"\mathcal{E}")
            .replace("⊗", r"\otimes ")
        )
        parts.append(r"\[" + formula + r"\]" if match.group(1) == "$$" else r"\(" + formula + r"\)")
        end = match.end()
    parts.append(escape_text(text[end:]).replace("⊗", r"\(\otimes\)"))
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


def display_statement(text: str) -> str:
    """Hide website instructions and figure placeholders without altering stored sources."""
    text = re.sub(r"\[\s*рисунок\s+\d+\s*\]", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(
        r"^(?:впишите|введите|запишите)\s+(?:правильный\s+)?ответ\s*[.:]\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"^дайте\s+разв[её]рнутый\s+ответ\s*[.:]\s*", "", text, flags=re.I)
    return text.strip()


def source_worksheet_tex(
    worksheet: TaskWorksheet, image_names: tuple[tuple[str, ...], ...], font: str
) -> str:
    worksheet_font = "Arial" if font == "Times New Roman" else "DejaVu Sans"
    preamble = PREAMBLE.replace("DejaVu Serif", worksheet_font).replace(
        r"\begin{document}",
        r"\usepackage{graphicx}"
        "\n"
        r"\definecolor{sheetAccent}{HTML}{278757}"
        "\n"
        r"\definecolor{sheetAdvanced}{HTML}{C86B20}"
        "\n"
        r"\setlength{\parskip}{3pt}"
        "\n"
        r"\begin{document}",
    )
    parts = [
        preamble,
        r"{\fontsize{20}{24}\selectfont\bfseries " + escape_text(worksheet.title) + r"\par}",
        r"\vspace{4mm}",
    ]
    for number, (task, names) in enumerate(zip(worksheet.tasks, image_names, strict=True), 1):
        color = "sheetAdvanced" if getattr(task, "exam_part", None) == 2 else "sheetAccent"
        parts.extend(
            [
                r"\par\addvspace{5mm}\Needspace{"
                + str(min(180, 35 + 38 * len(names)) if names else 25)
                + "mm}",
                r"\noindent{\color{"
                + color
                + r"}\bfseries "
                + str(number)
                + r".}\hspace{2mm}"
                + render_source_text(display_statement(task.statement_exact)),
            ]
        )
        parts.extend(r"\[" + safe_math(math) + r"\]" for math in task.statement_math_exact)
        for name in names:
            parts.append(
                r"\par\nopagebreak[3]\begin{center}\includegraphics["
                r"width=0.65\linewidth,height=38mm,keepaspectratio]{" + name + r"}\end{center}"
            )
        parts.append(r"\par")
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
