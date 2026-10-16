# Содержание занятия: контракт и интеграция

Слой участника 4 превращает подтверждённый запрос и переданную библиотеку в теорию,
общую практику, индивидуальное ДЗ и адресованные замечания. Это реализованный Python
API, независимый от Telegram, БД, OpenRouter и LaTeX. Сетевой клиент, поиск материалов,
диалог, ограниченный цикл исправлений, сохранение и документы подключают другие участники.

## Проверка без внешних сервисов

Требуется Python 3.12 или новее. Из корня репозитория:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python examples/content_agents.py --output-dir output/content-demo
python -m pytest
python -m ruff check .
python -m mypy src/prepa
python -m build
```

Demo воспроизводит записанные JSON-ответы и создаёт `teacher.json`, `student-a.json`,
`student-b.json`. Это не вызов живой LLM и не сборка PDF. Данные описаны в
[demo](../data/demo/README.md), предметная оценка — в [критериях качества](content-quality.md).

## Public API

```python
from prepa.agents.assignments import AssignmentsAgent
from prepa.agents.contracts import StructuredLLM
from prepa.agents.reviewer import ReviewerAgent
from prepa.agents.runtime import (
    AgentResponseError,
    ContentValidationError,
    InsufficientMaterialsError,
)
from prepa.agents.theory import TheoryAgent
from prepa.schemas import (
    AssignmentSet,
    GenerationContext,
    GenerationFailure,
    LessonPackage,
    RepairFeedback,
    ReviewReport,
    ReviewResult,
    Theory,
)
```

Каждый агент имеет конструктор `(llm: StructuredLLM, *, timeout_seconds: float = 60,
max_response_chars: int = 200_000)`. Таймаут должен быть конечным и положительным,
предел ответа — положительным целым числом. Точные асинхронные сигнатуры:

```python
class TheoryAgent:
    async def generate(
        self,
        context: GenerationContext,
        *,
        previous: Theory | None = None,
        feedback: ReviewResult | RepairFeedback | None = None,
    ) -> Theory: ...


class AssignmentsAgent:
    async def generate(
        self,
        context: GenerationContext,
        theory: Theory,
        *,
        previous: AssignmentSet | None = None,
        feedback: ReviewResult | RepairFeedback | None = None,
    ) -> AssignmentSet: ...


class ReviewerAgent:
    async def review(
        self,
        context: GenerationContext,
        theory: Theory,
        assignments: AssignmentSet,
    ) -> ReviewResult: ...
```

Пример последовательности в существующем async-обработчике:

```python
context = GenerationContext.model_validate(context_json)
theory = await TheoryAgent(llm).generate(context)
assignments = await AssignmentsAgent(llm).generate(context, theory)
review = await ReviewerAgent(llm).review(context, theory, assignments)
if review.approved:
    package = LessonPackage(
        context=context,
        theory=theory,
        assignments=assignments,
        review=review,
    )
    student_input = package.for_student(context.brief.student_ids[0])
    # Передать student_input в documents; package оставить преподавателю.
else:
    # Оркестратор адресует review.for_author(...) и ограничивает повторы.
    ...
```

`llm` и `context_json` поставляет вызывающий код. Исполняемый пример без внешних
зависимостей сервиса находится в `examples/content_agents.py`.

## Граница LLM-клиента

`StructuredLLM` — структурный `Protocol`, для которого нужен один метод:

```python
from typing import Any


