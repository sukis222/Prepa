"""Bounded anonymous Reshai source access: original conditions, never answer/solution text."""

import asyncio
import base64
import hashlib
import io
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from PIL import Image, UnidentifiedImageError

from prepa.schemas import LessonBrief, SourceImage, SourceTask
from prepa.schemas.source import source_task_digest
from prepa.task_bank.fipi.parser import flatten

ORIGIN = "https://reshai.online"
BASE = "/ege/subjects/physics/tasks/"
TOPICS = {
    "physical-basics-and-measurements": ("измерени", "физические величин", "погрешност"),
    "kinematics": ("кинемат", "равномерн", "равноускор", "движение по окружности"),
    "dynamics-and-gravitation": (
        "динамик",
        "гравитац",
        "силы",
        "ньютон",
        "статик",
        "равновес",
        "пружин",
    ),
    "energy-and-momentum": (
        "энерг",
        "сохранения",
        "импульс",
        "работа",
        "мощност",
        "кинетическ",
        "потенциальн",
    ),
    "fluids-and-pressure": (
        "давление и плавание",
        "давление жидк",
        "гидростат",
        "архимед",
        "плавание тел",
    ),
    "molecular-physics": ("молекуляр", "мкт", "идеальный газ", "температур"),
    "thermodynamics": ("термодинами", "изопроцесс", "первый закон", "внутренняя энергия"),
    "phase-transitions-and-heat-engines": (
        "теплов",
        "кпд",
        "карно",
        "фазов",
        "плавление",
        "теплообмен",
        "теплопередач",
        "испарени",
        "конденсац",
    ),
    "electric-circuits": ("электрический ток", "цепи", "закон ома", "постоянный ток"),
    "electrostatics-and-capacitors": (
        "электростат",
        "конденсатор",
        "кулон",
        "электрическое поле",
        "заряд",
    ),
    "magnetic-field-and-induction": ("магнит", "магнетизм", "индукц"),
    "oscillations-and-waves": ("колебан", "волн", "звук"),
    "geometrical-optics": ("оптик", "линз", "преломлен"),
    "quantum-and-nuclear-physics": ("квант", "ядер", "атом", "фотоэффект"),
}
CYCLE = re.compile(r"цикл|циклическ", re.I)
CODE = re.compile(r"^[A-F0-9]{6}$")


class ReshaiError(ValueError):
    """Static source failure, no external body or personal data in the message."""


@dataclass(frozen=True)
class ListingTask:
    id: str
    preview: str
    extended: bool
    number: int


def resolve_topics(topic: str) -> tuple[str, ...]:
    text = topic.casefold()
    if "внутренняя энерг" in text:
        return ("thermodynamics",)
    if "молекул" in text and "энерг" in text:
        return ("molecular-physics",)
    if "цикл" in text:
        return ("thermodynamics", "phase-transitions-and-heat-engines")
    slugs = tuple(
        slug
        for slug, words in TOPICS.items()
        if any(re.search(r"(?<!\w)" + re.escape(w), text) for w in words)
    )
    if re.search(r"лоренц|фараде|ленца|сил\w*\s+ампер", text):
        slugs = tuple(
            slug
            for slug in slugs
            if slug != "dynamics-and-gravitation"
            or re.search(r"динамик|ньютон|гравитац|равновес|пружин|статик", text)
        )
        slugs = tuple(dict.fromkeys((*slugs, "magnetic-field-and-induction")))
    if not slugs:
        raise ReshaiError("Unknown Reshai topic")
    return slugs


def request_part(description: str) -> int | None:
    text = description.casefold()
    if re.search(r"перв\w*\s+и\s+втор\w*\s+част|част\w*\s*1\s*и\s*2", text):
        return None
    parts = set()
    for number, word in ((1, "перв"), (2, "втор")):
        if re.search(
            rf"(?:{number}[- ]*(?:я|ая|ой|й)?\s*част|{word}\w*\s+част|част\w*\s*{number})", text
        ):
            parts.add(number)
    return parts.pop() if len(parts) == 1 else None


