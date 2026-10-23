"""Verified official FIPI PDF alternative while the searchable bank is unavailable.

This is a narrow theory source, not a mirror of the task bank and not synthetic demo data.
"""

import asyncio
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import date

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

from prepa.agents.runtime import InsufficientMaterialsError
from prepa.schemas import GenerationFailure, LessonBrief, Material

from .fipi.client import USER_AGENT, TaskSourceError
from .models import Exam

NOTICE_PAGES = {
    "ege": "https://fipi.ru/ege/otkrytyy-bank-zadaniy-ege",
    "oge": "https://fipi.ru/oge/otkrytyy-bank-zadaniy-oge",
}
DATES = re.compile(r"с\s+(\d{2}\.\d{2}\.\d{4})\s+по\s+(\d{2}\.\d{2}\.\d{4})")
TITLE = "Равномерное прямолинейное движение"
ALIASES = {
    "равномерное прямолинейное движение",
    "равномерное движение",
}
MAX_PDF_BYTES = 8_000_000


@dataclass(frozen=True)
class MaintenanceNotice:
    start: date
    end: date
    page_url: str

    def active(self, today: date) -> bool:
        return self.start <= today <= self.end


def parse_maintenance(html: str, exam: Exam) -> MaintenanceNotice | None:
    text = " ".join(BeautifulSoup(html, "html.parser").get_text(" ").split())
    if "профилактические работы" not in text.lower() or "недоступны" not in text.lower():
        return None
    match = DATES.search(text)
    if not match:
        return None
    try:
        dates = [date(*reversed([int(v) for v in part.split(".")])) for part in match.groups()]
        start, end = dates
        if end < start:
            return None
    except ValueError:
        return None
    return MaintenanceNotice(start, end, NOTICE_PAGES[exam])


async def maintenance_for_exam(exam: Exam) -> MaintenanceNotice | None:
    """Read the current public announcement, without probing unavailable bank IPs."""
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(5), headers={"User-Agent": USER_AGENT}
        ) as client:
            result = await client.get(NOTICE_PAGES[exam])
            result.raise_for_status()
            if len(result.content) > 2_000_000:
                return None
            return parse_maintenance(result.text, exam)
    except httpx.HTTPError:
        return None  # Announcement failure must not prevent trying the bank itself.


@dataclass(frozen=True)
class OfficialDocument:
    url: str
    sha256: str
    page: int
    # Manually checked transcription of the equation in the original PDF. Automatic
    # PDF extraction reorders symbols; don't silently guess formulas from corrupted text.
    formula: str
    title: str = TITLE
    anchor: str = TITLE
    category: str = "uniform"


DOCUMENTS: dict[str, OfficialDocument] = {
    "ege": OfficialDocument(
        "https://doc.fipi.ru/navigator-podgotovki/navigator-ege/2026/fi-1-mehanika.pdf",
        "fd2eaee517a2e633d9a507c248c259858ea794e2ca25556f56828aa54e030378",
        1,
        "x(t) = x_0 + v_0x * t; v_x(t) = v_0x = const.",
    ),
    "oge": OfficialDocument(
        "https://doc.fipi.ru/navigator-podgotovki/navigator-oge/fi-9_1_mehanicheskie_javlenija.pdf",
        "ec7a75f868fb06cfe69f45aacfcbb79edcfe2250ddd78d4beb3bd10505a9e7c4",
        2,
        "x(t) = x_0 + v_x * t.",
    ),
}


THERMO_URL = (
    "https://doc.fipi.ru/navigator-podgotovki/navigator-ege/2026/fi-2-molekuljarnaja-fizika.pdf"
)
THERMO_SHA = "e237804e3651887821f60d734e81ce3ba93f9ecf5a4b2735a995c3076f4063cd"
THERMO_DOCUMENTS = (
    OfficialDocument(
        THERMO_URL,
        THERMO_SHA,
        1,
        "Модель идеального газа в термодинамике. "
        "Уравнение Менделеева — Клапейрона: p*V = (m/mu)*R*T = nu*R*T = N*k*T; "
        "p = rho*R*T/mu. Количество вещества nu = N/N_A = m/mu; "
        "N_A — число Авогадро, m — масса системы, mu — молярная масса вещества. "
        "Внутренняя энергия одноатомного идеального газа: "
        "U = (3/2)*nu*R*T = (3/2)*N*k*T = (3/2)*(m/mu)*R*T = nu*c_v*T = (3/2)*p*V.",
        title="Идеальный газ: уравнение состояния и внутренняя энергия",
        anchor="Модель идеального газа в термодинамике",
        category="ideal-gas",
    ),
    OfficialDocument(
        THERMO_URL,
        THERMO_SHA,
        2,
        "Изопроцессы в разреженном газе при постоянном количестве вещества nu: "
        "изотерма T=const, p*V=const; изохора V=const, p/T=const; "
        "изобара p=const, V/T=const. Объединённый газовый закон: p*V/T=const. "
        "Графическое представление изопроцессов на pV-, pT- и VT-диаграммах. "
        "Элементарная работа: A=p*DeltaV. Вычисление работы по графику процесса "
        "на pV-диаграмме. Первый закон термодинамики: "
        "Q_12 = DeltaU_12 + A_12 = (U_2-U_1)+A_12. "
        "Адиабата: Q_12=0, A_12=U_1-U_2. "
        "Принципы действия тепловых машин. КПД: "
        "eta=A_cycle/Q_hot=(Q_hot-abs(Q_cold))/Q_hot=1-abs(Q_cold)/Q_hot. "
        "Максимальное значение КПД, цикл Карно: "
        "eta_max=eta_Carnot=(T_hot-T_cold)/T_hot=1-T_cold/T_hot. "
        "Уравнение теплового баланса: Q_1+Q_2+Q_3+...=0.",
        title="Термодинамика: изопроцессы, циклы и тепловые машины",
        anchor="Изопроцессы",
        category="thermodynamics",
    ),
)


