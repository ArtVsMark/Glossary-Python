"""Раздел «Статус» README называет, чего продукт не прошёл (правило каталога 106).

Прошёл ли глоссарий настоящий сценарий читателя, дереву не наблюдаемо. Наблюдаемо
другое: сказано ли об этом вслух — названы непроверенный класс и условие огласки.
"""

import re

from glossary.loader import project_root

README = project_root() / "README.md"


def status_section() -> str:
    """Текст раздела «Статус» до следующего заголовка второго уровня."""
    text = README.read_text("utf-8")
    match = re.search(
        r"^## Статус\n(?P<body>.*?)(?=^## )", text, re.MULTILINE | re.DOTALL
    )
    assert match, "в README нет раздела «## Статус»"
    return match.group("body")


def test_status_names_what_was_never_checked():
    assert "Не проверено" in status_section()


def test_status_names_the_condition_of_publicity():
    assert "Условие широкой огласки" in status_section()
