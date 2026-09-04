"""Контракт экспортёра и реестр форматов."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from glossary.models import Glossary

__all__ = ["Exporter"]


@runtime_checkable
class Exporter(Protocol):
    """Преобразует глоссарий в текстовое представление одного формата.

    Экспортёр не работает с файловой системой: он возвращает строку, а запись
    на диск остаётся за вызывающим кодом. Это делает форматы тестируемыми без
    временных каталогов и позволяет отдавать результат в stdout.
    """

    name: str
    """Идентификатор формата в CLI, например ``markdown``."""

    suffix: str
    """Расширение файла по умолчанию, включая точку."""

    def render(self, glossary: Glossary) -> str:
        """Отрисовать глоссарий целиком."""
        ...
