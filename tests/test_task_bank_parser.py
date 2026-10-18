"""FIPI page parsing and MathML conversion on synthetic pages in the bank markup."""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from prepa.task_bank import AnswerKind, BankTask, ParseError
from prepa.task_bank.fipi.mathml import to_latex
from prepa.task_bank.fipi.parser import clean, parse_tasks, parse_topics, parse_total

FIXTURES = Path(__file__).parent / "fixtures"
PAGE_URL = "https://ege.fipi.ru/bank/questions.php"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def tasks() -> dict[str, BankTask]:
    found = parse_tasks(
        fixture("fipi_questions.html"),
        exam="ege",
        page_url=PAGE_URL,
        task_url=lambda task_id: f"https://bank.test/{task_id}",
    )
    return {task.task_id: task for task in found}


def latex(mathml: str) -> str:
    math = BeautifulSoup(f"<m:math>{mathml}</m:math>", "html.parser").find("m:math")
    assert math is not None
    return to_latex(math)


def test_topics_keep_page_order_titles_and_drop_duplicates() -> None:
    topics = parse_topics(fixture("fipi_index.html"))
    codes = [topic.code for topic in topics]
    assert codes == ["1", "2", "1.1", "1.1.5", "1.1.6", "1.2", "1.2.4", "1.5.1", "2.1.7"]
    titles = {topic.code: topic.title for topic in topics}
    assert titles["2"] == "Молекулярная физика. Термодинамика"
    assert titles["1.1.5"] == "Равномерное прямолинейное движение"
    assert titles["1.2.4"] == "Второй закон Ньютона"
    assert topics[3].depth == 3


def test_page_without_topics_or_count_is_a_parse_error() -> None:
    with pytest.raises(ParseError):
        parse_topics("<html><body>Технические работы</body></html>")
    with pytest.raises(ParseError):
        parse_total("<html></html>")
    assert parse_total(fixture("fipi_questions.html")) == 57


def test_short_answer_task_text_math_picture_unit_and_metadata() -> None:
    task = tasks()["1A2B3C"]
    assert task.answer_kind is AnswerKind.SHORT
    assert task.url == "https://bank.test/1A2B3C"
    assert [topic.code for topic in task.kes] == ["1.1.5"]
    assert task.instruction == "Впишите правильный ответ."
    assert task.statement == (
        "Велосипедист едет со скоростью $\\upsilon_1=18$ км/ч.\n"
        "Пользуясь графиком, найдите путь s за время t_1.\n"
        "[рисунок 1]"
    )
    assert task.images == ("https://ege.fipi.ru/docs/PROJ/questions/AAA/xs3qstsrc_1.png",)
    assert task.answer_unit == "м"
    assert task.has_images


def test_choice_task_options_and_several_kes_topics() -> None:
    task = tasks()["4D5E6F"]
    assert task.answer_kind is AnswerKind.MULTIPLE_CHOICE
    assert [topic.code for topic in task.kes] == ["1.1.6", "1.2.4"]
    assert "$x=2+\\frac{a t^2}{2}$" in task.statement
    assert "ignored" not in task.statement
    assert task.options == (
        "1) Начальная координата равна 2 м.",
        "2) Ускорение направлено против оси Ох.",
    )
    assert not task.has_images


def test_matching_task_joins_labels_and_resolves_formula_pictures() -> None:
    task = tasks()["7A8B9C"]
    assert task.answer_kind is AnswerKind.MATCHING
    assert task.matching_keys == ("А", "Б")
    assert "А) период обращения\nБ) линейная скорость" in task.statement
    assert "1) [рисунок 1]\n2) [рисунок 2]" in task.statement
    assert "_[" not in task.statement
    assert task.images == (
        "https://ege.fipi.ru/docs/PROJ/questions/BBB/innerimg0.gif",
        "https://ege.fipi.ru/docs/PROJ/questions/BBB/innerimg1.gif",
    )


def test_unknown_answer_type_and_missing_kes_are_tolerated() -> None:
    task = tasks()["e0F1A2"]
    assert task.answer_kind is AnswerKind.OTHER
    assert task.kes == ()
    assert task.statement.startswith("Изотоп ${}_{6}^{14}X$ распадается.")


