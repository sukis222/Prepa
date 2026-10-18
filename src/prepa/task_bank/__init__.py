"""Search of exam problems by topic in the FIPI open bank."""

from .fipi.client import FipiClient, TaskSourceError
from .fipi.parser import ParseError
from .material import to_material
from .models import AnswerKind, BankTask, KesTopic, SearchResult
from .search import TaskSearch, UnknownTopicError, match_topics
from .text import format_result, format_task

__all__ = [
    "AnswerKind",
    "BankTask",
    "FipiClient",
    "KesTopic",
    "ParseError",
    "SearchResult",
    "TaskSearch",
    "TaskSourceError",
    "UnknownTopicError",
    "format_result",
    "format_task",
    "match_topics",
    "to_material",
]
