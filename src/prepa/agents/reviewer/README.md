# Проверка материалов

Реализован ReviewerAgent; независимые инструкции находятся в `prompt.md`.

```python
from prepa.agents.reviewer import ReviewerAgent

review = await ReviewerAgent(llm).review(context, theory, assignments)
theory_issues = review.for_author("theory")
assignment_issues = review.for_author("assignments")
```

Сигнатура: `async review(context: GenerationContext, theory: Theory, assignments:
AssignmentSet) -> ReviewResult`. Конструктор принимает StructuredLLM и параметры
`timeout_seconds=120`, `max_response_chars=200_000`.

Модель получает подтверждённый контекст, theory, assignments и локальные
contract_issues; возвращает **ReviewReport**, не ReviewResult. Допустим также явный
GenerationFailure, который превращается в InsufficientMaterialsError без одобрения.
Runtime проверяет версию/адреса, сохраняет локальные ошибки, вычисляет digest и
создаёт ReviewResult. approved в JSON запрещён: это вычисляемая Python property.
Error блокирует комплект, warning не блокирует.

Замечание содержит author (`theory`/`assignments`), существующий target_id этого
автора, severity, category, конкретные message и suggestion. Категории: physics,
units, answer, topic, level, source, coverage, timing. Для общей проблемы выбирается
существующий раздел/задача; отдельных адресатов orchestrator/documents нет.

После изменения данных review выполняется снова: digest связывает его со всем
контекстом и точным содержанием. Проверяющий не переписывает содержание и не запускает
исправления; маршрутизацию и предел попыток реализует оркестратор. Модель должна
независимо пересчитать физику, но одобрение не заменяет утверждение преподавателя.
Полный [контракт](../../../../docs/content-agents.md), числа и
[rubric](../../../../docs/content-quality.md).