def test_task_without_statement_cell_is_a_parse_error() -> None:
    html = "<div class='qblock' id='qABC123'><p>нет ячейки условия</p></div>"
    with pytest.raises(ParseError, match="ABC123"):
        parse_tasks(html, exam="oge", page_url=PAGE_URL, task_url=str)


def test_statement_made_only_of_a_picture_gets_placeholder_text() -> None:
    html = (
        "<div class='qblock' id='qABC123'><table><tr><td class='cell_0'> </td></tr></table></div>"
    )
    (task,) = parse_tasks(html, exam="oge", page_url=PAGE_URL, task_url=str)
    assert task.statement == "(условие только на рисунке)"
    assert task.instruction == ""


def test_clean_collapses_spaces_and_removes_space_before_punctuation() -> None:
    assert clean("  а\xa0 б ,  в \n\n 1)\n текст ") == "а б, в\n1) текст"


@pytest.mark.parametrize(
    ("mathml", "expected"),
    [
        (
            "<m:mi>x</m:mi><m:mo>−</m:mo><m:mn>4</m:mn><m:msup><m:mi>t</m:mi><m:mn>2</m:mn></m:msup>",
            "x-4 t^2",
        ),
        ("<m:msub><m:mi>υ</m:mi><m:mi>x</m:mi></m:msub>", "\\upsilon_x"),
        ("<m:msub><m:mi>F</m:mi><m:mtext>тр</m:mtext></m:msub>", "F_{\\text{тр}}"),
        (
            "<m:mfrac><m:mtext>м</m:mtext><m:mtext>с</m:mtext></m:mfrac>",
            "\\frac{\\text{м}}{\\text{с}}",
        ),
        ("<m:msqrt><m:mn>2</m:mn><m:mi>g</m:mi><m:mi>h</m:mi></m:msqrt>", "\\sqrt{2 g h}"),
        ("<m:mroot><m:mi>x</m:mi><m:mn>3</m:mn></m:mroot>", "\\sqrt[3]{x}"),
        ("<m:mover accent='true'><m:mi>F</m:mi><m:mo>→</m:mo></m:mover>", "\\vec{F}"),
        ("<m:mover><m:mi>x</m:mi><m:mo>*</m:mo></m:mover>", "\\overset{*}{x}"),
        ("<m:msubsup><m:mi>x</m:mi><m:mn>0</m:mn><m:mn>2</m:mn></m:msubsup>", "x_0^2"),
        (
            "<m:mn>1</m:mn><m:mn>0</m:mn><m:mo>⋅</m:mo><m:msup><m:mn>10</m:mn><m:mn>5</m:mn></m:msup>",
            "10 \\cdot{10}^5",
        ),
        ("<m:mi>Δ</m:mi><m:mi>t</m:mi><m:mo>≈</m:mo><m:mn>0,5</m:mn>", "\\Delta t \\approx 0,5"),
        ("<m:mi>α</m:mi><m:mo>=</m:mo><m:mn>30</m:mn><m:mo>°</m:mo>", "\\alpha=30^\\circ"),
        (
            "<m:mfenced open='[' close=']'><m:mi>a</m:mi><m:mi>b</m:mi></m:mfenced>",
            "\\left[a,b\\right]",
        ),
        (
            "<m:mtable><m:mtr><m:mtd><m:mn>1</m:mn></m:mtd><m:mtd><m:mn>2</m:mn></m:mtd></m:mtr>"
            "</m:mtable>",
            "\\begin{matrix}1 & 2\\end{matrix}",
        ),
        (
            "<m:mmultiscripts><m:mi>U</m:mi><m:mprescripts/><m:mn>92</m:mn><m:mn>238</m:mn>"
            "</m:mmultiscripts>",
            "{}_{92}^{238}U",
        ),
        ("<m:mmultiscripts><m:mi>x</m:mi><m:mn>1</m:mn><m:none/></m:mmultiscripts>", "x_{1}"),
        (
            "<m:mi>a</m:mi><m:mspace/><m:mtext> </m:mtext><m:mtext>и так</m:mtext>",
            "a~~\\text{и так}",
        ),
        ("<m:mtext>max</m:mtext><m:mphantom><m:mi>q</m:mi></m:mphantom>", "max"),
        ("<m:semantics></m:semantics>", ""),
    ],
)
def test_mathml_to_latex(mathml: str, expected: str) -> None:
    assert latex(mathml) == expected
