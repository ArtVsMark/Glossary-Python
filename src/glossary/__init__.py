"""Витрина и экспорт глоссария Python.

Пакет решает три задачи вокруг файла-источника ``data/glossary.json``:

* :mod:`glossary.validation` — проверка качества данных (полнота, дубликаты,
  консистентность ссылок и маркеров версий);
* :mod:`glossary.exporters` — сборка одностраничной HTML-витрины и экспорт в
  JSON, Markdown и CSV;
* :mod:`glossary.cli` — командный интерфейс поверх обоих.

У пакета нет runtime-зависимостей.
"""

from __future__ import annotations

from glossary.errors import DataFormatError, ExportError, GlossaryError
from glossary.loader import default_data_path, dump_glossary, load_glossary
from glossary.models import SCHEMA_VERSION, ColorGroup, Entry, Glossary
from glossary.validation import Issue, Severity, ValidationReport, validate

__version__ = "0.1.0"

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
