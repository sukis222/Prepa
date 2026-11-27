"""Render the vector diagrams for the first two cards to portable 2x PNGs."""

from pathlib import Path
import re

import pymupdf


def main() -> None:
    tasks = Path(__file__).resolve().parent.parent
    diagrams = sorted(
        p for task in ("task-01", "task-02")
        for p in (tasks / task / "images").glob("*.svg")
    )
    for path in diagrams:
        source = path.read_text(encoding="utf-8")
        # Arrowheads are explicit paths: MuPDF does not render SVG markers.
        source = re.sub(r"<defs>.*?</defs>", "", source, flags=re.S)
        source = re.sub(r' marker-(?:start|end)="[^"]*"', "", source)
        path.write_text(source, encoding="utf-8")
        with pymupdf.open(stream=source.encode("utf-8"), filetype="svg") as svg:
            with pymupdf.open("pdf", svg.convert_to_pdf()) as document:
                document[0].get_pixmap(
                    matrix=pymupdf.Matrix(2, 2), alpha=False
                ).save(path.with_suffix(".png"))
        print(path.relative_to(tasks))


if __name__ == "__main__":
    main()
