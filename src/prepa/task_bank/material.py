"""Adapter from found bank tasks to the shared Material contract used by content agents."""

from collections.abc import Sequence

from prepa.schemas import Material

from .models import BankTask
from .text import format_task


def to_material(task: BankTask, topics: Sequence[str]) -> Material:
    """topics are the LessonBrief topics this task was searched for, not КЭС titles.

    GenerationContext requires materials to cover brief topics by exact string, and only
    the caller knows which brief topic led to the search.
    """

    return Material(
        material_id=f"fipi-{task.exam}-{task.task_id}",
        title=f"Открытый банк ФИПИ ({task.exam.upper()}), задание {task.task_id}",
        source=task.url,
        exam=task.exam,
        topics=tuple(topics),
        content=format_task(task),
    )