def request_numbers(description: str) -> set[int]:
    text = description.casefold()
    matches = re.finditer(r"(?:№|номер(?:а|ов)?|задани[еяй])\s*(\d+(?:\s*[,и]\s*\d+)*)", text)
    return {
        int(number)
        for match in matches
        if not re.match(r"[- ]*(?:я|ая|ой|й)?\s*част", text[match.end() :])
        for number in re.findall(r"\d+", match[1])
    }


def parse_listing(html: str) -> tuple[tuple[ListingTask, ...], int]:
    soup = BeautifulSoup(html, "html.parser")
    tasks = []
    for card in soup.select("article.tk"):
        code = card.select_one(".tk-code")
        preview = card.select_one(".tk-text")
        number = card.select_one(".tk-top a[href*='/numbers/']")
        if code is None or preview is None or number is None:
            continue
        id = code.get_text(" ", strip=True).split()[-1]
        if not CODE.fullmatch(id):
            continue
        for watermark in preview.select(".wmk"):
            watermark.decompose()
        match = re.search(r"\d+", number.get_text())
        if match:
            tasks.append(
                ListingTask(
                    id,
                    preview.get_text(" ", strip=True),
                    "Развёрнутое решение" in card.get_text(" ", strip=True),
                    int(match[0]),
                )
            )
    if not tasks:
        raise ReshaiError("Reshai listing structure changed")
    pages = [
        int(m[1])
        for a in soup.select("a[href]")
        if (m := re.search(r"[?&]page=(\d+)(?:$|&)", str(a["href"])))
    ]
    return tuple(tasks), max(pages, default=1)


def original_condition(html: str, url: str) -> tuple[str, tuple[str, ...]]:
    soup = BeautifulSoup(html, "html.parser")
    original = soup.select_one("details.origin-task .o-body")
    if original is None:
        raise ReshaiError("Original condition missing")
    # The source-only disclosure contains the bank HTML, not site hints/answers/solutions.
    for hidden in original.select("script,style,.wmk"):
        hidden.decompose()
    # Layout tables need a structured renderer; do not flatten away row/column meaning.
    if any(
        sum(
            bool(cell.get_text(strip=True) or cell.find("img"))
            for cell in row.find_all(["td", "th"], recursive=False)
        )
        > 1
        for row in original.select("tr")
    ):
        raise ReshaiError("Original table layout unsupported")
    for node in original.select("sub,sup"):
        value = node.get_text("", strip=True)
        if not re.fullmatch(r"[\w+−=, .-]{1,30}", value):
            raise ReshaiError("Original index unsupported")
        sign = "_" if node.name == "sub" else "^"
        node.replace_with(NavigableString("${}" + sign + "{" + value + "}$"))
    images: list[str] = []
    text = flatten(original, url, images)
    if not text or len(text) > 20_000:
        raise ReshaiError("Invalid original condition")
    return text, tuple(dict.fromkeys(images))


def image_snapshot(content: bytes) -> SourceImage:
    if not content or len(content) > 3_000_000:
        raise ReshaiError("Source image too large")
    try:
        with Image.open(io.BytesIO(content)) as image:
            if (
                image.format not in ("PNG", "GIF", "JPEG")
                or image.width * image.height > 20_000_000
            ):
                raise ReshaiError("Unsupported source image")
            if getattr(image, "n_frames", 1) != 1:
                raise ReshaiError("Animated source figure unsupported")
            image.load()
            converted = image.convert("RGBA")
            clean = Image.new("RGB", converted.size, "white")
            clean.paste(converted, mask=converted.getchannel("A"))
            output = io.BytesIO()
            clean.save(output, format="PNG")
            data = output.getvalue()
            width, height = clean.size
    except (OSError, ValueError, Image.DecompressionBombError, UnidentifiedImageError):
        raise ReshaiError("Invalid source image") from None
    if len(data) > 3_000_000:
        raise ReshaiError("Source image too large")
    return SourceImage(
        data_base64=base64.b64encode(data).decode(),
        sha256=hashlib.sha256(data).hexdigest(),
        width=width,
        height=height,
    )


