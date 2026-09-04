"""Иерархия ошибок пакета."""

from __future__ import annotations

__all__ = ["DataFormatError", "ExportError", "GlossaryError"]


class GlossaryError(Exception):
    """Базовая ошибка пакета. Все остальные наследуются от неё."""


class DataFormatError(GlossaryError):
    """Файл данных повреждён или не соответствует ожидаемой структуре."""


class ExportError(GlossaryError):
    """Не удалось выполнить экспорт (нет шаблона, нераспознанный формат)."""
