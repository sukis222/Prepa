"""Plain-text rendering of found tasks for a teacher (Telegram message, console)."""

from .models import AnswerKind, BankTask, SearchResult

KIND_LABELS = {
    AnswerKind.SHORT: "краткий ответ",
    AnswerKind.SINGLE_CHOICE: "выбор одного ответа",
    AnswerKind.MULTIPLE_CHOICE: "выбор нескольких ответов",
    AnswerKind.MATCHING: "установление соответствия",
    AnswerKind.EXTENDED: "развёрнутый ответ",
    AnswerKind.FILL_TERMS: "расстановка терминов",
    AnswerKind.OTHER: "другой тип ответа",
}


def format_task(task: BankTask, number: int | None = None) -> str:
    title = f"Задача {number}" if number is not None else "Задача"
    kes = ", ".join(topic.code for topic in task.kes) or "—"
    lines = [
        f"{title} · {task.exam.upper()} · КЭС {kes} · {KIND_LABELS[task.answer_kind]}",
        task.statement,
    ]
    lines.extend(task.options)
    if task.matching_keys:
        lines.append("Ответ: " + " ".join(f"{key} —" for key in task.matching_keys))
    elif task.answer_unit:
        lines.append(f"Ответ: ____ {task.answer_unit}")
    lines.extend(f"[рисунок {i}] {url}" for i, url in enumerate(task.images, start=1))
    lines.append(f"Источник: открытый банк ФИПИ, задание {task.task_id} — {task.url}")
    return "\n".join(lines)


def format_result(result: SearchResult) -> str:
    topics = "; ".join(f"{topic.code} {topic.title}" for topic in result.topics)
    header = (
        f"{result.exam.upper()}: {topics}\n"
        f"В банке по теме: {result.total_available}, показано: {len(result.tasks)}. "
        "Ответы и решения банк не публикует."
    )
    tasks = (format_task(task, number) for number, task in enumerate(result.tasks, start=1))
    return "\n\n".join([header, *tasks])
