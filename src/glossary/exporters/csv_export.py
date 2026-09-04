"""Экспорт в CSV — импорт в таблицы, Anki и внешние инструменты."""

from __future__ import annotations

import csv
import io
from dataclasses import fields

from glossary.models import Entry, Glossary

__all__ = ["CsvExporter"]


class CsvExporter:
    """Плоская таблица: одна карточка — одна строка."""

    name = "csv"
    suffix = ".csv"

    def __init__(self, *, delimiter: str = ",") -> None:
        """Задать разделитель колонок."""
        self._delimiter = delimiter

    def render(self, glossary: Glossary) -> str:
        r"""Сериализовать карточки в CSV с заголовком.

        Используется ``\\r\\n`` — перевод строки, предписанный RFC 4180; он же
        нужен, чтобы многострочные примеры корректно читались Excel.
        """
        columns = [f.name for f in fields(Entry)]
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(
            buffer, fieldnames=columns, delimiter=self._delimiter, lineterminator="\r\n"
        )
        writer.writeheader()
        for entry in glossary.entries:
            writer.writerow(entry.to_dict())
        return buffer.getvalue()
