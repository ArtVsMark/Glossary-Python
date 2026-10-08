"""Документ статуса называет, чего продукт не прошёл (правило каталога 106).

Прошёл ли глоссарий настоящий сценарий читателя, дереву не наблюдаемо. Наблюдаемо
другое: сказано ли об этом вслух — названы непроверенный класс и условие огласки,
а README ведёт к этому документу.
"""

from glossary.loader import project_root

STATUS = project_root() / "docs" / "use" / "status.md"
README = project_root() / "README.md"


def test_status_names_what_was_never_checked():
    assert "## Не проверено" in STATUS.read_text("utf-8")


def test_status_names_the_condition_of_publicity():
    assert "## Условие широкой огласки" in STATUS.read_text("utf-8")


def test_readme_points_to_the_status():
    assert "(docs/use/status.md)" in README.read_text("utf-8")
