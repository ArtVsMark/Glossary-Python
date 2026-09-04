"""Форматы экспорта глоссария.

Реестр :data:`EXPORTERS` — единственное место, куда добавляется новый формат;
CLI перечисляет доступные варианты по нему автоматически.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from glossary.errors import ExportError
from glossary.exporters.base import Exporter
from glossary.exporters.csv_export import CsvExporter
from glossary.exporters.html import HtmlExporter
from glossary.exporters.json_export import JsonExporter
from glossary.exporters.markdown import MarkdownExporter

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "EXPORTERS",
    "CsvExporter",
    "Exporter",
    "HtmlExporter",
    "JsonExporter",
    "MarkdownExporter",
    "get_exporter",
]

_FACTORIES: Final[Mapping[str, type[Exporter]]] = {
    "html": HtmlExporter,
    "json": JsonExporter,
    "markdown": MarkdownExporter,
    "csv": CsvExporter,
}

EXPORTERS: Final[tuple[str, ...]] = tuple(_FACTORIES)
"""Имена доступных форматов в порядке приоритета для документации и CLI."""


def get_exporter(name: str) -> Exporter:
    """Создать экспортёр по имени формата.

    Raises:
        ExportError: формат не зарегистрирован.
    """
    try:
        factory = _FACTORIES[name]
    except KeyError as exc:
        raise ExportError(
            f"Неизвестный формат {name!r}; доступны: {', '.join(EXPORTERS)}"
        ) from exc
    return factory()