async def generate(
    self,
    *,
    system_prompt: str,
    user_prompt: str,
    response_schema: dict[str, Any],
) -> str | dict[str, Any]: ...
```

Агент читает свой `prompt.md` из установленного пакета, сериализует вход в JSON и
передаёт схему `anyOf` успешного результата (`Theory`, `AssignmentSet`, `ReviewReport`)
и `GenerationFailure`, включая `$defs`. Верхний `title` сохраняет имя успешной модели.
Клиент должен поддержать эту схему целиком либо адаптировать её к API провайдера;
локальная валидация всё равно обязательна. Возвращается JSON-объект либо строка с
JSON-объектом. Markdown, списки, обёртки провайдера и текст до/после JSON не подходят.

Участник 1 реализует адаптер в `llm/`: конфигурацию, секреты, выбор модели, провайдера
и нормализацию ответа. В агентском слое нет HTTP-вызовов, доступа к ключам, поиска,
автоматических повторов, резервных моделей или сохранения состояния. До первого вызова
проверяется `context.brief.confirmed`. Таймаут ограничивает один вызов через
`asyncio.wait_for`; отмена и ошибки адаптера передаются вызывающему коду без retries.
`max_response_chars` ограничивает полученный текст, в том числе JSON-сериализацию dict;
лимиты транспорта/токенов до получения ответа задаёт адаптер.

Если библиотека формально покрывает темы, но в ней недостаточно содержания, модель
может вернуть явный отказ вместо выдуманного материала:

```json
{
  "status": "insufficient_material",
  "missing_topics": ["Равномерное прямолинейное движение"],
  "reason": "В переданном фрагменте нет данных для решения выбранной задачи."
}
```

Runtime поднимает `InsufficientMaterialsError`, в `.failure` находится
`GenerationFailure`. Это не успешное содержание и не одобрение. Вызывающий код получает
лучшие источники либо возвращает вопрос преподавателю; после изменения контекста
предыдущий review неприменим.

| Ошибка | Значение и действие вызывающего кода |
|---|---|
| `pydantic.ValidationError` при чтении входа | Вход не соответствует схеме; исправить его сборку |
| `ValueError` | Нет подтверждения, неверная входная идентичность, устаревшая или неверно адресованная правка |
| `AgentResponseError` | Невалидный/слишком большой ответ модели, неверная версия результата или неизвестный адрес замечания; ответ не использовать |
| `InsufficientMaterialsError` | Явный отказ по материалам; `.failure` содержит темы и причину |
| `ContentValidationError` | Содержание нарушило локальные правила; `.issues`, `.content` и `.feedback` позволяют адресованное исправление |
| `TimeoutError` / исключение адаптера | Результата нет; политику повторов и сообщение пользователю задаёт оркестратор |

`AgentResponseError` не включает сырые ответы или значения ученического контекста.
Не следует логировать полные промпты и ответы в общие логи. Исключения адаптера
пробрасываются как есть: сам адаптер обязан удалять чувствительные значения из ошибок
провайдера и своих логов.

## JSON-контракты

Источник истины — `src/prepa/schemas/content.py`; схема отдельной модели получается
через `Model.model_json_schema()`. Читать через `model_validate`/`model_validate_json`,
писать через `model_dump(mode="json")`/`model_dump_json`. Python-последовательности —
неизменяемые `tuple`, в JSON — массивы. Все модели `frozen=True`, неизвестные поля
запрещены, внешние пробелы строк удаляются. После изменения собирать новую модель
через валидацию: `model_construct` и `model_copy(update=...)` её обходят.

Общие ограничения: ID — 1–100 символов `[a-zA-Z0-9_-]`; текст — 1–20 000 символов;
тема — 1–160. Пустая строка после удаления пробелов запрещена. Версии, целочисленные
счётчики и время строгие; `bool` и строки вместо целого не подходят. `confirmed` —
строгий bool. `exam`: `oge`/`ege`; уровень: `basic`/`intermediate`/`advanced`.
Темы сравниваются точно, без синонимизации; порядок массивов сохраняется.

| Модель | Обязательные поля | Ограничения и defaults |
|---|---|---|
| `StudentProfile` | `student_id`, `grade`, `exam` | grade 9–11; `level="basic"`, `mastered_topics=[]` (до 100), `common_errors=[]` (до 50) |
| `LessonBrief` | `preparation_id`, `version`, `student_ids`, `exam`, `topics` | version ≥1; 1–2 уникальных ученика, 1–8 уникальных тем; `duration_minutes=60` (1–180), `theory_level="basic"`, `lesson_task_count=4` (1–20), `homework_task_count=2` (0–20), `homework_minutes=20` (0–180), `teacher_notes=null`, `confirmed=false` |
| `Material` | `material_id`, `title`, `source`, `exam`, `topics`, `content` | 1–50 тем; source — реальный URL, книга/страница или локальное происхождение, не обязательно URL |
| `GenerationContext` | `brief`, `students`, `materials` | 1–2 профиля, 1–50 материалов; уникальные ID в каждом наборе; профили точно совпадают с brief; экзамены одинаковы; библиотека покрывает все темы |
| `TextBlock` | `text` | `math=[]`, до 20 математических выражений |
| `GenerationFailure` | `status`, `missing_topics`, `reason` | status=`insufficient_material`; 1–8 уникальных тем; runtime требует subset тем brief; вместо успешного результата |
| `Formula` | `expression`, `meaning`, `conditions`, `units` | Математика, обозначения, условия и единицы обязательны |
| `WorkedExample` | `statement`, `answer`, `solution` | Условие/ответ — TextBlock, решение — 1–20 TextBlock |
| `TheorySection` | `section_id`, `topic`, `title`, `explanation`, `worked_examples`, `source_ids` | `formulas=[]` (до 20), 1–3 примера, 1–10 источников |
| `Theory` | `preparation_id`, `version`, `sections` | 1–32 раздела, уникальные section_id; локальная проверка требует всех тем brief |
| `Assignment` | `assignment_id`, `topic`, `difficulty`, `estimated_minutes`, `statement`, `answer`, `solution`, `source_ids` | difficulty 1–3, время 1–180, решение 1–20 блоков, 1–10 источников, `hints=[]` (до 5) |
| `Homework` | `student_id`, `rationale`, `assignments` | 1–20 заданий; rationale объясняет персонализацию для преподавателя |
| `AssignmentSet` | `preparation_id`, `version`, `lesson_assignments`, `homeworks` | 1–20 задач урока, до 2 ДЗ; homeworks обязательно, но может быть `[]`; получатели не повторяются, ID задач уникальны во всём комплекте |
| `ReviewIssue` | `author`, `target_id`, `severity`, `category`, `message`, `suggestion` | author=`theory`/`assignments`, severity=`error`/`warning`; категории ниже |
| `ReviewReport` | `preparation_id`, `version`, `summary` | `issues=[]`, до 100; ответ модели reviewer |
| `RepairFeedback` | `preparation_id`, `version`, `author`, `content_digest`, `issues` | 1–200 замечаний только этому автору; создаётся кодом для отклонённой генерации |
| `ReviewResult` | Поля ReviewReport, `theory_digest`, `assignments_digest` | До 400 объединённых замечаний; digest — 64 hex-символа SHA-256; `approved` — Python property, не JSON-поле |
| `LessonPackage` | `context`, `theory`, `assignments`, `review` | Подтверждение, локальные проверки, идентичность, адреса и digest; только review без error |
| `StudentAssignment` | `assignment_id`, `topic`, `estimated_minutes`, `statement`, `source_ids` | 1–10 ссылок для атрибуции задачи; без ответов, решений, подсказок и сложности |
| `SourceCitation` | `material_id`, `title`, `source` | Ссылка без сырого content |
| `StudentLesson` | `preparation_id`, `version`, `student_id`, `theory`, `lesson_assignments`, `homework`, `sources` | 1–20 задач урока, до 20 задач ДЗ, 1–50 источников; identity theory совпадает; ID задач и citations уникальны; все используемые ссылки присутствуют; theory сохраняет разобранные примеры |

Дополнительные инварианты brief: задач урока не меньше числа тем; объём/время ДЗ
одновременно нулевые либо положительные; количество задач не превышает доступные
минуты даже при минимуме по минуте на задачу. Во всём комплекте preparation_id/version
должны точно совпадать с brief. Все source_ids уникальны внутри своего элемента,
существуют в библиотеке, хотя бы один источник покрывает тему элемента.

`AssignmentSet.all_assignments()` возвращает tuple практики и всех ДЗ.
`ReviewResult.for_author(author)` — tuple замечаний указанному автору.
`LessonPackage.for_student(student_id)` — StudentLesson; чужой ID отклоняется.

В `prepa.schemas.validation` доступны `check_theory`, `check_assignments`,
`check_review`, `ensure_identity`, `content_digest`. Это структурные проверки.
Они не доказывают физику, реальность источника, уровень и отсутствие ответа внутри
условия. Сумма времени практики может равняться всему уроку; резерв на объяснение
требует предметной оценки reviewer, а не гарантируется кодом.

## Проверка, исправления и версии

Основной путь: `confirmed → theory → assignments → review → package → for_student`.
Агенты не меняют состояние диалога и не запускают друг друга. Модель возвращает
ReviewReport; runtime проверяет его адреса, добавляет локальные замечания и создаёт
ReviewResult с digest. Пустой `issues` не позволяет модели снять локальную ошибку.

Категории: `physics`, `units`, `answer`, `topic`, `level`, `source`, `coverage`, `timing`.
Каждое замечание адресует существующий section_id или assignment_id соответствующего
автора. `error` блокирует комплект; `warning` не блокирует. `approved` означает
отсутствие error, не подтверждение преподавателем и не поле JSON.

`content_digest(context, content)` хеширует канонический JSON всего контекста и
конкретного содержания. Изменение brief, профиля, библиотеки или результата делает
review/feedback устаревшим даже без изменения version. Digest защищает от случайного
смешивания состояний, не является подписью или проверкой доверия. `check_review` и
конструктор LessonPackage отклоняют устаревший ReviewResult.

Для внутреннего исправления используются вместе `previous` и `feedback`, в той же
подготовке/версии, с совпадающим digest и существующими адресами данного автора:

```python
if review.for_author("assignments"):
    assignments = await AssignmentsAgent(llm).generate(
        context,
        theory,
        previous=assignments,
        feedback=review,
    )
    review = await ReviewerAgent(llm).review(context, theory, assignments)
