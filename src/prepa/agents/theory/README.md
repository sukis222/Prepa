# Составление теории

Реализован `TheoryAgent`; инструкции в `prompt.md` поставляются с Python-пакетом.
Агент получает уже найденные материалы, сам не вызывает поиск.

```python
from prepa.agents.theory import TheoryAgent

agent = TheoryAgent(llm, timeout_seconds=60, max_response_chars=200_000)
theory = await agent.generate(context)
# При наличии адресованных замечаний и неизменном контексте:
theory = await agent.generate(context, previous=theory, feedback=review)
```

Сигнатура: `async generate(context: GenerationContext, *, previous: Theory | None =
None, feedback: ReviewResult | RepairFeedback | None = None) -> Theory`.

Нужен подтверждённый GenerationContext. По каждой согласованной теме результат
содержит объяснения, формулы с условиями/единицами, разобранные примеры и source_ids
из библиотеки. Код проверяет версию, темы, покрытие и источники; физику и числа
проверяют reviewer/преподаватель. Ответ модели — JSON по Theory либо GenerationFailure;
runtime возвращает модель Theory или поднимает исключение.

previous и feedback передаются вместе, в той же подготовке/версии, с совпадающим
digest. Возвращается полный Theory, не diff. ContentValidationError содержит
отклонённый `.content` и кодовый `.feedback` для адресованного исправления.
Оркестратор ограничивает попытки и обновляет зависимые задания после новой теории.
Внешняя правка преподавателя требует новой версии и свежей генерации/проверки.

Клиент реализует StructuredLLM; сети и retries здесь нет. Сигнатуры, ошибки и
handoff: [контракт](../../../../docs/content-agents.md), предметная оценка:
[критерии качества](../../../../docs/content-quality.md).
