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

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version

from glossary.errors import DataFormatError, ExportError, GlossaryError
from glossary.loader import default_data_path, dump_glossary, load_glossary
from glossary.models import SCHEMA_VERSION, ColorGroup, Entry, Glossary
from glossary.validation import Issue, Severity, ValidationReport, validate

DISTRIBUTION = "glossary-python"

try:
    __version__ = _distribution_version(DISTRIBUTION)
except PackageNotFoundError:  # pragma: no cover - запуск из дерева без установки
    # Источник версии один — метаданные дистрибутива, собранные из
    # pyproject.toml (правило каталога 035). Второй записи здесь нет намеренно:
    # ручной дубль расходится молча и обнаруживается уже после публикации.
    #
    # Заглушка НЕ выглядит выпуском: «0+unknown» неотличимо от версии только для
    # того, кто её не читал, а «0.0.0» читалось бы как измеренный ноль.
    __version__ = "0+unknown"

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
