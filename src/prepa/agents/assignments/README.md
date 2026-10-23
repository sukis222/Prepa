# Задания на урок и домашнее задание

Реализован AssignmentsAgent; инструкции в `prompt.md` поставляются с пакетом. Один
агент готовит общую практику и отдельное обоснованное ДЗ по подтверждённому контексту,
уже найденной библиотеке и подготовленной теории.

```python
from prepa.agents.assignments import AssignmentsAgent

agent = AssignmentsAgent(llm, timeout_seconds=120, max_response_chars=200_000)
assignments = await agent.generate(context, theory)
# Только если review адресует замечания assignments:
assignments = await agent.generate(
    context,
    theory,
    previous=assignments,
    feedback=review,
)
```

Сигнатура: `async generate(context: GenerationContext, theory: Theory, *, previous:
AssignmentSet | None = None, feedback: ReviewResult | RepairFeedback | None = None)
-> AssignmentSet`.

Перед LLM агент проверяет theory локальными правилами. Модель возвращает AssignmentSet
либо GenerationFailure. Нужны ровно lesson_task_count общих задач и по
homework_task_count каждому ученику. При нулевом ДЗ обязательно `homeworks: []`.
ID задач уникальны во всём комплекте; время ДЗ ограничено отдельно для каждого ученика.
Условия, ответы, решения и подсказки разнесены; rationale объясняет персонализацию.

Код проверяет темы, ссылки, объём, время и получателей. Физика, уровень, разумность
времени и отсутствие ответа внутри условия требуют reviewer/преподавателя. Ученический
документ принимает `package.for_student(id)`, не полный AssignmentSet.

Исправление передаёт previous и feedback вместе, с тем же контекстом/версией и
совпадающим digest; нужны адресованные замечания. Возвращается полный комплект,
промпт требует сохранять неизменённые ID. ContentValidationError содержит `.content`
и `.feedback`: если отклонена входная теория, направить их TheoryAgent. После правок
проверить весь комплект заново. Поиск, сохранение и предел retries задаёт вызывающий
код. Подробнее: [контракт](../../../../docs/content-agents.md) и
[качество](../../../../docs/content-quality.md).
