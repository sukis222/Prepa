"""HTTP access to the FIPI open bank. Polite by default: sequential, delayed, cached topics."""

import asyncio
import ssl
from collections.abc import Iterable
from dataclasses import dataclass
from importlib.resources import files
from urllib.parse import urlencode

import certifi
import httpx

from prepa.task_bank.models import AnswerKind, BankTask, Exam, KesTopic

from .parser import parse_tasks, parse_topics, parse_total


@dataclass(frozen=True)
class Bank:
    host: str
    project: str

    @property
    def base(self) -> str:
        return f"https://{self.host}/bank/"

    def task_url(self, task_id: str) -> str:
        query = urlencode({"search": 1, "proj": self.project, "qid": task_id})
        return f"{self.base}questions.php?{query}"


PHYSICS = {
    "ege": Bank("ege.fipi.ru", "BA1F39653304A5B041B656915DC36B38"),
    "oge": Bank("oge.fipi.ru", "B24AFED7DE6AB5BC461219556CCA4F9B"),
}
KIND_CODES = {
    AnswerKind.SHORT: "ILI_STD_SHORT",
    AnswerKind.SINGLE_CHOICE: "ILI_STD_SELECTONE",
    AnswerKind.MULTIPLE_CHOICE: "ILI_STD_SELECTN",
    AnswerKind.MATCHING: "ILI_EXT_ACCORD",
    AnswerKind.EXTENDED: "ILI_STD_FULL",
    AnswerKind.FILL_TERMS: "ILI_EXT_TXTPARTCHOICE",
}
MAX_PAGE_SIZE = 50
USER_AGENT = "Prepa/0.1 (educational tutoring assistant; +https://github.com/sukis222/Prepa)"


class TaskSourceError(RuntimeError):
    """The bank could not be reached or answered with an unexpected page."""


@dataclass(frozen=True)
class Page:
    total: int
    tasks: tuple[BankTask, ...]


def ssl_context() -> ssl.SSLContext:
    """Public CAs plus the GlobalSign intermediate that fipi.ru servers do not send."""

    context = ssl.create_default_context(cafile=certifi.where())
    pem = files(__package__).joinpath("globalsign-gcc-r3-dv-tls-ca-2020.pem")
    context.load_verify_locations(cadata=pem.read_text(encoding="ascii"))
    return context


class FipiClient:
    def __init__(
        self,
        http: httpx.AsyncClient | None = None,
        *,
        banks: dict[str, Bank] | None = None,
        delay_seconds: float = 0.5,
    ) -> None:
        self.http = http or httpx.AsyncClient(
            verify=ssl_context(),
            timeout=httpx.Timeout(30),
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        self.banks = banks or PHYSICS
        self.delay_seconds = delay_seconds
        self.lock = asyncio.Lock()
        self.topic_cache: dict[str, tuple[KesTopic, ...]] = {}

    async def __aenter__(self) -> "FipiClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self.http.aclose()

    def bank(self, exam: Exam) -> Bank:
        return self.banks[exam]

    async def fetch(self, method: str, url: str, data: dict[str, str] | None = None) -> str:
        async with self.lock:
            try:
                response = await self.http.request(method, url, data=data)
                response.raise_for_status()
            except httpx.HTTPError as error:
                raise TaskSourceError(f"FIPI bank request failed: {error}") from error
            finally:
                await asyncio.sleep(self.delay_seconds)
        if response.charset_encoding is None:
            response.encoding = "cp1251"
        return response.text

    async def topics(self, exam: Exam) -> tuple[KesTopic, ...]:
        if exam not in self.topic_cache:
            bank = self.bank(exam)
            html = await self.fetch("GET", f"{bank.base}index.php?proj={bank.project}")
            self.topic_cache[exam] = parse_topics(html)
        return self.topic_cache[exam]

    async def page(
        self,
        exam: Exam,
        codes: Iterable[str],
        *,
        kinds: Iterable[AnswerKind] = (),
        page: int = 0,
        page_size: int = MAX_PAGE_SIZE,
    ) -> Page:
        """One page of tasks for КЭС codes; page is zero-based, parents include children."""

        if not 1 <= page_size <= MAX_PAGE_SIZE or page < 0:
            raise ValueError("page must be >= 0 and page_size within 1..50")
        bank = self.bank(exam)
        url = f"{bank.base}questions.php"
        form = {
            "search": "1",
            "proj": bank.project,
            "theme": ",".join(codes),
            "qkind": ",".join(KIND_CODES[kind] for kind in kinds if kind in KIND_CODES),
            "pagesize": str(page_size),
            "page": str(page),
        }
        html = await self.fetch("POST", url, data=form)
        return Page(
            total=parse_total(html),
            tasks=parse_tasks(html, exam=exam, page_url=url, task_url=bank.task_url),
        )
