"""Фабрики тестовых данных.

Вынесены из ``conftest``, чтобы их можно было импортировать как обычный модуль:
``conftest`` предназначен для фикстур, а не для переиспользуемых функций.
"""

from __future__ import annotations

from typing import Any

from glossary.models import Entry, Glossary

VALID_DESCRIPTION = (
    "Описание достаточной длины, объясняющее и что делает конструкция, "
    "и зачем она нужна на практике."
)


def make_entry(**overrides: Any) -> Entry:
    """Собрать корректную карточку, переопределив нужные поля.

    Карточка по умолчанию проходит все правила валидации, поэтому в тесте видно
    ровно то отклонение, которое он проверяет.
    """
    defaults: dict[str, Any] = {
        "id": "sample",
        "name": "sample()",
        "group": "Раздел",
        "subcat": "подкатегория",
        "cg": "builtin",
        "description": VALID_DESCRIPTION,
        "syntax": "sample() -> None",
        "examples": "sample()\n# → None",
        "version": None,
        "docs": "https://docs.python.org/3/library/functions.html#sample",
    }
    return Entry(**(defaults | overrides))


def make_glossary(*entries: Entry) -> Glossary:
    """Собрать глоссарий из карточек; без аргументов — с одной карточкой."""
    return Glossary(entries=entries or (make_entry(),))
