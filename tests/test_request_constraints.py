import pytest

from prepa.task_bank.reshai import request_numbers, request_part


@pytest.mark.parametrize(
    "text, expected",
    [
        ("магнетизм без второй части", 1),
        ("без первой части", 2),
        ("кроме 2 части", 1),
        ("не из второй части", 1),
        ("механика, задания 1 и 2 части", None),
        ("первая и вторая части", None),
        ("части 1 и 2", None),
        ("1-я часть", 1),
        ("задачи второй части", 2),
        ("30 задач по механике", None),
        ("12 часть", None),
        ("21 часть", None),
        ("30% первая часть, 70% вторая часть", None),
        ("не только первая часть, но и вторая часть", None),
        ("1 часть, без второй части", 1),
    ],
)
def test_part_constraints(text, expected):
    assert request_part(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("задания 24–26 по механике", {24, 25, 26}),
        ("номера 24-26", {24, 25, 26}),
        ("№ 24 — 26, 28 и 30", {24, 25, 26, 28, 30}),
        ("задания 24, 25 и 26", {24, 25, 26}),
        ("задачи 1 и 2 части", set()),
        ("задания 1 и 2 части", set()),
        ("задания 2-й части", set()),
        ("30 заданий, вторая часть", set()),
        ("первая часть, 30 задач", set()),
        ("номера 31-99", set()),
        ("номера 26-24", set()),
    ],
)
def test_number_constraints(text, expected):
    assert request_numbers(text) == expected
