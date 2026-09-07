"""Связь изменения с задачей: правило каталога 173.

Набор держит две разные вещи. **Разбор ответа** — чистая функция, и её
проверяют предметом, который она обязана отвергнуть: «Часть #N» без названного
остатка и русское «Закрывает #N», которого площадка не исполняет. **Утверждение
о живом дереве** — что форма изменения предлагает все три ответа — проверяется
отдельно и своими словами (правило 146).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import check_pr_link as link
from glossary.loader import project_root

TEMPLATE = project_root() / ".github" / "pull_request_template.md"

PART_WITH_REMAINDER = """## Что меняется

Закрыто правило `146`.

## Связанные задачи

Часть #25. Остаток: 23 правила, признанных действующими и не держащихся ничем.
"""

PART_WITHOUT_REMAINDER = """## Связанные задачи

Часть #25.
"""

RUSSIAN_PROMISE = """## Связанные задачи

Закрывает #25 целиком.
"""


# --------------------------------------------------------------------------- #
# Три ответа, и четвёртого нет
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "body, kind",
    [
        ("Closes #25", "закрывает"),
        ("closes #7 — сделано", "закрывает"),
        ("Fixes #12", "закрывает"),
        ("Resolves #3", "закрывает"),
        (PART_WITH_REMAINDER, "часть"),
        ("Без задачи: правка опечатки в комментарии", "освобождено"),
    ],
    ids=["closes", "нижний регистр", "fixes", "resolves", "часть", "освобождено"],
)
def test_every_allowed_answer_is_read(body: str, kind: str):
    found = link.answer(body)
    assert found is not None
    assert found.kind == kind


def test_part_without_a_remainder_is_not_an_answer():
    """Тот самый предмет: частичное изменение обязано назвать остаток."""
    assert link.answer(PART_WITHOUT_REMAINDER) is None
    assert "остаток не назван" in link.complaint(PART_WITHOUT_REMAINDER)


def test_russian_promise_is_not_a_closing_word():
    """«Закрывает» читает человек, а не площадка: задача осталась бы открытой."""
    assert link.answer(RUSSIAN_PROMISE) is None


def test_exemption_without_a_reason_is_not_an_answer():
    assert link.answer("Без задачи:") is None
    assert link.answer("Без задачи:   ") is None


def test_empty_body_is_not_an_answer():
    assert link.answer("") is None
    assert "ни одним из трёх" in link.complaint("")


def test_remainder_in_another_paragraph_does_not_count():
    """Окно — абзац: остаток из чужого абзаца к этой задаче не относится."""
    body = "Часть #25.\n\nСовсем про другое: остаётся ещё дождь за окном.\n"
    assert link.answer(body) is None


def test_exemption_reason_is_returned_whole():
    found = link.answer("Без задачи: перенос строки в докстринге")
    assert found is not None
    assert found.detail == "перенос строки в докстринге"


@pytest.mark.parametrize(
    "text, expected",
    [("", []), ("один\n\nдва", ["один", "два"]), ("а\nб\n\n\n в ", ["а б", "в"])],
    ids=["пусто", "два абзаца", "склейка строк"],
)
def test_windows_are_paragraphs(text: str, expected: list[str]):
    assert link.paragraphs(text) == expected


# --------------------------------------------------------------------------- #
# Исходы команды
# --------------------------------------------------------------------------- #


def test_missing_variable_is_the_third_outcome(capsys, monkeypatch):
    monkeypatch.delenv("НЕТ_ТАКОЙ", raising=False)
    assert link.main(["--from-env", "НЕТ_ТАКОЙ"]) == link.NOT_RUN
    error = capsys.readouterr().err
    assert "не отработала" in error
    assert "НЕТ_ТАКОЙ" in error, "третий исход обязан назвать предмет (правило 158)"


def test_body_without_an_answer_returns_one(capsys, monkeypatch):
    monkeypatch.setenv("PR_BODY", PART_WITHOUT_REMAINDER)
    assert link.main([]) == 1
    assert "остаток не назван" in capsys.readouterr().err


def test_answered_body_returns_zero(capsys, monkeypatch):
    monkeypatch.setenv("PR_BODY", PART_WITH_REMAINDER)
    assert link.main([]) == 0
    assert "часть" in capsys.readouterr().out


def test_refusal_is_not_the_same_code_as_a_finding(monkeypatch):
    """«Не отработало» и «ответа нет» — разные исходы (правило 039).

    Сравниваются коды, которые команда ОТДАЛА в двух положениях, а не два
    литерала: равенство литералов доказуемо чтением и не проверяет ничего.
    """
    monkeypatch.delenv("НЕТ_ТАКОЙ", raising=False)
    refused = link.main(["--from-env", "НЕТ_ТАКОЙ"])
    monkeypatch.setenv("PR_BODY", PART_WITHOUT_REMAINDER)
    found = link.main([])
    assert refused != found, "проверка не отработала и ответа нет — разные вещи"


# --------------------------------------------------------------------------- #
# Утверждение о живом дереве (правило 037)
# --------------------------------------------------------------------------- #


@pytest.mark.live_surface
def test_template_offers_a_place_for_the_answer():
    """Форма изменения обязана спрашивать связь: иначе гейт ловит забывчивость."""
    assert TEMPLATE.exists(), f"формы изменения нет: {TEMPLATE}"
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "Связанные задачи" in text
    assert "Closes #" in text, "форма не показывает слова, которые площадка исполняет"


@pytest.mark.live_surface
def test_template_names_all_three_answers():
    """Форма показывает три ответа, а не один: два других иначе не найти."""
    text = TEMPLATE.read_text(encoding="utf-8")
    missing = [
        name
        for name, needle in (
            ("закрывает", "Closes #"),
            ("часть", "Часть #"),
            ("освобождено", "Без задачи:"),
        )
        if needle not in text
    ]
    assert not missing, "форма изменения молчит об ответах: " + ", ".join(missing)


@pytest.mark.live_surface
def test_template_itself_passes_the_gate():
    """Подсказки формы — образец: непроходящий образец учит писать непроходящее."""
    assert link.answer(Path(TEMPLATE).read_text(encoding="utf-8")) is not None