```

Для ошибки локальных правил ещё до полного review:

```python
try:
    theory = await TheoryAgent(llm).generate(context)
except ContentValidationError as error:
    assert isinstance(error.content, Theory)
    # Одна дополнительная попытка; общий budget задаёт оркестратор.
    theory = await TheoryAgent(llm).generate(
        context,
        previous=error.content,
        feedback=error.feedback,
    )
```

В последнем примере перехватывается ошибка именно TheoryAgent, поэтому `.content` —
Theory; в общем обработчике проверять `.feedback.author` и тип `.content`.
AssignmentsAgent также может отклонить входную теорию до LLM: такое замечание нужно
направить составителю теории. RepairFeedback не является review и не одобряет комплект.
После исправления всё равно нужны полный reviewer и создание LessonPackage.

Возвращается полный результат, не diff; промпт требует сохранять ID неизменённых
элементов. Исправление автора без адресованных ему замечаний запрещено. После новой
теории оркестратор проверяет зависимую практику и при необходимости генерирует её
заново, затем проверяет весь комплект. Digest правки assignments связывает предыдущие
задачи с контекстом, но не проверяет свежесть связи с переданной theory: это задача
оркестратора и финального reviewer.

Внешняя правка преподавателя создаёт новый brief.version. Оркестратор заново собирает
и подтверждает контекст, генерирует и проверяет комплект; previous/feedback старой
версии нельзя подставить в API исправления новой. Для любого сценария повторов нужны
явный предел попыток, общий срок и остановка с передачей преподавателю. Этот цикл
реализует участник 1, здесь нет скрытых retries.

## Документы и ученический вариант

Участник 3 получает `package.for_student(id)` для ученического документа. Проекция
оставляет общую теорию и практику, только ДЗ выбранного ученика и только нужные ссылки.
В каждой ученической задаче сохранены source_ids для атрибуции через sources.
Исключены answer/solution/hints упражнений, чужое ДЗ, профили, teacher notes, rationale,
review и сырое `materials[].content`. Разобранные примеры теории намеренно сохраняют
ответы и решения: это часть объяснения. Поиск всех ключей answer/solution рекурсивно
не является корректным тестом проекции.

Полный LessonPackage содержит ответы и персональный контекст, предназначен для
преподавателя. Не передавать его ученическому шаблону с надеждой скрыть поля там.
Проекция защищает структурные границы; ответ внутри statement.text обнаруживают
reviewer/преподаватель, не схема.

TextBlock.text — обычный текст, TextBlock.math и Formula.expression — математические
выражения LaTeX, не готовый `.tex`. В JSON обратную косую черту нужно экранировать:
`"\\frac{s}{t}"`. Схема не фильтрует TeX-команды. Документы обязаны экранировать текст,
ограничивать разрешённую математику, изолировать компиляцию, отключать shell escape
и задавать таймаут. Этот слой не выполняет TeX и не подтверждает сборку PDF.

## Handoff и ownership

| Участник | Что подключить | Проверка границы |
|---|---|---|
| 1: бот, оркестратор, llm, запуск | StructuredLLM, подтверждение, порядок вызовов, for_author, bounded repair, версии и обработку ошибок | Нет вызова до подтверждения; диалоги изолированы; одна версия на комплект; сбой не объявляется готовым результатом |
| 2: профили и история | Адаптер хранения в StudentProfile, выбор учеников, сохранение подтверждённых версий | Стабильный student_id, grade 9–11, общий exam; mastered_topics/common_errors из истории; demo не записывается в реальные профили |
| 3: библиотека и PDF | Поиск до генерации; Material с происхождением; безопасные документы из StudentLesson, отдельные ответы преподавателю | Библиотека покрывает темы; stable material_id; адаптация не названа ФИПИ; чужое ДЗ и библиотека не попадают ученику; русский текст/формулы собираются |
| 4: содержание и качество | schemas, theory, assignments, reviewer, промпты, локальные правила, demo и тесты | Контракт, адреса, объём, версия/digest и offline-путь; предметное качество отдельно по rubric |

Схемы — общий интерфейс команды. Изменять через PR с JSON до/после, описанием миграции
сохранённых данных и влияния на потребителей; согласовывать с владельцами затронутых
границ. В том же PR обновлять промпты, тесты, demo и документацию. Переименование,
новый enum и ужесточение ограничений могут нарушить совместимость. Не создавать копии
моделей в bot/db/documents и не добавлять поля провайдера в общий контракт.
brief.version — версия подготовки, не версия формата: миграцию схем планировать явно.
Формат результата PDF пока не задан участником 4; его согласуют участники 1 и 3.
