"""Свод называет срок жизни окна: правило каталога 006.

Держится здесь одна вещь, зато та, ради которой раздел заведён: **срок назван
числом** там, где окно читает его при старте. Прозаическое «окно не должно жить
слишком долго» ни к чему не обязывает и не перечитывается.

Соблюдение срока не проверяется и проверено быть не может: возраст окна дереву
не наблюдаем ничем. Это названо в самом разделе, а не умолчано (правило 056).
"""

from __future__ import annotations

import re

import pytest

from glossary.loader import project_root

SVOD = project_root() / "CLAUDE.md"
SECTION = "## Про окно"
LIFETIME = re.compile(r"три–пять дней|3–5 дн|3-5 дн")
"""Срок, названный числом. Проза вместо числа ни к чему не обязывает."""

RELAY = ("как работаем", "где остановились", "ссылки на задачи")
"""Части эстафеты: без них перезапуск теряет то, ради чего он делается."""


@pytest.fixture(scope="module")
def window() -> str:
    """Раздел свода про окно, сведённый в одну строку.

    Пробелы нормализуются не для красоты: «где остановились» в живом своде
    разорвано переносом строки, и поиск подстрокой по сырому тексту нашёл бы
    пустоту. Разрыв ставит редактор ширины, а не автор — тот же класс, что
    правила 144 и 166.
    """
    text = SVOD.read_text(encoding="utf-8")
    assert SECTION in text, f"в своде нет раздела «{SECTION}» — окну негде прочесть срок"
    return " ".join(text.split(SECTION, 1)[1].split("\n## ", 1)[0].split())


@pytest.mark.live_surface
def test_lifetime_is_named_as_a_number(window: str):
    assert LIFETIME.search(window), (
        "срок жизни окна не назван числом. «Не слишком долго» ни к чему не "
        "обязывает: правило 006 просит именно число"
    )


@pytest.mark.live_surface
def test_relay_names_its_parts(window: str):
    missing = [part for part in RELAY if part not in window]
    assert not missing, "эстафета названа не полностью, недостаёт: " + ", ".join(missing)


@pytest.mark.live_surface
def test_the_section_says_what_it_cannot_check(window: str):
    """У сигнала пишут и то, чего он не означает (правило 056)."""
    assert "не наблюдаем" in window, (
        "раздел не говорит, что соблюдение срока машиной не проверяется — "
        "читатель принял бы названное число за проверяемое"
    )


def test_section_is_found_by_heading():
    """Разбор ищет заголовок, а не подстроку: слова «про окно» есть и в прозе."""
    text = SVOD.read_text(encoding="utf-8")
    assert text.count(SECTION) == 1, "заголовок раздела должен быть один"
