"""Parsers for the FIPI open bank pages (index.php topic tree and questions.php tasks)."""

import re
from collections.abc import Callable
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from prepa.task_bank.models import AnswerKind, BankTask, Exam, KesTopic

from .mathml import local_name, to_latex

KINDS = {
    "краткий ответ": AnswerKind.SHORT,
    "выбор ответа": AnswerKind.SINGLE_CHOICE,
    "выбор ответа из предложенных вариантов": AnswerKind.SINGLE_CHOICE,
    "выбор ответов из предложенных вариантов": AnswerKind.MULTIPLE_CHOICE,
    "установление соответствия": AnswerKind.MATCHING,
    "развернутый ответ": AnswerKind.EXTENDED,
    "развёрнутый ответ": AnswerKind.EXTENDED,
    "расстановка терминов": AnswerKind.FILL_TERMS,
}
PICTURE = re.compile(r"""ShowPicture\w*\(\s*["']([^"']+)["']""")
COUNT = re.compile(r"setQCount\((\d+)")
TOPIC = re.compile(r"^(\d+(?:\.\d+){0,2})\s+(.+)$", re.S)
LABEL = re.compile(r"^[А-ЯA-Z0-9]{1,2}\)$")
SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([.,;:!?)])")
BLOCKS = {"p", "div", "tr", "table", "br", "li", "ul", "ol", "h1", "h2", "h3"}
SKIPPED = {"style", "input", "select", "option", "button", "textarea", "noscript"}


class ParseError(ValueError):
    """The page no longer has the structure this parser was written for."""


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def clean(text: str) -> str:
    lines = (" ".join(line.replace("\xa0", " ").split()) for line in text.split("\n"))
    merged: list[str] = []
    for line in lines:
        if not line:
            continue
        line = SPACE_BEFORE_PUNCTUATION.sub(r"\1", line)
        # Word tables put a list label ("А)", "2)") and its item into separate cells.
        if merged and LABEL.match(merged[-1]):
            merged[-1] += " " + line
        else:
            merged.append(line)
    return "\n".join(merged)


def parse_topics(html: str) -> tuple[KesTopic, ...]:
    """КЭС sections and topics offered by the bank filter, in page order, without duplicates."""

    topics: dict[str, KesTopic] = {}
    for box in soup(html).select("input[name=theme][value]"):
        code = str(box["value"]).strip()
        label = box.find_parent("label")
        title = clean(label.get_text(" ") if label else "")
        title = re.sub(r"^" + re.escape(code) + r"\s+", "", title).rstrip(" :")
        if code and title and code not in topics:
            topics[code] = KesTopic(code=code, title=title)
    if not topics:
        raise ParseError("no КЭС topics found on the bank index page")
    return tuple(topics.values())


def parse_total(html: str) -> int:
    match = COUNT.search(html)
    if match is None:
        raise ParseError("task count is missing from the questions page")
    return int(match.group(1))


class TextWriter:
    """Flattens Word-exported HTML into plain text with $math$ and picture markers."""

    def __init__(self, page_url: str, images: list[str]) -> None:
        self.page_url = page_url
        self.images = images
        self.parts: list[str] = []

    def image(self, url: str) -> None:
        self.images.append(url)
        self.parts.append(f" [рисунок {len(self.images)}] ")

    def walk(self, node: Tag | NavigableString) -> None:
        if isinstance(node, NavigableString):
            if type(node) is NavigableString:
                self.parts.append(str(node).replace("\n", " "))
            return
        name = local_name(node)
        if name == "script":
            for path in PICTURE.findall(node.get_text()):
                # The bank resolves picture paths against the site root.
                self.image(urljoin(self.page_url, "/" + path.lstrip("./")))
            return
        if name in SKIPPED:
            return
        if name == "img" and node.get("src"):
            self.image(urljoin(self.page_url, str(node["src"])))
            return
        if name == "math":
            self.parts.append(" $" + to_latex(node) + "$ ")
            return
        if name in {"sub", "sup"}:
            inner = TextWriter(self.page_url, self.images)
            inner.walk_children(node)
            text = clean(inner.text())
            # Word wraps whole formula pictures into <sub>; a picture gets no index sign.
            if text.startswith("[рисунок"):
                self.parts.append(f" {text} ")
            elif text:
                self.parts.append(("_" if name == "sub" else "^") + text)
            return
        block = name in BLOCKS
        if block:
            self.parts.append("\n")
        self.walk_children(node)
        self.parts.append("\n" if block else (" " if name == "td" else ""))

    def walk_children(self, node: Tag) -> None:
        for child in node.children:
            if isinstance(child, Tag | NavigableString):
                self.walk(child)

    def text(self) -> str:
        return "".join(self.parts)


