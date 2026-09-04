"""Доменные модели глоссария.

Модели неизменяемы: глоссарий загружается из файла-источника, проверяется и
экспортируется, но не мутируется в процессе. Это упрощает тестирование и
исключает случайные расхождения между разными экспортёрами.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING, Any, Final, Literal, Self, get_args

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = ["COLOR_GROUPS", "SCHEMA_VERSION", "ColorGroup", "Entry", "Glossary"]

SCHEMA_VERSION: Final = 1
"""Версия формата ``data/glossary.json``, поддерживаемая этим пакетом."""

ColorGroup = Literal[
    "builtin", "str", "seq", "mapset", "oop", "exc", "module", "iter", "op", "typing"
]
"""Цветовая группа карточки — определяет акцентный цвет в витрине."""

COLOR_GROUPS: Final[frozenset[str]] = frozenset(get_args(ColorGroup))


@dataclass(frozen=True, slots=True)
class Entry:
    """Одна карточка глоссария.

    Порядок полей значим: он определяет порядок ключей в экспортируемом JSON,
    а значит — воспроизводимость собранной витрины.
    """

    id: str
    name: str
    group: str
    subcat: str
    cg: str
    description: str
    syntax: str
    examples: str
    version: str | None
    docs: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        """Собрать карточку из сырого словаря, отбрасывая неизвестные ключи.

        Отсутствующие поля заменяются пустыми значениями: за их наличие отвечает
        валидатор, который сообщит о каждом пропуске отдельной ошибкой.
        """
        known = {f.name for f in fields(cls)}
        data: dict[str, Any] = {k: v for k, v in raw.items() if k in known}
        for name in known - data.keys():
            data[name] = None if name == "version" else ""
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        """Представить карточку словарём в каноническом порядке полей."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @property
    def example_lines(self) -> list[str]:
        """Примеры, разбитые на строки (в источнике они хранятся одной строкой)."""
        return self.examples.splitlines()


@dataclass(frozen=True, slots=True)
class Glossary:
    """Коллекция карточек вместе с метаданными формата."""

    entries: tuple[Entry, ...]
    schema_version: int = SCHEMA_VERSION
    _by_id: dict[str, Entry] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Построить индекс по идентификатору."""
        # Дубликаты id — ошибка валидации, а не загрузки: индекс строится по
        # первому вхождению, чтобы валидатор успел собрать полный отчёт.
        index: dict[str, Entry] = {}
        for entry in self.entries:
            index.setdefault(entry.id, entry)
        object.__setattr__(self, "_by_id", index)

    def __len__(self) -> int:
        """Количество карточек."""
        return len(self.entries)

    def __iter__(self) -> Iterator[Entry]:
        """Итерация по карточкам в исходном порядке."""
        return iter(self.entries)

    def get(self, entry_id: str) -> Entry | None:
        """Найти карточку по идентификатору."""
        return self._by_id.get(entry_id)

    @property
    def groups(self) -> tuple[str, ...]:
        """Разделы в порядке первого появления — он же порядок в витрине."""
        return tuple(dict.fromkeys(e.group for e in self.entries))

    def in_group(self, group: str) -> tuple[Entry, ...]:
        """Карточки одного раздела с сохранением исходного порядка."""
        return tuple(e for e in self.entries if e.group == group)

    def stats(self) -> GlossaryStats:
        """Сводная статистика по глоссарию."""
        return GlossaryStats(
            total=len(self.entries),
            groups=Counter(e.group for e in self.entries),
            color_groups=Counter(e.cg for e in self.entries),
            versioned=sum(1 for e in self.entries if e.version),
            avg_description=(
                sum(len(e.description) for e in self.entries) / len(self.entries)
                if self.entries
                else 0.0
            ),
        )


@dataclass(frozen=True, slots=True)
class GlossaryStats:
    """Агрегаты, которые показывает команда ``glossary stats``."""

    total: int
    groups: Counter[str]
    color_groups: Counter[str]
    versioned: int
    avg_description: float