def documents_for_topic(exam: Exam, topic: str) -> tuple[OfficialDocument, ...]:
    key = " ".join(topic.lower().replace("ё", "е").split())
    if key in ALIASES or key == ("1.1.5" if exam == "ege" else "1.3"):
        return (DOCUMENTS[exam],)
    # A free-form request may include the exam part and plotting preferences. Match
    # the subject explicitly: generic "graphs/cycles" are not necessarily thermodynamics.
    if (
        exam == "ege"
        and "квант" not in key
        and (
            "термодинамик" in key
            or "изопроцесс" in key
            or "цикл карно" in key
            or "тепловые машины" in key
        )
    ):
        return THERMO_DOCUMENTS
    return ()


def supported_topic(exam: Exam, topic: str) -> bool:
    return bool(documents_for_topic(exam, topic))


def extract_verified(data: bytes, document: OfficialDocument) -> str:
    if len(data) > MAX_PDF_BYTES or hashlib.sha256(data).hexdigest() != document.sha256:
        raise TaskSourceError("Official FIPI document changed; verification required")
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        text = reader.pages[document.page - 1].extract_text()
    except Exception:
        raise TaskSourceError("Official FIPI PDF cannot be read") from None
    start = text.find(document.anchor)
    if start < 0:
        raise TaskSourceError("Expected topic missing from official FIPI PDF")
    # Exclude surrounding graph exercises, other topics and footnotes. Raw PDF math
    # is not sent to the model: it is replaced with the checked transcription above.
    text = text[start:]
    if document.category == "uniform" and document.page == 2:
        text = text.split("Графики зависимости", 1)[0]
    elif document.category == "uniform":
        text = text.split("1 На сайте", 1)[0]
    if len(text) > (2000 if document.category == "uniform" else 6000) or len(text) < len(
        document.anchor
    ):
        raise TaskSourceError("Unexpected official FIPI PDF layout")
    return (
        "Официальный навигатор самостоятельной подготовки ФИПИ-2026; "
        "это резервный теоретический источник, а не поиск задач по всему банку.\n"
        f"Раздел: {document.title}. Страница PDF: {document.page}.\n"
        "Проверенная текстовая расшифровка формул с указанной страницы "
        "(порядок символов при автоматическом извлечении PDF нарушается):\n"
        + document.formula
        + "\nЭто теоретический фрагмент. Готовые условия, численные данные и графики "
        "конкретных заданий банка в нём не извлекались. Новые примеры и задачи по этим "
        "законам — авторская адаптация. Для задачи с графиком нужна полная информация: "
        "координаты/уравнения участков и направление прохождения процесса."
    )


class OfficialNavigatorMaterials:
    """Download a real, version-verified theoretical fragment, only for supported topics."""

    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        self.http = http

    async def materials(self, brief: LessonBrief) -> tuple[Material, ...]:
        missing = tuple(t for t in brief.topics if not supported_topic(brief.exam, t))
        if missing:
            raise InsufficientMaterialsError(
                GenerationFailure(
                    status="insufficient_material",
                    missing_topics=missing,
                    reason="Банк ФИПИ недоступен. Резервный навигатор поддерживает "
                    "равномерное прямолинейное движение (ЕГЭ 1.1.5, ОГЭ 1.3) "
                    "и термодинамику ЕГЭ: идеальный газ, изопроцессы и тепловые циклы.",
                )
            )
        if self.http is not None:
            return await self._read(self.http, brief)
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15, connect=5), headers={"User-Agent": USER_AGENT}
        ) as client:
            return await self._read(client, brief)

    async def _read(self, client: httpx.AsyncClient, brief: LessonBrief) -> tuple[Material, ...]:
        groups: dict[OfficialDocument, list[str]] = {}
        for topic in brief.topics:
            for document in documents_for_topic(brief.exam, topic):
                groups.setdefault(document, []).append(topic)
        downloaded: dict[str, bytes] = {}
        materials: list[Material] = []
        for document, topics in groups.items():
            if document.url not in downloaded:
                downloaded[document.url] = await self._download(client, document.url)
            content = await asyncio.to_thread(extract_verified, downloaded[document.url], document)
            materials.append(
                Material(
                    material_id=f"fipi-navigator-{brief.exam}-2026-{document.category}",
                    title=f"ФИПИ-2026, навигатор {brief.exam.upper()}: "
                    f"{document.title}, с. {document.page}",
                    source=f"{document.url}#page={document.page}",
                    exam=brief.exam,
                    topics=tuple(topics),
                    content=content,
                )
            )
        return tuple(materials)

    @staticmethod
    async def _download(client: httpx.AsyncClient, url: str) -> bytes:
        try:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                # No redirects to arbitrary hosts, credentials, local files, or TLS bypass.
                if response.headers.get("content-type", "").split(";")[0] != "application/pdf":
                    raise TaskSourceError("Official FIPI endpoint did not return PDF")
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > MAX_PDF_BYTES:
                        raise TaskSourceError("Official FIPI PDF exceeds size limit")
                return bytes(chunks)
        except httpx.HTTPError:
            raise TaskSourceError("Official FIPI document unavailable") from None