def flatten(node: Tag, page_url: str, images: list[str]) -> str:
    writer = TextWriter(page_url, images)
    writer.walk(node)
    return clean(writer.text())


def info_rows(info: Tag | None) -> dict[str, Tag]:
    rows: dict[str, Tag] = {}
    for row in info.select("tr") if info else ():
        cells = row.find_all("td")
        if len(cells) >= 2:
            rows[clean(cells[0].get_text(" ")).rstrip(":").lower()] = cells[1]
    return rows


def kes_topics(cell: Tag | None) -> tuple[KesTopic, ...]:
    if cell is None:
        return ()
    entries = [clean(div.get_text(" ")) for div in cell.find_all("div")] or [
        clean(cell.get_text(" "))
    ]
    found = []
    for entry in entries:
        match = TOPIC.match(entry)
        if match:
            found.append(KesTopic(code=match.group(1), title=match.group(2)))
    return tuple(found)


def answer_kind(cell: Tag | None) -> AnswerKind:
    label = clean(cell.get_text(" ")).lower() if cell else ""
    return KINDS.get(label, AnswerKind.OTHER)


def options(block: Tag, page_url: str, images: list[str]) -> tuple[str, ...]:
    found = []
    for row in block.select("table.distractors-table tr"):
        cells = row.find_all("td")
        if cells:
            text = " ".join(flatten(cell, page_url, images) for cell in cells[1:])
            found.append(" ".join(text.split()))
    return tuple(text for text in found if text)


def answer_unit(block: Tag) -> str:
    field = block.select_one("td.varinats-block input[name=answer][type=text]")
    cell = field.find_parent("td") if field else None
    unit = cell.find_next_sibling("td") if cell else None
    return clean(unit.get_text(" ")) if unit else ""


def matching_keys(block: Tag) -> tuple[str, ...]:
    table = block.select_one("table.answer-table")
    first = table.find("tr") if table else None
    if first is None:
        return ()
    return tuple(clean(td.get_text(" ")) for td in first.find_all("td") if td.get_text(strip=True))


def parse_tasks(
    html: str, *, exam: Exam, page_url: str, task_url: Callable[[str], str]
) -> tuple[BankTask, ...]:
    """Tasks of one questions.php page. page_url resolves relative picture paths."""

    page = soup(html)
    tasks = []
    for block in page.select("div.qblock[id]"):
        task_id = str(block["id"])[1:]
        statement_cell = block.select_one("td.cell_0")
        if statement_cell is None:
            raise ParseError(f"task {task_id} has no statement cell")
        rows = info_rows(page.find(id="i" + task_id))
        hint = block.select_one(".hint")
        images: list[str] = []
        statement = flatten(statement_cell, page_url, images)
        tasks.append(
            BankTask(
                exam=exam,
                task_id=task_id,
                url=task_url(task_id),
                kes=kes_topics(rows.get("кэс")),
                answer_kind=answer_kind(rows.get("тип ответа")),
                instruction=clean(hint.get_text(" ")) if hint else "",
                statement=statement or "(условие только на рисунке)",
                options=options(block, page_url, images),
                matching_keys=matching_keys(block),
                answer_unit=answer_unit(block),
                images=tuple(images),
            )
        )
    return tuple(tasks)
