"""Экспорт в JSON — машиночитаемый обмен с другими проектами."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glossary.models import Glossary

__all__ = ["JsonExporter"]


class JsonExporter:
    """Плоский массив карточек без метаданных формата.

    В отличие от файла-источника здесь нет ключей ``$schema``/``schema_version``:
    результат предназначен для потребителей (например, базы знаний
    Stepik-Python-Grader), которым нужны сами карточки.
    """

    name = "json"
    suffix = ".json"

    def __init__(self, *, indent: int | None = 2) -> None:
        """Задать отступ; ``None`` — компактный JSON без переносов."""
        self._indent = indent

    def render(self, glossary: Glossary) -> str:
        """Сериализовать карточки в JSON."""
        return (
            json.dumps(
                [entry.to_dict() for entry in glossary.entries],
                ensure_ascii=False,
                indent=self._indent,
            )
            + "\n"
        )