class ReshaiSource:
    """Bounded search: 70 conditions, or 120 when illustrations are requested."""

    def __init__(
        self,
        *,
        cache_dir: Path = Path("output/source-cache/reshai"),
        http: httpx.AsyncClient | None = None,
        cache_seconds: int = 86400,
        request_interval: float = 0.12,
    ) -> None:
        self.cache_dir, self.http = Path(cache_dir), http
        self.cache_seconds, self.interval = cache_seconds, request_interval
        self._gate = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(3)
        self._last_request = 0.0
        self._calls = 0

    async def _fetch(self, path: str, *, image: bool = False) -> bytes:
        url = urljoin(ORIGIN, path)
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "reshai.online"
            or not (parsed.path.startswith(BASE) or parsed.path.startswith("/media/task/"))
        ):
            raise ReshaiError("Untrusted Reshai URL")
        key = hashlib.sha256(url.encode()).hexdigest()
        file = self.cache_dir / (key + ".bin")
        metadata = self.cache_dir / (key + ".json")
        maximum = 3_000_000 if image else 2_000_000
        try:
            info = json.loads(metadata.read_text())
            data = file.read_bytes()
            if (
                time.time() - info["stored_at"] < self.cache_seconds
                and len(data) <= maximum
                and hashlib.sha256(data).hexdigest() == info["sha256"]
            ):
                return data
        except (OSError, ValueError, KeyError, TypeError):
            pass
        async with self._semaphore:
            async with self._gate:
                if self._calls >= 220:
                    raise ReshaiError("Reshai request limit reached")
                await asyncio.sleep(
                    max(0.0, self.interval - (time.monotonic() - self._last_request))
                )
                self._last_request = time.monotonic()
                self._calls += 1
            if self.http is None:
                raise ReshaiError("Source client missing")
            try:
                async with self.http.stream(
                    "GET", url, timeout=8, follow_redirects=False
                ) as response:
                    if response.status_code != 200:
                        raise ReshaiError("Reshai unavailable")
                    mime = response.headers.get("content-type", "").casefold()
                    if (image and not mime.startswith("image/")) or (
                        not image and "text/html" not in mime
                    ):
                        raise ReshaiError("Unexpected source content")
                    data = b""
                    async for chunk in response.aiter_bytes():
                        data += chunk
                        if len(data) > maximum:
                            raise ReshaiError("Source response too large")
            except httpx.HTTPError:
                raise ReshaiError("Reshai unavailable") from None
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
            metadata.write_text(
                json.dumps({"stored_at": time.time(), "sha256": hashlib.sha256(data).hexdigest()})
            )
            return data

    async def _task(self, item: ListingTask) -> SourceTask:
        url = ORIGIN + BASE + item.id
        html = (await self._fetch(url)).decode("utf-8")
        text, urls = original_condition(html, url)
        if len(urls) > 4:
            raise ReshaiError("Too many original figures")
        images = tuple(await asyncio.gather(*(self._image(url) for url in urls)))
        math: tuple[str, ...] = ()
        return SourceTask(
            id="reshai-" + item.id,
            statement_exact=text,
            statement_math_exact=math,
            source_url=url,
            images=images,
            exam_part=2 if item.extended else 1,
            exam_number=item.number,
            sha256=source_task_digest(text, math),
        )

    async def _image(self, url: str) -> SourceImage:
        return await asyncio.to_thread(image_snapshot, await self._fetch(url, image=True))

    async def candidates(self, brief: LessonBrief) -> list[tuple[SourceTask, tuple[str, ...]]]:
        if brief.exam != "ege":
            raise ReshaiError("Reshai source currently supports EGE physics only")
        if self.http is None:
            async with httpx.AsyncClient(
                headers={"User-Agent": "Prepa/0.1 educational worksheet"}
            ) as http:
                return await ReshaiSource(
                    cache_dir=self.cache_dir,
                    http=http,
                    cache_seconds=self.cache_seconds,
                    request_interval=self.interval,
                ).candidates(brief)
        async with asyncio.timeout(35):
            return await self._candidates(brief)

    async def _candidates(self, brief: LessonBrief) -> list[tuple[SourceTask, tuple[str, ...]]]:
        grouped: dict[str, tuple[ListingTask, set[str]]] = {}
        description = "; ".join(brief.topics) + " " + (brief.teacher_notes or "")
        cycle_query = "цикл" in description.casefold()
        requested_part = request_part(description)
        requested_numbers = request_numbers(description)
        require_images = bool(re.search(r"с\s+(?:график|рисунк|картинк)", description, re.I))
        detail_limit = 120 if require_images else 70
        listing_budget = 16 if cycle_query else 12
        target = max(20, min(brief.lesson_task_count + 10, 60))
        for topic in brief.topics:
            matching: dict[str, ListingTask] = {}
            for slug in resolve_topics(description if len(brief.topics) == 1 else topic):
                page = 1
                pages = 1
                while page <= pages and listing_budget > 0:
                    path = BASE + "physics." + slug + (f"?page={page}" if page > 1 else "")
                    listing_budget -= 1
                    try:
                        items, pages = parse_listing((await self._fetch(path)).decode("utf-8"))
                    except ReshaiError:
                        if page == 1:
                            raise
                        # An empty/outdated later page must not erase verified earlier candidates.
                        break
                    for item in items:
                        if requested_part and (2 if item.extended else 1) != requested_part:
                            continue
                        if requested_numbers and item.number not in requested_numbers:
                            continue
                        matching[item.id] = item
                    page += 1
            ranked = list(matching.values())
            if "цикл" in topic.casefold():
                # Preview is a ranking hint only: missing/truncated words never exclude a task.
                ranked.sort(key=lambda item: not bool(CYCLE.search(item.preview)))
            elif not requested_numbers:
                # Sample across task formats/parts instead of taking only the first easy pages.
                buckets: dict[tuple[bool, int], list[ListingTask]] = {}
                for item in ranked:
                    buckets.setdefault((item.extended, item.number), []).append(item)
                ranked = []
                while any(buckets.values()):
                    for bucket in buckets.values():
                        if bucket:
                            ranked.append(bucket.pop(0))
            if re.search(r"ампер|лоренц", description, re.I):
                ranked.sort(
                    key=lambda item: (
                        not bool(re.search(r"ампер|лоренц|сил[аы]", item.preview, re.I))
                    )
                )
            for item in ranked[:detail_limit]:
                if item.id not in grouped:
                    grouped[item.id] = (item, set())
                grouped[item.id][1].add(topic)
        # Fetch small batches; skip broken/unsupported originals, never substitute invented data.
        found = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        grouped_items = list(grouped.values())
        if cycle_query:
            grouped_items.sort(key=lambda pair: not bool(CYCLE.search(pair[0].preview)))
        grouped_items = grouped_items[:detail_limit]
        for start in range(0, len(grouped_items), 3):
            chunk = grouped_items[start : start + 3]
            results = await asyncio.gather(
                *(self._task(item) for item, _ in chunk), return_exceptions=True
            )
            for (_item, topics), result in zip(chunk, results, strict=True):
                if isinstance(result, SourceTask):
                    if require_images and not result.images:
                        continue
                    # Recheck the cycle constraint against the complete original.
                    covered = tuple(
                        t for t in topics if not cycle_query or CYCLE.search(result.statement_exact)
                    )
                    digest = (result.sha256, tuple(image.sha256 for image in result.images))
                    if covered and digest not in seen:
                        seen.add(digest)
                        found.append((result, covered))
            if len(found) >= target and set(brief.topics) <= {t for _, ts in found for t in ts}:
                break
        if not found:
            raise ReshaiError("No complete matching source conditions")
        return found
