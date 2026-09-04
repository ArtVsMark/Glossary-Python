"""Фабрики тестовых данных.

Вынесены из ``conftest``, чтобы их можно было импортировать как обычный модуль:
``conftest`` предназначен для фикстур, а не для переиспользуемых функций.
"""

from __future__ import annotations

from typing import Any

from glossary.models import Entry, Glossary, Text

VALID_SUMMARY = (
    "Краткое описание достаточной длины: что делает и зачем нужно на практике."
)
VALID_SUMMARY_EN = (
    "A summary long enough to say both what the thing does and why it is useful."
)
VALID_BODY = (
    "Развёрнутый разбор: где конструкция ломается, чем её обычно путают и "
    "какая альтернатива дешевле в поддержке."
)
VALID_BODY_EN = (
    "A longer discussion: where the construct breaks, what it gets confused "
    "with, and which alternative is cheaper to maintain."
)


def make_entry(**overrides: Any) -> Entry:
    """Собрать корректную карточку, переопределив нужные поля.

    Карточка по умолчанию проходит все правила валидации, поэтому в тесте видно
    ровно то отклонение, которое он проверяет.
    """
    defaults: dict[str, Any] = {
        "id": "sample",
        "title": "sample()",
        "kind": "function",
        "summary": Text(ru=VALID_SUMMARY, en=VALID_SUMMARY_EN),
        "body": Text(ru=VALID_BODY, en=VALID_BODY_EN),
        "syntax": "sample() -> None",
        "status": "ready",
        "docs_url": "https://docs.python.org/3/library/functions.html#sample",
        "version": "",
        "section": "Раздел",
        "subcat": "подкатегория",
        "color_group": "builtin",
        "examples": ("sample()", "# → None"),
    }
    return Entry(**(defaults | overrides))


def make_glossary(*entries: Entry) -> Glossary:
    """Собрать глоссарий из карточек; без аргументов — с одной карточкой."""
    return Glossary(entries=entries or (make_entry(),))
