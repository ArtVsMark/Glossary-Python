"""Витрина и экспорт глоссария Python.

Пакет решает три задачи вокруг файла-источника ``data/glossary.json``:

* :mod:`glossary.validation` — проверка качества данных (полнота, дубликаты,
  консистентность ссылок и маркеров версий);
* :mod:`glossary.exporters` — сборка одностраничной HTML-витрины и экспорт в
  JSON, Markdown и CSV;
* :mod:`glossary.cli` — командный интерфейс поверх обоих.

У пакета нет runtime-зависимостей. Версия объявлена один раз, в
``pyproject.toml``; :data:`__version__` читает её из метаданных
дистрибутива (:mod:`glossary._version`).

Публичные имена отдаются **лениво** (PEP 562): импорт пакета не тянет за
собой валидатор, модели и загрузчик. Это граница замера языка —
:mod:`glossary.measure` исполняется на версиях ниже планки и обязан загрузить
только свою цепочку. Список имён и модулей — :data:`_LAZY`.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any, Final

from glossary._version import package_version

if TYPE_CHECKING:
    from glossary.errors import DataFormatError, ExportError, GlossaryError
    from glossary.loader import default_data_path, dump_glossary, load_glossary
    from glossary.models import SCHEMA_VERSION, ColorGroup, Entry, Glossary
    from glossary.validation import Issue, Severity, ValidationReport, validate

__version__ = package_version()
"""Версия дистрибутива. Объявлена в ``pyproject.toml`` и только там."""

_LAZY: Final[dict[str, str]] = {
    "DataFormatError": "glossary.errors",
    "ExportError": "glossary.errors",
    "GlossaryError": "glossary.errors",
    "default_data_path": "glossary.loader",
    "dump_glossary": "glossary.loader",
    "load_glossary": "glossary.loader",
    "SCHEMA_VERSION": "glossary.models",
    "ColorGroup": "glossary.models",
    "Entry": "glossary.models",
    "Glossary": "glossary.models",
    "Issue": "glossary.validation",
    "Severity": "glossary.validation",
    "ValidationReport": "glossary.validation",
    "validate": "glossary.validation",
}
"""Публичное имя → модуль, из которого оно отдаётся при первом обращении."""


def __getattr__(name: str) -> Any:  # noqa: ANN401 — имя любого вида, как в модуле
    """Отдать публичное имя при первом обращении (PEP 562).

    Raises:
        AttributeError: Имени в пакете нет.
    """
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Имена пакета вместе с ленивыми — для автодополнения и ``help``."""
    return sorted({*globals(), *_LAZY})


__all__ = [
    "SCHEMA_VERSION",
    "ColorGroup",
    "DataFormatError",
    "Entry",
    "ExportError",
    "Glossary",
    "GlossaryError",
    "Issue",
    "Severity",
    "ValidationReport",
    "__version__",
    "default_data_path",
    "dump_glossary",
    "load_glossary",
    "validate",
]
